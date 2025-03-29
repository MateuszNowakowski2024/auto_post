import os
from config import *
from modules import SlideshowGenerator, FacebookStory, InstaStory
from dotenv import load_dotenv
load_dotenv()

def main():
    # Generate video using your SlideshowGenerator
    generator = SlideshowGenerator(
        WIDTH, HEIGHT, SPEED, QUALITY, TEXT_CONFIGS, AUDIO_PATH,
        FOLDER1, FOLDER2, OUTPUT_FILE, RANDOM_CHOICE, OPPOSITE,
        DURATION, VIDEO_MAX_LENGTH, TRANSITION_DURATION,
        S3_VIDEO_BUCKET, S3_VIDEO_KEY
    )

    video_url = generator.generate_slideshow(MODE)
    os.remove(OUTPUT_FILE)
    print(f"Mode: {MODE}, Opposite: {OPPOSITE}, URL: {video_url}")

    caption = "Happy Coloring! Check us out: lily10coloringbooks.fun"

    # Initialize publishers
    ig = InstaStory()
    fb = FacebookStory()

    # --- Facebook Story ---
    fb_story_video_id, fb_story_upload_url = fb.init_story_upload()
    if fb.upload_story_video(fb_story_upload_url, video_url):
        success, post_id = fb.publish_story(fb_story_video_id)
        print("Facebook Story published:", success, post_id)
    else:
        print("Facebook Story upload failed")

    # --- Instagram Story ---
    insta_story_media_id = ig.publish_story(video_url)
    if insta_story_media_id:
        print("Instagram Story published, Media ID:", insta_story_media_id)
    else:
        print("Instagram Story failed")

    # --- Facebook Reel ---
    fb_reel_video_id, fb_reel_upload_url = fb.init_reel_upload()
    if fb.upload_reel_video(fb_reel_upload_url, video_url):
        success, post_id = fb.publish_reel(fb_reel_video_id, caption)
        print("Facebook Reel published:", success, post_id)
    else:
        print("Facebook Reel upload failed")

    # --- Instagram Reel ---
    insta_reel_media_id = ig.publish_reel(video_url, caption)
    if insta_reel_media_id:
        print("Instagram Reel published, Media ID:", insta_reel_media_id)
    else:
        print("Instagram Reel failed")

if __name__ == "__main__":
    main()