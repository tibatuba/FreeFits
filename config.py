import os


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
    MONGO_URI = os.getenv("MONGO_URI", "")
    GOOGLE_PLACES_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY", "")
    IMAGGA_API_KEY = os.getenv("IMAGGA_API_KEY", "")
    IMAGGA_API_SECRET = os.getenv("IMAGGA_API_SECRET", "")
    # api4ai Fashion API
    API4AI_API_KEY = os.getenv("API4AI_API_KEY", "")
    # AWS Rekognition (RECOMMENDED - free tier: 5,000 images/month, reliable, part of AWS)
    AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "")
    AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "")
    AWS_REGION = os.getenv("AWS_REGION", "us-east-1")  # Default region
    # Set to 'rekognition' for AWS Rekognition (recommended), 'api4ai', or 'imagga'
    IMAGE_VALIDATION_API = os.getenv("IMAGE_VALIDATION_API", "rekognition")  # Default to AWS Rekognition
    # AWS S3 Configuration for image storage
    AWS_S3_BUCKET_NAME = os.getenv("AWS_S3_BUCKET_NAME", "")
    AWS_S3_REGION = os.getenv("AWS_S3_REGION", "")  # Optional, defaults to AWS_REGION if not set


def get_config():
    return Config()


