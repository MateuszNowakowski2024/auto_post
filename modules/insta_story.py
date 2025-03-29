import requests
import time
import os

class InstaStory:
    BASE_URL = "https://graph.facebook.com/v22.0"

    def __init__(self):
        self.ig_user_id = os.getenv('IG_ID')
        self.user_access_token = os.getenv('USER_ACCESS_TOKEN')
        
        if not self.ig_user_id or not self.user_access_token:
            raise ValueError("Instagram credentials are not set in environment variables.")

    def create_media_container(self, video_url, media_type, caption=None):
        url = f"{self.BASE_URL}/{self.ig_user_id}/media"
        payload = {
            "video_url": video_url,
            "media_type": media_type,
            "access_token": self.user_access_token
        }
        if caption:
            payload["caption"] = caption

        response = requests.post(url, data=payload)
        data = response.json()
        print(f"Created {media_type} container:", data)
        return data.get("id")

    def publish_media(self, container_id):
        url = f"{self.BASE_URL}/{self.ig_user_id}/media_publish"
        payload = {
            "creation_id": container_id,
            "access_token": self.user_access_token
        }

        response = requests.post(url, data=payload)
        data = response.json()
        print(f"Published media with container {container_id}:", data)
        return data.get("id")

    def get_media_status(self, container_id):
        url = f"{self.BASE_URL}/{container_id}"
        params = {
            "fields": "status_code",
            "access_token": self.user_access_token
        }

        response = requests.get(url, params=params)
        data = response.json()
        print(f"Status for container {container_id}:", data)
        return data.get("status_code")

    def publish_reel(self, video_url, caption=None):
        container_id = self.create_media_container(video_url, "REELS", caption)

        if container_id:
            time.sleep(15)
            # Optionally check status before publishing
            for _ in range(8):
                status = self.get_media_status(container_id)
                if status == "FINISHED":
                    break
                elif status == "ERROR":
                    print("Error during media processing.")
                    return None
                time.sleep(10)  # Wait 10 sec before retrying
            return self.publish_media(container_id)

    def publish_story(self, video_url):
        container_id = self.create_media_container(video_url, "STORIES")

        if container_id:
            time.sleep(15)
            for _ in range(8):
                status = self.get_media_status(container_id)
                if status == "FINISHED":
                    break
                elif status == "ERROR":
                    print("Error during media processing.")
                    return None
                time.sleep(10)
            return self.publish_media(container_id)