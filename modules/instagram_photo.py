import os
import requests
import json

def post_to_instagram(image_url, post):
    """
    Posts an image to Instagram using the provided image URL and caption.
    Retrieves the user access token and Instagram user ID from environment variables.
    """
    # Retrieve access token and Instagram user ID from environment variables
    user_access_token = os.getenv('USER_ACCESS_TOKEN')
    ig_user_id = os.getenv('IG_ID')
    
    if not user_access_token or not ig_user_id:
        raise Exception("USER_ACCESS_TOKEN and IG_ID environment variables must be set.")

    # Construct the endpoint URL for creating media
    post_url = f'https://graph.facebook.com/v22.0/{ig_user_id}/media'

    payload = {
        'image_url': image_url,
        'caption': post,
        'access_token': user_access_token
    }

    # Post to the Instagram API to create media
    r = requests.post(post_url, data=payload)
    print("Create Media Response:")
    print(r.text)

    result = json.loads(r.text)
    if 'id' in result:
        creation_id = result['id']
        
        # Construct the endpoint URL for publishing the media
        second_url = f'https://graph.facebook.com/v22.0/{ig_user_id}/media_publish'
        second_payload = {
            'creation_id': creation_id,
            'access_token': user_access_token
        }
        r = requests.post(second_url, data=second_payload)
        print('---------------------- Posted to Instagram successfully ----------------------')
        print(r.text)
    else:
        print('---------------------- Failed to post to Instagram ---------------------------')
        print(r.text)
