"""
AWS S3 Image Storage Utility

This module provides functions for securely storing and retrieving images from AWS S3.
Supports both public bucket access and signed URLs for better security.
"""

import boto3
import os
import uuid
from werkzeug.utils import secure_filename
from flask import current_app
from botocore.exceptions import ClientError, BotoCoreError
import logging

logger = logging.getLogger(__name__)

# Allowed image extensions
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}


def get_s3_client(aws_access_key_id=None, aws_secret_access_key=None, region_name=None):
    """
    Creates and returns an S3 client using AWS credentials.
    
    Args:
        aws_access_key_id: AWS access key (defaults to config)
        aws_secret_access_key: AWS secret key (defaults to config)
        region_name: AWS region (defaults to config)
    
    Returns:
        boto3 S3 client
    """
    from config import get_config
    config = get_config()
    
    access_key = aws_access_key_id or config.AWS_ACCESS_KEY_ID
    secret_key = aws_secret_access_key or config.AWS_SECRET_ACCESS_KEY
    region = region_name or config.AWS_REGION or os.getenv("AWS_S3_REGION", "us-east-1")
    
    if not access_key or not secret_key:
        raise ValueError("AWS credentials not configured. Please set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY.")
    
    return boto3.client(
        's3',
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name=region
    )


def get_bucket_name():
    """Gets the S3 bucket name from config or environment variable."""
    from config import get_config
    config = get_config()
    
    # Check if bucket name is in config (you'll need to add this)
    bucket_name = os.getenv("AWS_S3_BUCKET_NAME", "")
    
    if not bucket_name:
        raise ValueError("AWS_S3_BUCKET_NAME not configured. Please set it in .env file.")
    
    return bucket_name


def generate_unique_filename(original_filename):
    """
    Generates a unique filename for S3 storage.
    
    Args:
        original_filename: Original filename from upload
    
    Returns:
        Unique filename string (e.g., "abc123-def456-image.jpg")
    """
    # Get file extension
    file_ext = original_filename.rsplit('.', 1)[1].lower() if '.' in original_filename else ''
    
    # Generate unique ID
    unique_id = str(uuid.uuid4())[:8]
    
    # Sanitize original filename (remove extension)
    base_name = secure_filename(original_filename.rsplit('.', 1)[0] if '.' in original_filename else original_filename)
    base_name = base_name[:50]  # Limit length
    
    # Construct new filename
    if file_ext and file_ext in ALLOWED_EXTENSIONS:
        return f"{unique_id}-{base_name}.{file_ext}"
    else:
        return f"{unique_id}-{base_name}"


def upload_image_to_s3(file_obj, filename=None, content_type=None):
    """
    Uploads an image file to S3.
    
    Args:
        file_obj: File-like object (from request.files['image'])
        filename: Optional custom filename (auto-generated if not provided)
        content_type: Optional content type (auto-detected if not provided)
    
    Returns:
        Tuple of (success: bool, s3_key: str or None, error_message: str or None)
    """
    try:
        # Generate unique filename if not provided
        if not filename:
            original_filename = file_obj.filename if hasattr(file_obj, 'filename') else 'image'
            filename = generate_unique_filename(original_filename)
        
        # Get S3 client and bucket
        s3_client = get_s3_client()
        bucket_name = get_bucket_name()
        
        # Determine content type
        if not content_type:
            file_ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
            content_type_map = {
                'jpg': 'image/jpeg',
                'jpeg': 'image/jpeg',
                'png': 'image/png',
                'gif': 'image/gif',
                'webp': 'image/webp'
            }
            content_type = content_type_map.get(file_ext, 'image/jpeg')
        
        # Reset file pointer to beginning
        if hasattr(file_obj, 'seek'):a
            file_obj.seek(0)
        
        # Upload to S3
        # Note: ACLs are disabled (recommended), so we rely on bucket policy for public access
        s3_client.upload_fileobj(
            file_obj,
            bucket_name,
            filename,
            ExtraArgs={
                'ContentType': content_type
                # ACL removed - bucket policy handles public access when ACLs are disabled
            }
        )
        
        logger.info(f"Successfully uploaded image to S3: {filename}")
        return True, filename, None
        
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        error_msg = f"AWS S3 upload failed: {error_code}"
        logger.error(f"{error_msg}: {str(e)}")
        return False, None, error_msg
    
    except BotoCoreError as e:
        error_msg = "AWS S3 connection error"
        logger.error(f"{error_msg}: {str(e)}")
        return False, None, error_msg
    
    except Exception as e:
        error_msg = f"Unexpected error uploading to S3: {str(e)}"
        logger.error(error_msg)
        return False, None, error_msg


def get_s3_image_url(s3_key, signed=False, expiration=3600):
    """
    Gets the URL for an image stored in S3.
    
    Args:
        s3_key: The S3 object key (filename)
        signed: If True, returns a signed URL (expires after expiration seconds)
        expiration: Expiration time in seconds for signed URLs (default: 1 hour)
    
    Returns:
        Image URL string
    """
    try:
        bucket_name = get_bucket_name()
        region = os.getenv("AWS_S3_REGION", os.getenv("AWS_REGION", "us-east-1"))
        
        if signed:
            # Generate signed URL (more secure)
            s3_client = get_s3_client()
            url = s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': bucket_name, 'Key': s3_key},
                ExpiresIn=expiration
            )
            return url
        else:
            # Public URL (simpler, but requires public bucket)
            # Format: https://bucket-name.s3.region.amazonaws.com/key
            return f"https://{bucket_name}.s3.{region}.amazonaws.com/{s3_key}"
    
    except Exception as e:
        logger.error(f"Error generating S3 URL: {str(e)}")
        return None


def delete_image_from_s3(s3_key):
    """
    Deletes an image from S3.
    
    Args:
        s3_key: The S3 object key (filename) to delete
    
    Returns:
        Tuple of (success: bool, error_message: str or None)
    """
    try:
        s3_client = get_s3_client()
        bucket_name = get_bucket_name()
        
        s3_client.delete_object(Bucket=bucket_name, Key=s3_key)
        
        logger.info(f"Successfully deleted image from S3: {s3_key}")
        return True, None
        
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        error_msg = f"AWS S3 delete failed: {error_code}"
        logger.error(f"{error_msg}: {str(e)}")
        return False, error_msg
    
    except Exception as e:
        error_msg = f"Unexpected error deleting from S3: {str(e)}"
        logger.error(error_msg)
        return False, error_msg


def check_s3_configured():
    """
    Checks if S3 is properly configured.
    
    Returns:
        Tuple of (is_configured: bool, error_message: str or None)
    """
    try:
        get_s3_client()
        get_bucket_name()
        return True, None
    except ValueError as e:
        return False, str(e)
    except Exception as e:
        return False, f"Error checking S3 configuration: {str(e)}"

