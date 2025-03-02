import os
import random
import json
from urllib.parse import urlparse
import boto3
import openai

# Set your OpenAI API key from an environment variable or directly.
openai.api_key = os.getenv("OPENAI_API_KEY")

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
    Calls ChatGPT to extract the coloring book name from the filename.
    The book name is assumed to be contained in the first one or two words of the filename.
    """
    # Remove file extension.
    name_part = os.path.splitext(filename)[0]
    prompt = (
        f"Extract the coloring book name from the following filename. "
        f"The coloring book name is contained in the first one or two words: '{name_part}'. "
        "Provide only the book name."
    )
    
    response = openai.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0,
        messages=[
            {"role": "system", "content": "You are a helpful assistant that extracts book names from filenames."},
            {"role": "user", "content": prompt}
        ]
    )
    book_name = response.choices[0].message.content.strip()
    return book_name

def generate_instagram_post(book_name, filename):
    """
    Dynamically generates an Instagram post using ChatGPT.
    It includes hashtags, emojis, and a call-to-action.
    If the filename contains 'kids', the prompt instructs GPT to advertise the book
    as perfect for the youngest artists (avoiding the word 'kid').
    """
    is_for_kids = "kids" in filename.lower()
    
    if is_for_kids:
        prompt = (
            f"Create an engaging Instagram post to advertise a coloring book named '{book_name}'. "
            "The post should be creative, include relevant hashtags and emojis, and advertise the book "
            "as a perfect coloring book for the youngest artists. Do not use the word 'kid' in the description. "
            "Also, ask followers to comment on what book theme they'd like to see next."
            "Encourage users to visit our website lily10coloringbooks.fun Link in the Bio!"
            "include #lily_one_zero in the hashtags"
        )
    else:
        prompt = (
            f"Create an engaging Instagram post to advertise a coloring book named '{book_name}'. "
            "The post should be creative, include relevant hashtags and emojis, advise users to visit our website (link in Bio and Comments), "
            "mention that the book is available on Amazon now, and ask followers to comment on what book theme they'd like to see next."
            "Encourage users to visit our website lily10coloringbooks.fun Link in the Bio!"
            "include #lily_one_zero in the hashtags"
        )
    
    response = openai.chat.completions.create(
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
    folder_prefix = "covers/"  # e.g., "coloring-books/"
    
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
    
    # Step 4: Dynamically generate the Instagram post using ChatGPT.
    post = generate_instagram_post(book_name, filename)
    
    # Final outcome: Print and return the post text and full image URL.
    print("Instagram Post:")
    print(post)
    print("\nImage URL:")
    print(image_url)
    
    return post, image_url

if __name__ == "__main__":
    main()
