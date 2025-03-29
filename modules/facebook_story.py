import requests
import os

class FacebookStory:
    BASE_GRAPH_URL = "https://graph.facebook.com/v22.0"
    BASE_UPLOAD_URL = "https://rupload.facebook.com/video-upload/v22.0"

    def __init__(self):
        self.page_id = os.getenv("PAGE_ID")
        self.page_access_token = os.getenv("PAGE_ACCESS_TOKEN")
        
        if not self.page_id or not self.page_access_token:
            raise ValueError("Facebook credentials are not set in environment variables.")

    # ======================
    # Methods for STORIES
    # ======================

    def init_story_upload(self):
        url = f"{self.BASE_GRAPH_URL}/{self.page_id}/video_stories"
        params = {
            "upload_phase": "start",
            "access_token": self.page_access_token
        }

        response = requests.post(url, data=params).json()
        return response.get('video_id'), response.get('upload_url')

    def upload_story_video(self, upload_url, hosted_file_url):
        headers = {
            "Authorization": f"OAuth {self.page_access_token}",
            "file_url": hosted_file_url
        }

        response = requests.post(upload_url, headers=headers).json()
        return response.get("success", False)

    def publish_story(self, video_id):
        url = f"{self.BASE_GRAPH_URL}/{self.page_id}/video_stories"
        params = {
            "video_id": video_id,
            "upload_phase": "finish",
            "access_token": self.page_access_token
        }

        response = requests.post(url, data=params).json()
        return response.get("success", False), response.get("post_id")

    # ======================
    # Methods for REELS
    # ======================

    def init_reel_upload(self):
        url = f"{self.BASE_GRAPH_URL}/{self.page_id}/video_reels"
        params = {
            "upload_phase": "start",
            "access_token": self.page_access_token
        }

        response = requests.post(url, json=params).json()
        return response.get('video_id'), response.get('upload_url')

    def upload_reel_video(self, video_id, hosted_file_url):
        upload_url = f"{self.BASE_UPLOAD_URL}/{video_id}"
        headers = {
            "Authorization": f"OAuth {self.page_access_token}",
            "file_url": hosted_file_url
        }

        response = requests.post(upload_url, headers=headers).json()
        return response.get("success", False)

    def check_video_status(self, video_id):
        url = f"{self.BASE_GRAPH_URL}/{video_id}"
        params = {
            "fields": "status",
            "access_token": self.page_access_token
        }

        response = requests.get(url, params=params).json()
        return response.get('status', {})

    def publish_reel(self, video_id, description=""):
        url = f"{self.BASE_GRAPH_URL}/{self.page_id}/video_reels"
        params = {
            "access_token": self.page_access_token,
            "video_id": video_id,
            "upload_phase": "finish",
            "video_state": "PUBLISHED",
            "description": description
        }

        response = requests.post(url, params=params).json()
        return response.get('success', False), response.get('post_id')