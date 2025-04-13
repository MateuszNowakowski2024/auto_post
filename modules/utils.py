import os
import re
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

##############################
# --- Common Helper Functions ---
##############################

def natural_sort_key(s):
    """Splits the string into alphanumeric chunks for natural sorting."""
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', os.path.basename(s))]

def hex_to_rgb(hex_color):
    """Converts a hex string (e.g. "#RRGGBB") to an RGB tuple."""
    hex_color = hex_color.lstrip('#')
    if len(hex_color) not in (6, 8):
        raise ValueError("Invalid hex color format (must be 6 or 8 digits)")
    return tuple(int(hex_color[i:i+2], 16) for i in range(0, len(hex_color), 2))

def resize_to_height(image, target_height):
    """Resizes an image to a given height while preserving aspect ratio."""
    if image is None:
        return None
    original_height, original_width = image.shape[:2]
    scale = target_height / original_height
    new_width = int(original_width * scale)
    return cv2.resize(image, (new_width, target_height), interpolation=cv2.INTER_AREA)

def wrap_text(text, font, max_width):
    """Wraps text so that no line exceeds max_width."""
    lines = []
    if max_width <= 0 or not text:
        return lines
    paragraphs = text.split('\n')
    for para in paragraphs:
        words = para.split()
        if not words:
            lines.append('')
            continue
        current_line = []
        current_length = 0
        for word in words:
            word_length = font.getlength(word + ' ')
            if current_line and current_length + word_length > max_width:
                lines.append(' '.join(current_line))
                current_line = [word]
                current_length = font.getlength(word + ' ')
            else:
                current_line.append(word)
                current_length += word_length
        if current_line:
            lines.append(' '.join(current_line))
    return lines

def add_text_overlays(frame, processed_text_configs):
    """Adds text overlays (with optional background rectangles) onto the frame."""
    img_pil = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(img_pil)
    for config in processed_text_configs:
        if config['bg_color']:
            draw.rounded_rectangle(
                config['bg_coords'],
                radius=config['corner_radius'],
                fill=config['bg_color']
            )
        x_pos, y_pos = config['position']
        box_width = config['box_width']
        for idx, line in enumerate(config['wrapped_lines']):
            line_width = config['font'].getlength(line)
            line_x = x_pos + (box_width - line_width) // 2
            current_y = y_pos + idx * config['line_height'] - config['ascent']
            draw.text((line_x, current_y), line, font=config['font'], fill=config['color'])
    return cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)

def prepare_text_configs(text_configs, canvas_width):
    """
    Processes text configuration dictionaries:
      - Loads fonts, converts hex colors, and wraps text.
      - Returns a list of processed configuration dictionaries.
    """
    processed = []
    for config in text_configs:
        content = config.get('content', '').strip()
        if not content:
            continue
        font_path = config.get('font_path', '')
        font_size = config.get('font_size', 12)
        color_hex = config.get('color_hex', '#FFFFFF')
        bg_color_hex = config.get('bg_color_hex', None)
        y = config.get('y', 0)
        box_width = config.get('box_width', canvas_width)
        padding = config.get('padding', 0)
        corner_radius = config.get('corner_radius', 0)
        
        if not os.path.exists(font_path):
            continue
        try:
            font = ImageFont.truetype(font_path, font_size)
        except Exception:
            continue
        
        try:
            color = hex_to_rgb(color_hex)
        except:
            color = (255, 255, 255)
        
        bg_color = None
        if bg_color_hex:
            try:
                bg_color = hex_to_rgb(bg_color_hex)
                if len(bg_color) == 4:
                    bg_color = bg_color[:3]
            except:
                pass
        
        wrapped_lines = wrap_text(content, font, box_width)
        if not wrapped_lines:
            continue
        
        ascent, descent = font.getmetrics()
        line_height = ascent + descent
        total_text_height = len(wrapped_lines) * line_height
        x = (canvas_width - box_width) // 2
        bg_left = x - padding
        bg_top = y - ascent - padding
        bg_right = x + box_width + padding
        bg_bottom = y + total_text_height - descent + padding - 40
        
        processed.append({
            'wrapped_lines': wrapped_lines,
            'font': font,
            'color': color,
            'bg_color': bg_color,
            'position': (x, y),
            'bg_coords': (bg_left, bg_top, bg_right, bg_bottom),
            'corner_radius': corner_radius,
            'line_height': line_height,
            'ascent': ascent,
            'box_width': box_width
        })
    return processed

def resize_to_width(image, target_width):
    """Resizes an image to the given width while maintaining aspect ratio."""
    original_height, original_width = image.shape[:2]
    scale = target_width / float(original_width)
    new_height = int(original_height * scale)
    return cv2.resize(image, (target_width, new_height), interpolation=cv2.INTER_AREA)

def resize_to_square(image, size):
    """Resizes an image to a square of given size."""
    return cv2.resize(image, (size, size), interpolation=cv2.INTER_AREA)

'''def build_composite_strip_vertical(image_list, required_height):
    """
    Builds a tall composite image by stacking images vertically until the total height >= required_height.
    (Used for mode a.)
    """
    if not image_list:
        return None
    composite = image_list[0]
    idx = 1
    while composite.shape[0] < required_height:
        next_img = image_list[idx % len(image_list)]
        composite = np.vstack((composite, next_img))
        idx += 1
    return composite'''

def build_composite_column(image_list, required_height):
    """
    Builds a composite column by stacking images vertically until the total height >= required_height.
    (Used for modes b, c, and d.)
    """
    if not image_list:
        return None
    composite = image_list[0]
    idx = 1
    while composite.shape[0] < required_height:
        next_img = image_list[idx % len(image_list)]
        composite = np.vstack((composite, next_img))
        idx += 1
    return composite

def build_composite_strip(image_list, required_width):
    if not image_list:
        return None
    composite = image_list[0]
    idx = 1
    while composite.shape[1] < required_width:
        next_img = image_list[idx % len(image_list)]
        composite = np.hstack((composite, next_img))
        idx += 1
    return composite

def generate_video_writer(output_file, width, height, quality, fps):
    """Creates and returns a cv2.VideoWriter for the final video."""
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    writer = cv2.VideoWriter(output_file, fourcc, fps, (width, height))
    writer.set(cv2.VIDEOWRITER_PROP_QUALITY, quality * 100)
    return writer
