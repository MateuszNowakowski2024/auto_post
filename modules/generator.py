import os
import random
import math
from .utils import *
from .s3 import S3Manager
from moviepy.editor import VideoFileClip, AudioFileClip, concatenate_audioclips


class SlideshowGenerator:
    def __init__(
        self, width, height, speed, quality, text_configs, audio_path,
        folder1, folder2, output_file, random_choice=True, opposite=False,
        duration=40, video_max_length=20, transition_duration=2,
        s3_video_bucket=None, s3_video_key=None
    ):
        
        self.width = width
        self.height = height
        self.quality = quality
        self.text_configs = prepare_text_configs(text_configs, width)
        self.audio_path = audio_path
        self.folder1 = folder1
        self.folder2 = folder2
        self.output_file = output_file
        self.random_choice = random_choice
        self.opposite = opposite
        self.duration = duration
        self.speed = speed
        self.video_max_length = video_max_length
        self.transition_duration = transition_duration
        self.s3_manager = S3Manager()
        self.s3_video_bucket = s3_video_bucket
        self.s3_video_key = s3_video_key

    def generate_mode_a(self):
        """
        Mode A: Two-row layout.
        Video is split horizontally into two rows. Top row from folder1, bottom from folder2.
        """
        processed_text_configs = self.text_configs

        row_height = self.height // 2
        total_frames = int(self.speed * (self.video_max_length if self.video_max_length else self.duration))
        transition_frames = int(self.speed * self.transition_duration)
        N_full = (total_frames - 1) // transition_frames
        remainder = (total_frames - 1) % transition_frames
        needed_images = N_full + 2 if remainder > 0 else N_full + 1

        sequence1, sequence2 = [], []

        bucket1, _ = self.s3_manager.parse_s3_path(self.folder1)
        bucket2, _ = self.s3_manager.parse_s3_path(self.folder2)

        if self.random_choice:
            files_folder1 = self.s3_manager.list_images(self.folder1)
            files_folder2 = self.s3_manager.list_images(self.folder2)

            mapping_folder2 = {}
            for key in files_folder2:
                base = os.path.basename(key)
                m = re.search(r'(\d+)', base)
                if m:
                    num = int(m.group(1))
                    mapping_folder2[num] = key

            eligible_A_files = [
                key for key in files_folder1
                if (m := re.search(r'(\d+)', os.path.basename(key))) and int(m.group(1)) in mapping_folder2
            ]

            if len(eligible_A_files) < needed_images:
                print(f"Not enough matching images. Required: {needed_images}, found: {len(eligible_A_files)}")
                return

            selected_files_1 = random.sample(eligible_A_files, needed_images)
            for key in selected_files_1:
                img1 = self.s3_manager.read_image(bucket1, key)
                if img1 is None:
                    continue
                sequence1.append(resize_to_width(img1, self.width))

                num = int(re.search(r'(\d+)', os.path.basename(key)).group(1))
                file2 = mapping_folder2.get(num)
                if file2:
                    img2 = self.s3_manager.read_image(bucket2, file2)
                    if img2 is not None:
                        sequence2.append(resize_to_width(img2, self.width))
                else:
                    print(f"No matching file for key {num} in folder2.")
        else:
            files_folder1 = self.s3_manager.list_images(self.folder1)
            files_folder2 = self.s3_manager.list_images(self.folder2)

            if not files_folder1 or not files_folder2:
                print("No images found in one or both folders.")
                return

            loaded1 = [resize_to_width(self.s3_manager.read_image(bucket1, key), self.width)
                    for key in files_folder1 if self.s3_manager.read_image(bucket1, key) is not None]

            loaded2 = [resize_to_width(self.s3_manager.read_image(bucket2, key), self.width)
                    for key in files_folder2 if self.s3_manager.read_image(bucket2, key) is not None]

            sequence1 = [loaded1[i % len(loaded1)] for i in range(needed_images)]
            sequence2 = [loaded2[i % len(loaded2)] for i in range(needed_images)]

            # SHIFT the first image of folder2 to the end.
        if len(sequence2) > 1:
            first_image = sequence2.pop(0)
            sequence1.append(first_image)
        
        # Reverse sequences if opposite is True
        if self.opposite:
            if len(sequence1) > 1:
                sequence1 = sequence1[-0:] + sequence1[:-0]
            sequence2 = sequence2[::-1]

        scroll_speed_top = sequence1[0].shape[0] / (self.transition_duration * self.speed)
        scroll_speed_bottom = sequence2[0].shape[0] / (self.transition_duration * self.speed)

        required_height_top = row_height + int(scroll_speed_top * total_frames)
        required_height_bottom = row_height + int(scroll_speed_bottom * total_frames)

        composite_top = build_composite_column(sequence1, required_height_top)
        composite_bottom = build_composite_column(sequence2, required_height_bottom)

        if composite_top is None or composite_bottom is None:
            print("Error building composite strips.")
            return

        writer = generate_video_writer(self.output_file, self.width, self.height, self.quality, self.speed)

        for f in range(total_frames):
            offset_top = min(int(f * scroll_speed_top), composite_top.shape[0] - row_height)
            offset_bottom = min(int(f * scroll_speed_bottom), composite_bottom.shape[0] - row_height)
            
            if self.opposite:
                offset_bottom = max(composite_bottom.shape[0] - row_height - offset_bottom, 0)

            top_crop = composite_top[offset_top: offset_top + row_height, :]
            bottom_crop = composite_bottom[offset_bottom: offset_bottom + row_height, :]

            composite_frame = np.vstack((top_crop, bottom_crop))
            
            if processed_text_configs:
                composite_frame = add_text_overlays(composite_frame, processed_text_configs)

            writer.write(composite_frame)

        writer.release()
        print(f"Successfully created video: {self.output_file}")

        # Attach audio using your class method
        self.attach_audio()
        
    def generate_mode_b(self):
        """
        Mode B: Two-column layout.
        The video is split vertically into 2 equal columns.
        Images are resized to squares with side = self.width // 2.
        """
        # Parse S3 URIs internally using self.folder1 and self.folder2
        bucket1, _ = self.s3_manager.parse_s3_path(self.folder1)
        bucket2, _ = self.s3_manager.parse_s3_path(self.folder2)
        
        processed_text_configs = self.text_configs
        img_size = self.width // 2
        total_frames = int(self.speed * (self.video_max_length if self.video_max_length is not None else self.duration))
        scroll_speed = img_size / (self.transition_duration * self.speed)
        required_height = self.height + int(scroll_speed * total_frames)
        needed_images = int(math.ceil(required_height / img_size))
        
        column1 = []
        column2 = []
        
        if self.random_choice:
            files_folder1 = self.s3_manager.list_images(self.folder1)
            files_folder2 = self.s3_manager.list_images(self.folder2)
            
            # Build mapping for folder2 using numeric keys extracted from basename.
            mapping_folder2 = {}
            for key in files_folder2:
                base = os.path.basename(key)
                m = re.search(r'(\d+)', base)
                if m:
                    num = int(m.group(1))
                    mapping_folder2[num] = key
            
            eligible_A_files = []
            for key in files_folder1:
                base = os.path.basename(key)
                m = re.search(r'(\d+)', base)
                if m and int(m.group(1)) in mapping_folder2:
                    eligible_A_files.append(key)
            
            if len(eligible_A_files) < needed_images:
                print(f"Not enough matching images. Required: {needed_images}, found: {len(eligible_A_files)}")
                return
            
            selected_files_1 = random.sample(eligible_A_files, needed_images)
            for key in selected_files_1:
                img1 = self.s3_manager.read_image(bucket1, key)
                if img1 is None:
                    continue
                resized1 = resize_to_square(img1, img_size)
                column1.append(resized1)
                
                base = os.path.basename(key)
                m = re.search(r'(\d+)', base)
                if m:
                    num = int(m.group(1))
                    file2 = mapping_folder2.get(num)
                    if file2:
                        img2 = self.s3_manager.read_image(bucket2, file2)
                        if img2 is None:
                            continue
                        resized2 = resize_to_square(img2, img_size)
                        column2.append(resized2)
                    else:
                        print(f"Matching file for key {num} not found in folder2")
        else:
            files_folder1 = self.s3_manager.list_images(self.folder1)
            files_folder2 = self.s3_manager.list_images(self.folder2)
            if not files_folder1 or not files_folder2:
                print("No images found in one or both folders.")
                return
            loaded1 = []
            for key in files_folder1:
                img = self.s3_manager.read_image(bucket1, key)
                if img is not None:
                    loaded1.append(resize_to_square(img, img_size))
            loaded2 = []
            for key in files_folder2:
                img = self.s3_manager.read_image(bucket2, key)
                if img is not None:
                    loaded2.append(resize_to_square(img, img_size))
            column1 = [loaded1[i % len(loaded1)] for i in range(needed_images)]
            column2 = [loaded2[i % len(loaded2)] for i in range(needed_images)]
        
        if self.opposite:
            if len(column1) > 1:
                column1 = column1[-0:] + column1[:-0]
            column2 = column2[::-1]
        
        composite_left = build_composite_column(column1, required_height)
        composite_right = build_composite_column(column2, required_height)
        if composite_left is None or composite_right is None:
            print("Error building composite columns.")
            return
        
        comp_left_height = composite_left.shape[0]
        comp_right_height = composite_right.shape[0]
        
        writer = generate_video_writer(self.output_file, self.width, self.height, self.quality, self.speed)
        
        for f in range(total_frames):
            offset_left = int(f * scroll_speed)
            if offset_left + self.height > comp_left_height:
                offset_left = comp_left_height - self.height
            left_crop = composite_left[offset_left: offset_left + self.height, :]
            
            if self.opposite:
                offset_right = comp_right_height - self.height - int(f * scroll_speed)
                if offset_right < 0:
                    offset_right = 0
            else:
                offset_right = int(f * scroll_speed)
                if offset_right + self.height > comp_right_height:
                    offset_right = comp_right_height - self.height
            right_crop = composite_right[offset_right: offset_right + self.height, :]
            
            composite_frame = np.hstack((left_crop, right_crop))
            if processed_text_configs:
                composite_frame = add_text_overlays(composite_frame, processed_text_configs)
            writer.write(composite_frame)
        
        writer.release()
        print(f"Successfully created video: {self.output_file}")
        self.attach_audio()
        
    def generate_mode_c(self):
        """
        Mode C: Four-column layout.
        The final canvas is divided into four vertical columns.
        Uses pairing logic based on common filenames between the two S3 folders.
        Top half of pairs builds columns 1 & 2; bottom half builds columns 3 & 4.
        """
        bucket1, _ = self.s3_manager.parse_s3_path(self.folder1)
        bucket2, _ = self.s3_manager.parse_s3_path(self.folder2)
        
        processed_text_configs = self.text_configs
        img_size = self.width // 4
        total_frames = int(self.speed * (self.video_max_length if self.video_max_length is not None else self.duration))
        scroll_speed = img_size / (self.transition_duration * self.speed)
        required_height = self.height + int(scroll_speed * total_frames)
        needed_images = int(math.ceil(required_height / img_size))
        
        # Build common pairs using basenames.
        files1 = self.s3_manager.list_images(self.folder1)
        files2 = self.s3_manager.list_images(self.folder2)
        folder1_map = {os.path.basename(k): k for k in files1}
        folder2_map = {os.path.basename(k): k for k in files2}
        common_basenames = set(folder1_map.keys()) & set(folder2_map.keys())
        common_pairs = [(folder1_map[basename], folder2_map[basename]) for basename in common_basenames]
        common_pairs.sort(key=lambda x: natural_sort_key(x[0]))
        if not common_pairs:
            print("No common images found between the two folders.")
            return
        
        total_pairs_needed = needed_images * 2
        if self.random_choice:
            if len(common_pairs) < total_pairs_needed:
                print(f"Need {total_pairs_needed} common pairs, found {len(common_pairs)}.")
                return
            selected_pairs = random.sample(common_pairs, total_pairs_needed)
        else:
            repeats = (total_pairs_needed + len(common_pairs) - 1) // len(common_pairs)
            cycled_pairs = common_pairs * repeats
            selected_pairs = cycled_pairs[:total_pairs_needed]
        
        top_pairs = selected_pairs[:needed_images]
        bottom_pairs = selected_pairs[needed_images: total_pairs_needed]
        
        col1_imgs, col2_imgs = [], []
        col3_imgs, col4_imgs = [], []
        
        for pair in top_pairs:
            img1 = self.s3_manager.read_image(bucket1, pair[0])
            img2 = self.s3_manager.read_image(bucket2, pair[1])
            if img1 is not None:
                col1_imgs.append(resize_to_square(img1, img_size))
            if img2 is not None:
                col2_imgs.append(resize_to_square(img2, img_size))
        for pair in bottom_pairs:
            img1 = self.s3_manager.read_image(bucket1, pair[0])
            img2 = self.s3_manager.read_image(bucket2, pair[1])
            if img1 is not None:
                col3_imgs.append(resize_to_square(img1, img_size))
            if img2 is not None:
                col4_imgs.append(resize_to_square(img2, img_size))
        
        if self.opposite:
            if len(col1_imgs) > 1:
                col1_imgs = col1_imgs[-1:] + col1_imgs[:-1]
            if len(col3_imgs) > 1:
                col3_imgs = col3_imgs[-1:] + col3_imgs[:-1]
            col2_imgs = col2_imgs[::-1]
            col4_imgs = col4_imgs[::-1]
        
        composite_1 = build_composite_column(col1_imgs, required_height)
        composite_2 = build_composite_column(col2_imgs, required_height)
        composite_3 = build_composite_column(col3_imgs, required_height)
        composite_4 = build_composite_column(col4_imgs, required_height)
        if any(x is None for x in [composite_1, composite_2, composite_3, composite_4]):
            print("Error building composite columns.")
            return
        
        comp_h1 = composite_1.shape[0]
        comp_h2 = composite_2.shape[0]
        comp_h3 = composite_3.shape[0]
        comp_h4 = composite_4.shape[0]
        
        writer = generate_video_writer(self.output_file, self.width, self.height, self.quality, self.speed)
        
        for f in range(total_frames):
            def get_offset(comp_h, base_speed, is_opposite):
                offset = comp_h - self.height - int(f * base_speed) if is_opposite else int(f * base_speed)
                return max(0, min(offset, comp_h - self.height))
            
            offset_1 = get_offset(comp_h1, scroll_speed, False)
            crop_1 = composite_1[offset_1: offset_1 + self.height, :]
            offset_2 = get_offset(comp_h2, scroll_speed, True)
            crop_2 = composite_2[offset_2: offset_2 + self.height, :]
            offset_3 = get_offset(comp_h3, scroll_speed, False)
            crop_3 = composite_3[offset_3: offset_3 + self.height, :]
            offset_4 = get_offset(comp_h4, scroll_speed, True)
            crop_4 = composite_4[offset_4: offset_4 + self.height, :]
            
            composite_frame = np.hstack((crop_1, crop_2, crop_3, crop_4))
            if processed_text_configs:
                composite_frame = add_text_overlays(composite_frame, processed_text_configs)
            writer.write(composite_frame)
        
        writer.release()
        print(f"Successfully created video: {self.output_file}")
        self.attach_audio()

    def generate_mode_d(self):
        """
        Mode D: Four-column large layout.
        Uses four columns where the two middle (foreground) columns are enlarged.
        Background (outer) columns come from top pairs and foreground (enlarged) columns from bottom pairs.
        The enlarged columns are centered in the final canvas.
        """
        bucket1, _ = self.s3_manager.parse_s3_path(self.folder1)
        bucket2, _ = self.s3_manager.parse_s3_path(self.folder2)
        
        processed_text_configs = self.text_configs
        img_size = self.width // 4
        enlarged_size = int(img_size * 1.3)
        
        total_frames = int(self.speed * (self.video_max_length if self.video_max_length is not None else self.duration))
        scroll_speed_bg = img_size / (self.transition_duration * self.speed)
        scroll_speed_fg = enlarged_size / (self.transition_duration * self.speed)
        required_height_bg = self.height + int(scroll_speed_bg * total_frames)
        required_height_fg = self.height + int(scroll_speed_fg * total_frames)
        
        # Pairing logic (common basenames)
        files1 = self.s3_manager.list_images(self.folder1)
        files2 = self.s3_manager.list_images(self.folder2)
        folder1_map = {os.path.basename(k): k for k in files1}
        folder2_map = {os.path.basename(k): k for k in files2}
        common_basenames = set(folder1_map.keys()) & set(folder2_map.keys())
        common_pairs = [(folder1_map[bn], folder2_map[bn]) for bn in common_basenames]
        common_pairs.sort(key=lambda x: natural_sort_key(x[0]))
        if not common_pairs:
            print("No common images found between the two folders.")
            return
        
        needed_images = int(math.ceil(required_height_bg / img_size))
        total_pairs_needed = needed_images * 2
        if self.random_choice:
            if len(common_pairs) < total_pairs_needed:
                print(f"Need {total_pairs_needed} common pairs, found {len(common_pairs)}.")
                return
            selected_pairs = random.sample(common_pairs, total_pairs_needed)
        else:
            repeats = (total_pairs_needed + len(common_pairs) - 1) // len(common_pairs)
            cycled_pairs = common_pairs * repeats
            selected_pairs = cycled_pairs[:total_pairs_needed]
        
        top_pairs = selected_pairs[:needed_images]
        bottom_pairs = selected_pairs[needed_images: total_pairs_needed]
        
        # Build image lists.
        col1_imgs = []
        col2_imgs = []
        for pair in top_pairs:
            img1 = self.s3_manager.read_image(bucket1, pair[0])
            img2 = self.s3_manager.read_image(bucket2, pair[1])
            if img1 is not None:
                col1_imgs.append(resize_to_square(img1, img_size))
            if img2 is not None:
                col2_imgs.append(resize_to_square(img2, img_size))
        col3_imgs_fg = []
        col4_imgs_fg = []
        for pair in bottom_pairs:
            img1 = self.s3_manager.read_image(bucket1, pair[0])
            img2 = self.s3_manager.read_image(bucket2, pair[1])
            if img1 is not None:
                col3_imgs_fg.append(resize_to_square(img1, enlarged_size))
            if img2 is not None:
                col4_imgs_fg.append(resize_to_square(img2, enlarged_size))

        composite_bg_1 = build_composite_column(col1_imgs, required_height_bg)
        composite_bg_2 = build_composite_column(col2_imgs, required_height_bg)
        composite_fg_2 = build_composite_column(col4_imgs_fg, required_height_fg)
        composite_fg_3 = build_composite_column(col3_imgs_fg, required_height_fg)
        if any(x is None for x in [composite_bg_1, composite_bg_2, composite_fg_2, composite_fg_3]):
            print("Error building composite columns.")
            return
        
        writer = generate_video_writer(self.output_file, self.width, self.height, self.quality, self.speed)
        
        # Fixed x positions for background columns.
        x_bg1 = 0
        x_bg2 = self.width - img_size
        total_fg_width = 2 * enlarged_size
        x_start = (self.width - total_fg_width) // 2
        if x_start < 0 or (x_start + total_fg_width) > self.width:
            new_enlarged_size = self.width // 2
            composite_fg_2 = cv2.resize(composite_fg_2, (new_enlarged_size, composite_fg_2.shape[0]))
            composite_fg_3 = cv2.resize(composite_fg_3, (new_enlarged_size, composite_fg_3.shape[0]))
            enlarged_size = new_enlarged_size
            x_start = (self.width - (2 * enlarged_size)) // 2
        x_fg2 = x_start
        x_fg3 = x_start + enlarged_size
        
        def get_offset(f, spd, comp_h, is_foreground=False):
            base_offset = int(f * spd)
            current_opposite = self.opposite if not is_foreground else False  # Match Script B's logic
            offset = comp_h - self.height - base_offset if current_opposite else base_offset
            return max(0, min(offset, comp_h - self.height))
        
        for f in range(total_frames):
            off_bg1 = get_offset(f, scroll_speed_bg, composite_bg_1.shape[0])
            off_bg2 = get_offset(f, scroll_speed_bg, composite_bg_2.shape[0])
            off_fg2 = get_offset(f, scroll_speed_fg, composite_fg_2.shape[0], is_foreground=True)
            off_fg3 = get_offset(f, scroll_speed_fg, composite_fg_3.shape[0], is_foreground=True)
            
            crop_bg1 = composite_bg_1[off_bg1: off_bg1 + self.height, :]
            crop_bg2 = composite_bg_2[off_bg2: off_bg2 + self.height, :]
            crop_fg2 = composite_fg_2[off_fg2: off_fg2 + self.height, :]
            crop_fg3 = composite_fg_3[off_fg3: off_fg3 + self.height, :]
            
            canvas = np.zeros((self.height, self.width, 3), dtype=np.uint8)
            canvas[:, x_bg1:x_bg1+img_size] = crop_bg1
            canvas[:, x_bg2:x_bg2+img_size] = crop_bg2
            canvas[:, x_fg2:x_fg2+enlarged_size] = crop_fg2
            canvas[:, x_fg3:x_fg3+enlarged_size] = crop_fg3
            
            if processed_text_configs:
                canvas = add_text_overlays(canvas, processed_text_configs)
            writer.write(canvas)
        
        writer.release()
        print(f"Successfully created video: {self.output_file}")
        self.attach_audio()
    
    
    def generate_slideshow(self, mode):
        if mode == 'a':
            self.generate_mode_a()
        elif mode == 'b':
            self.generate_mode_b()
        elif mode == 'c':
            self.generate_mode_c()
        elif mode == 'd':
            self.generate_mode_d()
        else:
            raise ValueError(f"Invalid mode '{mode}' selected.")
         
        return self.upload_video()
        
            
    def upload_video(self):
        return self.s3_manager.upload_file(
            self.output_file, self.s3_video_bucket, self.s3_video_key
        )
    
    def attach_audio(self):
        """Attaches the audio file to the video and rewrites the output file."""
        audio_file_path = self.audio_path
        output_file = self.output_file

        if audio_file_path and os.path.exists(audio_file_path):
            # Handle directory containing multiple audio files
            if os.path.isdir(audio_file_path):
                music_files = [os.path.join(audio_file_path, file) 
                               for file in os.listdir(audio_file_path) 
                               if file.lower().endswith(('.mp3', '.wav', '.aac', '.flac', '.ogg'))]
                if not music_files:
                    print("No music files found in directory.")
                    return
                audio_file_path = random.choice(music_files)

            try:
                video_clip = VideoFileClip(output_file)
                video_duration = video_clip.duration
                audio_clip = AudioFileClip(audio_file_path)
                audio_duration = audio_clip.duration

                if audio_duration == 0:
                    print("Invalid audio duration.")
                    return

                if audio_duration < video_duration:
                    loops = int(math.ceil(video_duration / audio_duration))
                    final_audio = concatenate_audioclips([audio_clip] * loops).subclip(0, video_duration)
                else:
                    final_audio = audio_clip.subclip(0, video_duration)

                final_clip = video_clip.set_audio(final_audio)
                temp_output = output_file.replace(".mp4", "_temp.mp4")
                final_clip.write_videofile(temp_output, codec='libx264', audio_codec='aac')

                video_clip.close()
                audio_clip.close()
                final_clip.close()
                os.replace(temp_output, output_file)
                print("Audio added successfully to the video.")

            except Exception as e:
                print("Audio error:", str(e))