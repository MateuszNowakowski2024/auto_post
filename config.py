import random

###############################
# Parameter Setting
###############################

# S3 paths
FOLDER1 = "s3://lily-images/reels/cartoon_images"
FOLDER2 = "s3://lily-images/reels/outline_images"
S3_VIDEO_BUCKET = "lily-images"
S3_VIDEO_KEY = "videos/production_video.mp4"
SINGLE_SLIDESHOW_FOLDER = "s3://lily-images/pages"
# Local paths
OUTPUT_FILE = "auto_post_reels/temp/temp_video.mp4"
AUDIO_PATH = "auto_post_reels/reel_sounds"
FONT_PATH = "auto_post_reels/reel_fonts/SuperCaramel-5yBza.ttf"

# Video settings
WIDTH = 720
HEIGHT = 1280
SPEED = 40         #fps
QUALITY = 75
VIDEO_MAX_LENGTH = 20
DURATION = 40
TRANSITION_DURATION = 2
RANDOM_CHOICE = True
MODE =  random.choice(['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h'])
OPPOSITE = random.choice([True, False])      # set in main randomly

# Text overlay configurations
TEXT_CONFIGS = [
    {
        'content': "Happy Coloring! Link in Bio!",
        'font_path': FONT_PATH,
        'font_size': 60,
        'color_hex': "#fffbed",
        'bg_color_hex': "#5a006b",
        'y': 170,
        'box_width': 520,
        'padding': 5,
        'corner_radius': 25
    },
    {
        'content': "Check Our Website. lily10coloringbooks.fun",
        'font_path': FONT_PATH,
        'font_size': 55,
        'color_hex': "#fffbed",
        'bg_color_hex': "#5a006b",
        'y': 1150,
        'box_width': 680,
        'padding': 5,
        'corner_radius': 25
    }
]

