import requests
import time
import os


def post_image_to_feed(page_id, page_access_token, post, image_url):
    """
    Posts to the Facebook Page feed with a caption (message) and link (image link).
    """
    post_url = f"https://graph.facebook.com/v22.0/{page_id}/feed"
    data = {
        "message": post,
        "link": image_url,
        "access_token": page_access_token
    }
    r = requests.post(post_url, json=data)
    print("Feed Post Response:", r.text)
    try:
        response_json = r.json()
        return response_json.get("id")
    except Exception as e:
        print("Error parsing JSON response:", e)
        return None

def post_comment(page_post_id, page_access_token):
    """
    Posts a comment under a previously created Facebook post.
    The link here remains hardcoded, as requested.
    """
    post_url = f"https://graph.facebook.com/v22.0/{page_post_id}/comments"
    data = {
        "message": "Visit Our Website 👉 https://lily10coloringbooks.fun",
        "access_token": page_access_token
    }
    r = requests.post(post_url, json=data)
    print("Comment Post Response:", r.text)

def post_image(page_id, page_access_token, post, image_url):
    """
    Posts an image directly to the Facebook Page with a caption.
    """
    post_url = f"https://graph.facebook.com/v22.0/{page_id}/photos"
    data = {
        "caption": post,
        "url": image_url,
        "access_token": page_access_token
    }
    r = requests.post(post_url, json=data)
    print("Image Post Response:", r.text)

def post_to_facebook(post, image_url):
    
    page_id = os.getenv("PAGE_ID")
    page_access_token = os.getenv("PAGE_ACCESS_TOKEN")
    """
    Coordinates the workflow of:
      1) Posting link+caption to the feed
      2) Waiting 10 seconds
      3) Commenting on the post
      4) Waiting 5 seconds
      5) Posting an image
    """
    # 1. Post to feed and retrieve the post ID.
    post_id = post_image_to_feed(page_id, page_access_token, post, image_url)
    
    # 2. Wait 10 seconds before posting the comment.
    time.sleep(10)
    
    # 3. Post a comment using the returned post ID.
    if post_id:
        post_comment(post_id, page_access_token)
    else:
        print("Post ID not available, skipping comment post.")
    
    # 4. Wait 5 seconds before posting the image.
    time.sleep(5)
    
    # 5. Post an image.
    post_image(page_id, page_access_token, post, image_url)