import os
import random
import json
from urllib.parse import urlparse
import boto3
from openai import OpenAI

# Set your OpenAI API key from an environment variable or directly.
client = OpenAI(
    api_key=os.environ.get('OPENAI_API_KEY'),
)

URL_FILE = "url.json"

def load_posted_urls(file_path):
    """
    Loads the list of previously posted image URLs from a JSON file.
    If the file doesn't exist or is empty, returns an empty list.
    """
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
        except json.JSONDecodeError:
            return []
    return []

def save_posted_urls(file_path, urls):
    """
    Saves the list of posted image URLs to a JSON file.
    """
    with open(file_path, 'w') as f:
        json.dump(urls, f)

def get_random_image_url(bucket_name, folder_prefix, posted_urls=None):
    """
    Lists objects in the specified S3 bucket folder and returns a random image URL 
    that has not been posted before (if posted_urls is provided).
    """
    s3 = boto3.client('s3')
    response = s3.list_objects_v2(Bucket=bucket_name, Prefix=folder_prefix)
    objects = response.get('Contents', [])
    if not objects:
        raise Exception("No objects found in the specified bucket folder.")
    
    # Build a list of full URLs that have not been posted yet.
    new_urls = []
    for obj in objects:
        key = obj['Key']
        url = f"https://{bucket_name}.s3.amazonaws.com/{key}"
        if posted_urls is None or url not in posted_urls:
            new_urls.append(url)
    
    if not new_urls:
        raise Exception("No new images found that haven't been posted yet.")
    
    # Randomly select one URL from the list of new URLs.
    return random.choice(new_urls)

def extract_filename(image_url):
    """
    Extracts the filename from the full image URL.
    """
    parsed_url = urlparse(image_url)
    filename = os.path.basename(parsed_url.path)
    return filename

def get_book_name_from_filename(filename):
    """
    Calls ChatGPT to extract the book name from the filename.
    The book name is assumed to be the portion before the word "book".
    For example, given "10_magic_dragons_book_a_bright_dragon.jpeg", it should return "Magic Dragons".
    """
    prompt = (
        f"Extract the book name from the following filename. "
        f"The book name is the portion before the word 'book'. Ignore any numerical prefixes and underscores, "
        f"and return the name in title case. Filename: '{filename}'.\n"
        "Provide only the book name."
    )
    
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0,
        messages=[
            {"role": "system", "content": "You are a helpful assistant that extracts book names from filenames."},
            {"role": "user", "content": prompt}
        ]
    )
    book_name = response.choices[0].message.content.strip()
    return book_name

def get_image_description_from_filename(filename):
    """
    Calls ChatGPT to extract the image description from the filename.
    The description is assumed to be the portion after the word "book".
    For example, given "pages/10_magic_dragons_book_a_bright_citrineyellow_dragon_with_orange_highligh.jpeg", 
    it should return "a_bright_citrineyellow_dragon_with_orange_highligh".
    """
    prompt = (
        f"Extract the image description from the following filename. "
        f"The description is the portion after the word 'book'. Do not include the file extension. "
        f"Filename: '{filename}'.\n"
        "Provide only the image description exactly as it appears."
    )
    
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0,
        messages=[
            {"role": "system", "content": "You are a helpful assistant that extracts image descriptions from filenames."},
            {"role": "user", "content": prompt}
        ]
    )
    description = response.choices[0].message.content.strip()
    return description

def generate_instagram_post(book_name, image_description):
    """
    Uses ChatGPT to dynamically generate an Instagram post for the new coloring book.
    The post will reference the book name and the image description extracted from the filename.
    It will be creative and include hashtags, emojis, and a call-to-action.
    """
    prompt = (
        f"Create an engaging Instagram post to introduce my new coloring book '{book_name}'. "
        f"The featured image shows {image_description}. "
        "The post should be creative, include relevant hashtags and emojis, mention that the book is available on Amazon, "
        "and ask followers to comment on what book theme they'd like to see next. "
        "Include the hashtag #lily_one_zero in the post."
    )
    
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.7,
        messages=[
            {"role": "system", "content": "You are a creative copywriter skilled in generating engaging social media content."},
            {"role": "user", "content": prompt}
        ]
    )
    
    post_content = response.choices[0].message.content.strip()
    return post_content

def main():
    bucket_name = "lily-images"
    folder_prefix = "pages/"  # e.g., "coloring-books/"
    
    # Load list of already posted URLs.
    posted_urls = load_posted_urls(URL_FILE)
    
    # Step 1: Retrieve a random new image URL from the S3 bucket folder.
    image_url = get_random_image_url(bucket_name, folder_prefix, posted_urls)
    
    # Save the new image URL into the JSON file to prevent future duplicates.
    posted_urls.append(image_url)
    save_posted_urls(URL_FILE, posted_urls)
    
    # Step 2: Extract the filename from the image URL.
    filename = extract_filename(image_url)
    
    # Step 3: Retrieve the book name from the filename via ChatGPT.
    book_name = get_book_name_from_filename(filename)
    
    # Step 4: Retrieve the image description from the filename via ChatGPT.
    image_description = get_image_description_from_filename(filename)
    
    # Step 5: Dynamically generate the Instagram post using ChatGPT.
    post = generate_instagram_post(book_name, image_description)
    
    # Final outcome: Print and return the post text and full image URL.
    print("Instagram Post:")
    print(post)
    print("\nImage URL:")
    print(image_url)
    
    return post, image_url

if __name__ == "__main__":
    main()