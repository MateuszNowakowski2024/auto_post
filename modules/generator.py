import os
import random
import math
from .utils import *
from .s3 import S3Manager
from moviepy.editor import VideoFileClip, AudioFileClip, concatenate_audioclips


class SlideshowGenerator:
    def __init__(
        self, width, height, speed, quality, text_configs, audio_path,
        folder1, folder2, single_slideshow_folder, output_file, random_choice=True, opposite=False,
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
        self.single_slideshow_folder = single_slideshow_folder
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
    
    # ##################################################################################
    # Mode E: Combined slideshow with background frames built from two S3 folders 
    # ################################################################################### 

    def generate_mode_e(self):


        processed_text_configs = self.text_configs

        # --- Determine Frame and Row Parameters ---
        row_height = math.ceil(self.height / 6)
        total_frames = int(self.speed * (self.video_max_length if self.video_max_length is not None else self.duration))
        transition_frames = int(self.speed * self.transition_duration)
        N_full = (total_frames - 1) // transition_frames
        remainder = (total_frames - 1) % transition_frames
        needed_images = N_full + 2 if remainder > 0 else N_full + 1

        # --- List and Match Images from S3 ---
        bucket1, _ = self.s3_manager.parse_s3_path(self.folder1)
        bucket2, _ = self.s3_manager.parse_s3_path(self.folder2)
        files1 = self.s3_manager.list_images(self.folder1)
        files2 = self.s3_manager.list_images(self.folder2)

        folder1_map = {os.path.basename(f): f for f in files1}
        folder2_map = {os.path.basename(f): f for f in files2}
        common_pairs = []
        common = set(folder1_map.keys()) & set(folder2_map.keys())
        for basename in common:
            common_pairs.append((folder1_map[basename], folder2_map[basename]))
        common_pairs.sort(key=lambda x: natural_sort_key(x[0]))
        if not common_pairs:
            print("No common images found between the two S3 folders for mode A.")
            return

        # --- Select Image Pairs for 3 Groups (6 Rows) ---
        if self.random_choice:
            if len(common_pairs) < needed_images * 3:
                print(f"Need {needed_images*3} common images, found {len(common_pairs)}.")
                return
            selected_pairs = random.sample(common_pairs, needed_images * 3)
        else:
            total_needed = needed_images * 3
            repeats = (total_needed + len(common_pairs) - 1) // len(common_pairs)
            selected_pairs = (common_pairs * repeats)[:total_needed]

        group1 = selected_pairs[:needed_images]
        group2 = selected_pairs[needed_images:needed_images*2]
        group3 = selected_pairs[needed_images*2:needed_images*3]

        # --- Load and Resize Images from S3 ---
        row1_imgs, row2_imgs = [], []
        row3_imgs, row4_imgs = [], []
        row5_imgs, row6_imgs = [], []
        for pair in group1:
            img1 = self.s3_manager.read_image(bucket1, pair[0])
            img2 = self.s3_manager.read_image(bucket2, pair[1])
            if img1 is not None:
                row1_imgs.append(resize_to_height(img1, row_height))
            if img2 is not None:
                row2_imgs.append(resize_to_height(img2, row_height))
        for pair in group2:
            img1 = self.s3_manager.read_image(bucket1, pair[0])
            img2 = self.s3_manager.read_image(bucket2, pair[1])
            if img1 is not None:
                row3_imgs.append(resize_to_height(img1, row_height))
            if img2 is not None:
                row4_imgs.append(resize_to_height(img2, row_height))
        for pair in group3:
            img1 = self.s3_manager.read_image(bucket1, pair[0])
            img2 = self.s3_manager.read_image(bucket2, pair[1])
            if img1 is not None:
                row5_imgs.append(resize_to_height(img1, row_height))
            if img2 is not None:
                row6_imgs.append(resize_to_height(img2, row_height))

        # --- Adjust Rows if 'opposite' is True ---
        if self.opposite:
            if len(row1_imgs) > 1:
                row1_imgs = row1_imgs[-3:] + row1_imgs[:-3]
            if len(row3_imgs) > 1:
                row3_imgs = row3_imgs[-3:] + row3_imgs[:-3]
            if len(row5_imgs) > 1:
                row5_imgs = row5_imgs[-3:] + row5_imgs[:-3]
            row2_imgs = row2_imgs[::-1]
            row4_imgs = row4_imgs[::-1]
            row6_imgs = row6_imgs[::-1]

        base_w1 = row1_imgs[0].shape[1] if row1_imgs else 0
        base_w2 = row2_imgs[0].shape[1] if row2_imgs else 0
        base_w3 = row3_imgs[0].shape[1] if row3_imgs else 0
        base_w4 = row4_imgs[0].shape[1] if row4_imgs else 0
        base_w5 = row5_imgs[0].shape[1] if row5_imgs else 0
        base_w6 = row6_imgs[0].shape[1] if row6_imgs else 0

        scroll_speed_1 = base_w1 / (self.transition_duration * self.speed) if self.transition_duration > 0 else 0
        scroll_speed_2 = base_w2 / (self.transition_duration * self.speed) if self.transition_duration > 0 else 0
        scroll_speed_3 = base_w3 / (self.transition_duration * self.speed) if self.transition_duration > 0 else 0
        scroll_speed_4 = base_w4 / (self.transition_duration * self.speed) if self.transition_duration > 0 else 0
        scroll_speed_5 = base_w5 / (self.transition_duration * self.speed) if self.transition_duration > 0 else 0
        scroll_speed_6 = base_w6 / (self.transition_duration * self.speed) if self.transition_duration > 0 else 0

        req_w1 = self.width + int(scroll_speed_1 * total_frames)
        req_w2 = self.width + int(scroll_speed_2 * total_frames)
        req_w3 = self.width + int(scroll_speed_3 * total_frames)
        req_w4 = self.width + int(scroll_speed_4 * total_frames)
        req_w5 = self.width + int(scroll_speed_5 * total_frames)
        req_w6 = self.width + int(scroll_speed_6 * total_frames)

        comp_1 = build_composite_strip(row1_imgs, req_w1)
        comp_2 = build_composite_strip(row2_imgs, req_w2)
        comp_3 = build_composite_strip(row3_imgs, req_w3)
        comp_4 = build_composite_strip(row4_imgs, req_w4)
        comp_5 = build_composite_strip(row5_imgs, req_w5)
        comp_6 = build_composite_strip(row6_imgs, req_w6)
        if any(x is None for x in [comp_1, comp_2, comp_3, comp_4, comp_5, comp_6]):
            print("Error building composite strips.")
            return

        comp_w1 = comp_1.shape[1]
        comp_w2 = comp_2.shape[1]
        comp_w3 = comp_3.shape[1]
        comp_w4 = comp_4.shape[1]
        comp_w5 = comp_5.shape[1]
        comp_w6 = comp_6.shape[1]

        # --- Video Writer Setup ---
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        writer = cv2.VideoWriter(self.output_file, fourcc, self.speed, (self.width, self.height))
        writer.set(cv2.VIDEOWRITER_PROP_QUALITY, self.quality * 100)

        row_directions = [False, True, False, True, False, True] if self.opposite else [False] * 6

        def get_offset(comp_w, spd, reverse, frame_index):
            base_offset = int(frame_index * spd)
            if reverse:
                offset = comp_w - self.width - base_offset
            else:
                offset = base_offset
            return max(0, min(offset, comp_w - self.width))

        # --- Create and Write Frames ---
        for f in range(total_frames):
            off1 = get_offset(comp_w1, scroll_speed_1, row_directions[0], f)
            off2 = get_offset(comp_w2, scroll_speed_2, row_directions[1], f)
            off3 = get_offset(comp_w3, scroll_speed_3, row_directions[2], f)
            off4 = get_offset(comp_w4, scroll_speed_4, row_directions[3], f)
            off5 = get_offset(comp_w5, scroll_speed_5, row_directions[4], f)
            off6 = get_offset(comp_w6, scroll_speed_6, row_directions[5], f)

            crop_1 = comp_1[:, off1:off1 + self.width]
            crop_2 = comp_2[:, off2:off2 + self.width]
            crop_3 = comp_3[:, off3:off3 + self.width]
            crop_4 = comp_4[:, off4:off4 + self.width]
            crop_5 = comp_5[:, off5:off5 + self.width]
            crop_6 = comp_6[:, off6:off6 + self.width]

            frame_canvas = np.vstack((crop_1, crop_2, crop_3, crop_4, crop_5, crop_6))
            frame_canvas = frame_canvas[:self.height, :, :]

            if processed_text_configs:
                frame_canvas = add_text_overlays(frame_canvas, processed_text_configs)
            writer.write(frame_canvas)

        writer.release()
        print(f"Video created: {self.output_file}")
        self.attach_audio()
    
    
    ###################################################################################
    # Mode F: Combined slideshow with background frames built from two S3 folders 
    # ###################################################################################        
        
    def generate_mode_f(self):
            """
            Mode B: Combined slideshow with background frames built from two S3 folders
            (folder1 and folder2) and foreground frames (single slideshow) built from a single S3 folder.
            The background is constructed as 6 vertical rows (3 groups) and the foreground slides across,
            with optional reversed direction if self.opposite==True.
            """
            import math, random, cv2, numpy as np

            # Determine total frames
            total_frames = int(self.speed * (self.video_max_length if self.video_max_length is not None else self.duration))
            row_height = math.ceil(self.height / 6)
            transition_frames = int(self.speed * self.transition_duration)
            N_full = (total_frames - 1) // transition_frames
            remainder = (total_frames - 1) % transition_frames
            needed_images = N_full + 2 if remainder > 0 else N_full + 1

            # --- Generate Background Frames ---
            # List images from S3 for folder1 and folder2 and build a mapping by basename.
            bucket1, _ = self.s3_manager.parse_s3_path(self.folder1)
            bucket2, _ = self.s3_manager.parse_s3_path(self.folder2)
            files1 = self.s3_manager.list_images(self.folder1)
            files2 = self.s3_manager.list_images(self.folder2)
            folder1_map = {os.path.basename(f): f for f in files1}
            folder2_map = {os.path.basename(f): f for f in files2}
            common_basenames = set(folder1_map.keys()) & set(folder2_map.keys())
            common_pairs = [(folder1_map[bn], folder2_map[bn]) for bn in common_basenames]
            common_pairs.sort(key=lambda x: natural_sort_key(x[0]))
            if not common_pairs:
                print("No matching basenames found between folder1 and folder2.")
                return

            total_needed = needed_images * 3  # for 3 groups (rows 1-2, 3-4, 5-6)
            if self.random_choice:
                if len(common_pairs) < total_needed:
                    repeats = (total_needed // len(common_pairs)) + 1
                    big_list = (common_pairs * repeats)[:total_needed]
                else:
                    big_list = random.sample(common_pairs, total_needed)
            else:
                repeats = (total_needed + len(common_pairs) - 1) // len(common_pairs)
                big_list = (common_pairs * repeats)[:total_needed]

            group1 = big_list[0:needed_images]               # rows 1 & 2
            group2 = big_list[needed_images:2*needed_images]    # rows 3 & 4
            group3 = big_list[2*needed_images:3*needed_images]  # rows 5 & 6

            # Load images from S3 and resize to row height.
            def load_rows(group):
                row_img1, row_img2 = [], []
                for (p1, p2) in group:
                    img1 = self.s3_manager.read_image(bucket1, p1)
                    img2 = self.s3_manager.read_image(bucket2, p2)
                    if img1 is not None:
                        row_img1.append(resize_to_height(img1, row_height))
                    if img2 is not None:
                        row_img2.append(resize_to_height(img2, row_height))
                return row_img1, row_img2

            row1_imgs, row2_imgs = load_rows(group1)
            row3_imgs, row4_imgs = load_rows(group2)
            row5_imgs, row6_imgs = load_rows(group3)

            # Apply opposite shifts if self.opposite is True.
            if self.opposite:
                if len(row1_imgs) > 1:
                    row1_imgs = row1_imgs[-3:] + row1_imgs[:-3]
                if len(row3_imgs) > 1:
                    row3_imgs = row3_imgs[-3:] + row3_imgs[:-3]
                if len(row5_imgs) > 1:
                    row5_imgs = row5_imgs[-3:] + row5_imgs[:-3]
                row2_imgs = row2_imgs[::-1]
                row4_imgs = row4_imgs[::-1]
                row6_imgs = row6_imgs[::-1]

            def safe_width(imgs):
                return imgs[0].shape[1] if imgs else 0

            base_w1 = safe_width(row1_imgs)
            base_w2 = safe_width(row2_imgs)
            base_w3 = safe_width(row3_imgs)
            base_w4 = safe_width(row4_imgs)
            base_w5 = safe_width(row5_imgs)
            base_w6 = safe_width(row6_imgs)

            scroll_speed_1 = base_w1 / (self.transition_duration * self.speed) if self.transition_duration > 0 else 0
            scroll_speed_2 = base_w2 / (self.transition_duration * self.speed) if self.transition_duration > 0 else 0
            scroll_speed_3 = base_w3 / (self.transition_duration * self.speed) if self.transition_duration > 0 else 0
            scroll_speed_4 = base_w4 / (self.transition_duration * self.speed) if self.transition_duration > 0 else 0
            scroll_speed_5 = base_w5 / (self.transition_duration * self.speed) if self.transition_duration > 0 else 0
            scroll_speed_6 = base_w6 / (self.transition_duration * self.speed) if self.transition_duration > 0 else 0

            req_w1 = self.width + int(scroll_speed_1 * total_frames)
            req_w2 = self.width + int(scroll_speed_2 * total_frames)
            req_w3 = self.width + int(scroll_speed_3 * total_frames)
            req_w4 = self.width + int(scroll_speed_4 * total_frames)
            req_w5 = self.width + int(scroll_speed_5 * total_frames)
            req_w6 = self.width + int(scroll_speed_6 * total_frames)

            comp_1 = build_composite_strip(row1_imgs, req_w1)
            comp_2 = build_composite_strip(row2_imgs, req_w2)
            comp_3 = build_composite_strip(row3_imgs, req_w3)
            comp_4 = build_composite_strip(row4_imgs, req_w4)
            comp_5 = build_composite_strip(row5_imgs, req_w5)
            comp_6 = build_composite_strip(row6_imgs, req_w6)
            if any(x is None for x in [comp_1, comp_2, comp_3, comp_4, comp_5, comp_6]):
                print("Error building composite strips (some row had no images).")
                return

            comp_w1 = comp_1.shape[1]
            comp_w2 = comp_2.shape[1]
            comp_w3 = comp_3.shape[1]
            comp_w4 = comp_4.shape[1]
            comp_w5 = comp_5.shape[1]
            comp_w6 = comp_6.shape[1]

            bg_frames = []
            # For each frame, compute per-row offset and crop the composite strip.
            for f in range(total_frames):
                if self.opposite:
                    row_dirs = [False, True, False, True, False, True]
                else:
                    row_dirs = [False] * 6

                def get_offset(comp_w, scroll_speed, reverse):
                    if reverse:
                        off = comp_w - self.width - int(f * scroll_speed)
                        return max(0, min(off, comp_w - self.width))
                    else:
                        off = int(f * scroll_speed)
                        return max(0, min(off, comp_w - self.width))

                off_1 = get_offset(comp_w1, scroll_speed_1, row_dirs[0])
                off_2 = get_offset(comp_w2, scroll_speed_2, row_dirs[1])
                off_3 = get_offset(comp_w3, scroll_speed_3, row_dirs[2])
                off_4 = get_offset(comp_w4, scroll_speed_4, row_dirs[3])
                off_5 = get_offset(comp_w5, scroll_speed_5, row_dirs[4])
                off_6 = get_offset(comp_w6, scroll_speed_6, row_dirs[5])

                crop_1 = comp_1[:, off_1: off_1 + self.width]
                crop_2 = comp_2[:, off_2: off_2 + self.width]
                crop_3 = comp_3[:, off_3: off_3 + self.width]
                crop_4 = comp_4[:, off_4: off_4 + self.width]
                crop_5 = comp_5[:, off_5: off_5 + self.width]
                crop_6 = comp_6[:, off_6: off_6 + self.width]
                frame_bg = np.vstack((crop_1, crop_2, crop_3, crop_4, crop_5, crop_6))
                frame_bg = frame_bg[:self.height, :, :]
                bg_frames.append(frame_bg)

            # --- Generate Foreground (Single-Row) Frames ---
            # Use the single slideshow folder from S3.
            bucket_slide, _ = self.s3_manager.parse_s3_path(self.single_slideshow_folder)
            files_slide = self.s3_manager.list_images(self.single_slideshow_folder)
            all_imgs = []
            for key in files_slide:
                img = self.s3_manager.read_image(bucket_slide, key)
                if img is not None:
                    h, w = img.shape[:2]
                    if w == 0:
                        continue
                    scale = self.width / float(w)
                    new_h = int(h * scale)
                    resized = cv2.resize(img, (self.width, new_h), interpolation=cv2.INTER_AREA)
                    all_imgs.append(resized)
            if not all_imgs:
                # If no images were loaded, create a dummy black image.
                dummy = np.full((self.height, self.width, 3), (0, 0, 0), dtype=np.uint8)
                all_imgs = [dummy]

            # Determine how many images are needed for the transitions.
            if total_frames <= 1:
                fg_frames = []
            else:
                full_transitions = (total_frames - 1) // transition_frames
                remainder_frames = (total_frames - 1) % transition_frames
                needed_fg_imgs = full_transitions + 2 if remainder_frames > 0 else full_transitions + 1

                if self.random_choice:
                    if len(all_imgs) < needed_fg_imgs:
                        repeats = (needed_fg_imgs // len(all_imgs)) + 1
                        big_list = (all_imgs * repeats)[:needed_fg_imgs]
                    else:
                        big_list = random.sample(all_imgs, needed_fg_imgs)
                else:
                    repeats = (needed_fg_imgs // len(all_imgs)) + 1
                    big_list = (all_imgs * repeats)[:needed_fg_imgs]

                fg_frames = [big_list[0]]
                frames_count = 1
                finished = False
                for i in range(needed_fg_imgs - 1):
                    tf = transition_frames
                    if i == full_transitions and remainder_frames > 0:
                        tf = remainder_frames
                    for t in range(tf):
                        if frames_count >= total_frames:
                            finished = True
                            break
                        progress = (t + 1) / float(transition_frames)
                        current = big_list[i]
                        nxt = big_list[i + 1]
                        ch, cw = current.shape[:2]
                        nh, nw = nxt.shape[:2]
                        max_h = max(ch, nh)
                        # Create canvases for both current and next with background canvas color = black.
                        can1 = np.full((max_h, self.width, 3), 0, dtype=np.uint8)
                        can2 = can1.copy()
                        top_off_1 = (max_h - ch) // 2
                        can1[top_off_1:top_off_1 + ch, 0:self.width] = current
                        top_off_2 = (max_h - nh) // 2
                        can2[top_off_2:top_off_2 + nh, 0:self.width] = nxt
                        # create_transition_frame is assumed to generate a blended frame from can1 to can2.
                        slide = self.create_transition_frame(can1, can2,  progress)
                        fg_frames.append(slide)
                        frames_count += 1
                    if finished:
                        break

            # Ensure the number of foreground frames matches the number of background frames.
            total_bg_frames = len(bg_frames)
            if not fg_frames:
                dummy = np.full((self.height, self.width, 3), 0, dtype=np.uint8)
                fg_frames = [dummy] * total_bg_frames
            if len(fg_frames) < total_bg_frames:
                idx = 0
                while len(fg_frames) < total_bg_frames:
                    fg_frames.append(fg_frames[idx % len(fg_frames)])
                    idx += 1
            elif len(fg_frames) > total_bg_frames:
                fg_frames = fg_frames[:total_bg_frames]

            # --- Composite Final Frames ---
            final_frames = []
            # Use self.text_configs (already prepared in __init__) for overlay text.
            for i in range(total_bg_frames):
                bg = bg_frames[i].copy()
                fg = fg_frames[i]
                fg_h, fg_w = fg.shape[:2]
                y_offset = (self.height - fg_h) // 2
                if y_offset + fg_h <= self.height:
                    bg[y_offset:y_offset + fg_h, 0:fg_w] = fg
                else:
                    region = bg[y_offset:self.height, 0:fg_w]
                    region_h = region.shape[0]
                    if region_h > 0:
                        bg[y_offset:y_offset + region_h, 0:fg_w] = fg[:region_h, :, :]
                out_frame = add_text_overlays(bg, self.text_configs)
                final_frames.append(out_frame)

            # --- Write the Video ---
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            writer = cv2.VideoWriter(self.output_file, fourcc, self.speed, (self.width, self.height))
            writer.set(cv2.VIDEOWRITER_PROP_QUALITY, self.quality * 100)
            for frame in final_frames:
                writer.write(frame)
            writer.release()
            print(f"Video created: {self.output_file}")
            self.attach_audio() 
            
    ###################################################################################
    # Mode G: Two-Folder Implementation
    ###################################################################################
            

    def generate_mode_g(self):
        """
        Mode C: Two-Folder Implementation that:
        1) Renders 6 normal rows filling the entire frame height (with no black bars).
        2) Overlays rows 3 & 4 as enlarged layers (fully visible, may overlap rows 2 or 5).
        3) If opposite=True, rows 3 & 4 (normal and enlarged) scroll in the reverse direction.
        """

        # Validate and parse the S3 folders
        bucket1, _ = self.s3_manager.parse_s3_path(self.folder1)
        bucket2, _ = self.s3_manager.parse_s3_path(self.folder2)

        processed_text_configs = self.text_configs

        # Determine total number of frames for the video
        if self.video_max_length is not None:
            total_frames = int(self.speed * self.video_max_length)
        else:
            total_frames = int(self.speed * self.duration)

        # Determine the number of image pairs needed; a transition uses several frames.
        transition_frames = int(self.speed * self.transition_duration)
        N_full = (total_frames - 1) // transition_frames
        remainder = (total_frames - 1) % transition_frames
        needed_images = N_full + 2 if remainder > 0 else N_full + 1

        # Collect matching images from both S3 folders based on common basenames
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

        # Select enough pairs for 3 groups (rows 1&2, rows 3&4, rows 5&6)
        total_needed = needed_images * 3
        if self.random_choice:
            if len(common_pairs) < total_needed:
                print(f"Need {total_needed} common images, found {len(common_pairs)}.")
                return
            selected_pairs = random.sample(common_pairs, total_needed)
        else:
            repeats = (total_needed + len(common_pairs) - 1) // len(common_pairs)
            selected_pairs = (common_pairs * repeats)[:total_needed]

        group1 = selected_pairs[:needed_images]               # For rows 1 & 2
        group2 = selected_pairs[needed_images:needed_images*2]  # For rows 3 & 4
        group3 = selected_pairs[needed_images*2:needed_images*3]# For rows 5 & 6

        # Compute row heights so that 6 rows fill the frame exactly
        normal_row_height = self.height // 6
        used_for_first_5 = normal_row_height * 5
        last_row_height = self.height - used_for_first_5

        # For rows 3 and 4, create enlarged versions (by 30%)
        enlarged_height = int(round(normal_row_height * 1.3))

        # ---- Create image lists for each row using S3 images ----
        # Rows 1 & 2 (normal rows)
        row1_imgs, row2_imgs = [], []
        for pair in group1:
            img1 = self.s3_manager.read_image(bucket1, pair[0])
            img2 = self.s3_manager.read_image(bucket2, pair[1])
            if img1 is not None:
                row1_imgs.append(resize_to_height(img1, normal_row_height))
            if img2 is not None:
                row2_imgs.append(resize_to_height(img2, normal_row_height))
        
        # Rows 3 & 4: normal and enlarged versions
        row3_imgs, row4_imgs = [], []
        row3_imgs_enlarged, row4_imgs_enlarged = [], []
        for pair in group2:
            img1 = self.s3_manager.read_image(bucket1, pair[0])
            img2 = self.s3_manager.read_image(bucket2, pair[1])
            if img1 is not None:
                row3_imgs.append(resize_to_height(img1, normal_row_height))
                row3_imgs_enlarged.append(resize_to_height(img1, enlarged_height))
            if img2 is not None:
                row4_imgs.append(resize_to_height(img2, normal_row_height))
                row4_imgs_enlarged.append(resize_to_height(img2, enlarged_height))
        
        # Rows 5 & 6 (normal rows)
        row5_imgs, row6_imgs = [], []
        for pair in group3:
            img1 = self.s3_manager.read_image(bucket1, pair[0])
            img2 = self.s3_manager.read_image(bucket2, pair[1])
            if img1 is not None:
                row5_imgs.append(resize_to_height(img1, normal_row_height))
            if img2 is not None:
                row6_imgs.append(resize_to_height(img2, last_row_height))

        # ---- Build composite strips for scrolling ----
        def build_strip_and_speed(imgs):
            """
            Builds a composite strip from a list of images wide enough for the entire scrolling duration.
            Returns the composite image and its horizontal scroll speed (pixels/frame).
            """
            if not imgs:
                return None, 0
            base_w = imgs[0].shape[1]
            spd = base_w / (self.transition_duration * self.speed) if self.transition_duration > 0 else 0
            required_w = self.width + int(spd * total_frames)
            comp = build_composite_strip(imgs, required_w)
            return comp, spd

        # Normal row composites
        c1, spd1 = build_strip_and_speed(row1_imgs)
        c2, spd2 = build_strip_and_speed(row2_imgs)
        c3, spd3_normal = build_strip_and_speed(row3_imgs)
        c4, spd4_normal = build_strip_and_speed(row4_imgs)
        c5, spd5 = build_strip_and_speed(row5_imgs)
        c6, spd6 = build_strip_and_speed(row6_imgs)
        # Enlarged composites for rows 3 & 4
        c3e, spd3e_normal = build_strip_and_speed(row3_imgs_enlarged)
        c4e, spd4e_normal = build_strip_and_speed(row4_imgs_enlarged)

        if any(x is None for x in [c1, c2, c3, c4, c5, c6, c3e, c4e]):
            print("Error: Could not build composite strips for all rows.")
            return

        # Adjust speeds for rows 3 & 4 if opposite is True (both normal and enlarged)
        if self.opposite:
            spd3 = -spd3_normal
            spd4 = -spd4_normal
            spd3e = -spd3e_normal
            spd4e = -spd4e_normal
        else:
            spd3 = spd3_normal
            spd4 = spd4_normal
            spd3e = spd3e_normal
            spd4e = spd4e_normal

        # Compute vertical positions for the normal rows
        y1_top = 0
        y2_top = y1_top + normal_row_height
        y3_top = y2_top + normal_row_height
        y4_top = y3_top + normal_row_height
        y5_top = y4_top + normal_row_height
        y6_top = y5_top + normal_row_height  # row6 fills the remainder

        # Compute positions for the enlarged rows (rows 3 & 4 overlays)
        combined_enlarged_height = 2 * enlarged_height
        vertical_center = self.height // 2
        row3_enlarged_top = vertical_center - combined_enlarged_height // 2
        if row3_enlarged_top < 0:
            row3_enlarged_top = 0
        elif row3_enlarged_top + combined_enlarged_height > self.height:
            row3_enlarged_top = self.height - combined_enlarged_height
        row4_enlarged_top = row3_enlarged_top + enlarged_height
        row3_enlarged_top = max(0, min(row3_enlarged_top, self.height - enlarged_height))
        row4_enlarged_top = max(0, min(row4_enlarged_top, self.height - enlarged_height))
        if row3_enlarged_top + enlarged_height > self.height:
            row3_enlarged_top = self.height - enlarged_height
        if row4_enlarged_top + enlarged_height > self.height:
            row4_enlarged_top = self.height - enlarged_height

        # Prepare the video writer
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(self.output_file, fourcc, self.speed, (self.width, self.height))
        out.set(cv2.VIDEOWRITER_PROP_QUALITY, self.quality * 100)

        # Helper function to compute horizontal offset for a given frame
        def get_offset(frame_idx, spd, comp_w):
            x_off = int(frame_idx * spd)
            if spd >= 0:
                return max(0, min(x_off, comp_w - self.width))
            else:
                start_max = comp_w - self.width
                pos = start_max - abs(x_off)
                return max(0, min(pos, start_max))

        # Create and write each frame
        for f in range(total_frames):
            # Compute offsets for normal composites
            off1 = get_offset(f, spd1, c1.shape[1])
            off2 = get_offset(f, spd2, c2.shape[1])
            off3 = get_offset(f, spd3, c3.shape[1])
            off4 = get_offset(f, spd4, c4.shape[1])
            off5 = get_offset(f, spd5, c5.shape[1])
            off6 = get_offset(f, spd6, c6.shape[1])
            # Offsets for enlarged composites
            off3e = get_offset(f, spd3e, c3e.shape[1])
            off4e = get_offset(f, spd4e, c4e.shape[1])
            
            # Crop normal rows from composites
            row1_crop = c1[:, off1: off1 + self.width]
            row2_crop = c2[:, off2: off2 + self.width]
            row3_crop = c3[:, off3: off3 + self.width]
            row4_crop = c4[:, off4: off4 + self.width]
            row5_crop = c5[:, off5: off5 + self.width]
            row6_crop = c6[:, off6: off6 + self.width]
            # Crop enlarged rows
            row3e_crop = c3e[:, off3e: off3e + self.width]
            row4e_crop = c4e[:, off4e: off4e + self.width]
            
            # Create a blank canvas and place the normal rows
            frame_canvas = np.zeros((self.height, self.width, 3), dtype=np.uint8)
            frame_canvas[y1_top: y1_top + normal_row_height] = row1_crop
            frame_canvas[y2_top: y2_top + normal_row_height] = row2_crop
            frame_canvas[y3_top: y3_top + normal_row_height] = row3_crop
            frame_canvas[y4_top: y4_top + normal_row_height] = row4_crop
            frame_canvas[y5_top: y5_top + normal_row_height] = row5_crop
            frame_canvas[y6_top: y6_top + (self.height - y5_top)] = row6_crop

            # Overlay the enlarged rows
            # First overlay row4 enlarged, then row3 enlarged (so row3 appears on top)
            row4e_bottom = row4_enlarged_top + row4e_crop.shape[0]
            frame_canvas[row4_enlarged_top: row4e_bottom, :row4e_crop.shape[1]] = row4e_crop
            row3e_bottom = row3_enlarged_top + row3e_crop.shape[0]
            frame_canvas[row3_enlarged_top: row3e_bottom, :row3e_crop.shape[1]] = row3e_crop

            # Apply text overlays if configured
            if processed_text_configs:
                frame_canvas = add_text_overlays(frame_canvas, processed_text_configs)

            out.write(frame_canvas)

        out.release()
        print(f"Video created: {self.output_file}")
        self.attach_audio() 
        
         ###################################################################################
    # Mode D: Two-Folder Implementation with 4 rows (2x2) and scrolling
    
    ###################################################################################


    def generate_mode_h(self):
        
        bucket1, _ = self.s3_manager.parse_s3_path(self.folder1)
        bucket2, _ = self.s3_manager.parse_s3_path(self.folder2)
        processed_text_configs = self.text_configs
        row_height = self.height // 4
        total_frames = int(self.speed * (self.video_max_length if self.video_max_length is not None else self.duration))
        transition_frames = int(self.speed * self.transition_duration)
        N_full = (total_frames - 1) // transition_frames
        remainder = (total_frames - 1) % transition_frames
        needed_images = N_full + 2 if remainder > 0 else N_full + 1

        folder1_keys = self.s3_manager.list_images(self.folder1)
        folder2_keys = self.s3_manager.list_images(self.folder2)
        folder1_map = {os.path.basename(k): k for k in folder1_keys}
        folder2_map = {os.path.basename(k): k for k in folder2_keys}
        common_pairs = []
        for bn in set(folder1_map.keys()) & set(folder2_map.keys()):
            common_pairs.append((folder1_map[bn], folder2_map[bn]))
        common_pairs.sort(key=lambda x: natural_sort_key(x[0]))
        if not common_pairs:
            print("No common images found between the two folders for mode D.")
            return

        if self.random_choice:
            if len(common_pairs) < needed_images * 2:
                print(f"Need {needed_images * 2} common images, found {len(common_pairs)}.")
                return
            selected_pairs = random.sample(common_pairs, needed_images * 2)
            top_pairs = selected_pairs[:needed_images]
            bottom_pairs = selected_pairs[needed_images:needed_images * 2]
        else:
            total_needed = needed_images * 2
            repeats = (total_needed + len(common_pairs) - 1) // len(common_pairs)
            selected_pairs = (common_pairs * repeats)[:total_needed]
            top_pairs = selected_pairs[:needed_images]
            bottom_pairs = selected_pairs[needed_images:total_needed]

        def load_pair(pair):
            key1, key2 = pair
            img1 = self.s3_manager.read_image(bucket1, key1)
            img2 = self.s3_manager.read_image(bucket2, key2)
            return img1, img2

        row1_imgs, row2_imgs = [], []
        for pair in top_pairs:
            img1, img2 = load_pair(pair)
            if img1 is not None:
                row1_imgs.append(resize_to_height(img1, row_height))
            if img2 is not None:
                row2_imgs.append(resize_to_height(img2, row_height))
        row3_imgs, row4_imgs = [], []
        for pair in bottom_pairs:
            img1, img2 = load_pair(pair)
            if img1 is not None:
                row3_imgs.append(resize_to_height(img1, row_height))
            if img2 is not None:
                row4_imgs.append(resize_to_height(img2, row_height))
        if self.opposite:
            if len(row1_imgs) > 1:
                row1_imgs = row1_imgs[-2:] + row1_imgs[:-2]
            if len(row3_imgs) > 1:
                row3_imgs = row3_imgs[-2:] + row3_imgs[:-2]
            row2_imgs = row2_imgs[::-1]
            row4_imgs = row4_imgs[::-1]

        base_w1 = row1_imgs[0].shape[1] if row1_imgs else 0
        base_w2 = row2_imgs[0].shape[1] if row2_imgs else 0
        base_w3 = row3_imgs[0].shape[1] if row3_imgs else 0
        base_w4 = row4_imgs[0].shape[1] if row4_imgs else 0

        scroll_speed_1 = base_w1 / (self.transition_duration * self.speed)
        scroll_speed_2 = base_w2 / (self.transition_duration * self.speed)
        scroll_speed_3 = base_w3 / (self.transition_duration * self.speed)
        scroll_speed_4 = base_w4 / (self.transition_duration * self.speed)

        req_w1 = self.width + int(scroll_speed_1 * total_frames)
        req_w2 = self.width + int(scroll_speed_2 * total_frames)
        req_w3 = self.width + int(scroll_speed_3 * total_frames)
        req_w4 = self.width + int(scroll_speed_4 * total_frames)

        comp_1 = build_composite_strip(row1_imgs, req_w1)
        comp_2 = build_composite_strip(row2_imgs, req_w2)
        comp_3 = build_composite_strip(row3_imgs, req_w3)
        comp_4 = build_composite_strip(row4_imgs, req_w4)
        if any(x is None for x in [comp_1, comp_2, comp_3, comp_4]):
            print("Error building composite strips for mode D.")
            return

        comp_w1 = comp_1.shape[1]
        comp_w2 = comp_2.shape[1]
        comp_w3 = comp_3.shape[1]
        comp_w4 = comp_4.shape[1]

        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(self.output_file, fourcc, self.speed, (self.width, self.height))
        out.set(cv2.VIDEOWRITER_PROP_QUALITY, self.quality * 100)

        for f in range(total_frames):
            row_directions = [False, True, False, True] if self.opposite else [False] * 4
            base_offset_1 = int(f * scroll_speed_1)
            offset_1 = comp_w1 - self.width - base_offset_1 if row_directions[0] else base_offset_1
            offset_1 = max(0, min(offset_1, comp_w1 - self.width))
            crop_1 = comp_1[:, offset_1:offset_1 + self.width]
            base_offset_2 = int(f * scroll_speed_2)
            offset_2 = comp_w2 - self.width - base_offset_2 if row_directions[1] else base_offset_2
            offset_2 = max(0, min(offset_2, comp_w2 - self.width))
            crop_2 = comp_2[:, offset_2:offset_2 + self.width]
            base_offset_3 = int(f * scroll_speed_3)
            offset_3 = comp_w3 - self.width - base_offset_3 if row_directions[2] else base_offset_3
            offset_3 = max(0, min(offset_3, comp_w3 - self.width))
            crop_3 = comp_3[:, offset_3:offset_3 + self.width]
            base_offset_4 = int(f * scroll_speed_4)
            offset_4 = comp_w4 - self.width - base_offset_4 if row_directions[3] else base_offset_4
            offset_4 = max(0, min(offset_4, comp_w4 - self.width))
            crop_4 = comp_4[:, offset_4:offset_4 + self.width]
            composite_frame = (crop_1, crop_2, crop_3, crop_4)
            composite_frame = np.vstack((crop_1, crop_2, crop_3, crop_4))
            if processed_text_configs:
                composite_frame = add_text_overlays(composite_frame, processed_text_configs)
            out.write(composite_frame)
        out.release()
        print(f"Video created: {self.output_file}")
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
        elif mode == 'e':
            self.generate_mode_e()
        elif mode == 'f':
            self.generate_mode_f()
        elif mode == 'g':
            self.generate_mode_g()
        elif mode == 'h':
            self.generate_mode_h()
        else:
            raise ValueError(f"Invalid mode '{mode}' selected.")
         
        return self.upload_video()
        
            
    def upload_video(self):
        return self.s3_manager.upload_file(
            self.output_file, self.s3_video_bucket, self.s3_video_key
        )
        
        
    def create_transition_frame(self, img1, img2, progress):
        """
        Creates a sliding transition frame between img1 and img2.
        Uses a fixed black canvas and class-level width and direction.

        Args:
            img1 (np.ndarray): Current image frame.
            img2 (np.ndarray): Next image frame.
            progress (float): Transition progress (0.0 to 1.0).

        Returns:
            np.ndarray: Transition frame.
        """
        width = self.width
        height = max(img1.shape[0], img2.shape[0])
        shift = int(progress * width)

        # Fixed black canvas
        frame = np.full((height, width, 3), (0, 0, 0), dtype=img1.dtype)

        if not self.opposite:
            frame[:, :width - shift] = img1[:, shift:width]
            frame[:, width - shift:] = img2[:, :shift]
        else:
            frame[:, shift:] = img1[:, :width - shift]
            frame[:, :shift] = img2[:, width - shift:]

        return frame
    
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