import boto3
import numpy as np
import cv2
from .utils import natural_sort_key

#from utils import natural_sort_key

class S3Manager:
    def __init__(self):
        self.s3 = boto3.client('s3')

    @staticmethod
    def parse_s3_path(s3_path):
        s3_path = s3_path.replace("s3://", "")
        bucket, _, prefix = s3_path.partition('/')
        prefix = prefix.rstrip('/') + '/'
        return bucket, prefix

    def list_images(self, s3_path, allowed_exts=('.jpg', '.jpeg', '.png', '.bmp')):
        bucket, prefix = self.parse_s3_path(s3_path)
        response = self.s3.list_objects_v2(Bucket=bucket, Prefix=prefix)
        keys = [obj['Key'] for obj in response.get('Contents', []) if obj['Key'].lower().endswith(allowed_exts)]
        return sorted(keys, key=lambda k: natural_sort_key(k))

    def read_image(self, bucket, key):
        obj = self.s3.get_object(Bucket=bucket, Key=key)
        data = np.asarray(bytearray(obj['Body'].read()), dtype=np.uint8)
        return cv2.imdecode(data, cv2.IMREAD_COLOR)

    def upload_file(self, local_path, bucket, key):
        self.s3.upload_file(local_path, bucket, key)
        video_url = f"https://{bucket}.s3.amazonaws.com/{key}"
        return video_url