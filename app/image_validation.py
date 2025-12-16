"""
Image validation module for verifying uploaded images contain clothing items.
Supports multiple APIs: AWS Rekognition 

Security features:
- File size validation
- Path sanitization
- Secure error handling
- Input validation
"""

import requests
import base64
import os
import logging
from typing import Tuple, Optional
from pathlib import Path

try:
    import boto3
    from botocore.exceptions import ClientError, BotoCoreError
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False

# Configure logging
logger = logging.getLogger(__name__)

# ============================================================================
# CONSTANTS - Configuration values
# ============================================================================

# Maximum file size: 10MB (AWS Rekognition limit is 15MB, but we use 10MB for safety)
MAX_IMAGE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB

# Minimum file size: 1KB (to prevent empty files)
MIN_IMAGE_SIZE_BYTES = 1024  # 1 KB

# AWS Rekognition API configuration
REKOGNITION_MAX_LABELS = 20
REKOGNITION_MIN_CONFIDENCE = 50.0  # Minimum confidence for clothing detection
REKOGNITION_NON_CLOTHING_MIN_CONFIDENCE = 70.0  # Higher threshold for rejection

# API timeout (seconds)
API_TIMEOUT = 30

# Clothing-related labels that indicate the image contains clothing
# Used by both Imagga and AWS Rekognition
CLOTHING_LABELS = frozenset({
    'apparel', 'clothing', 'garment', 'outfit', 'wardrobe', 'fashion',
    'shirt', 't-shirt', 'tshirt', 'blouse', 'top', 'tank top',
    'pants', 'trousers', 'jeans', 'shorts', 'leggings',
    'dress', 'skirt', 'gown',
    'jacket', 'coat', 'hoodie', 'sweater', 'cardigan', 'pullover',
    'shoes', 'sneakers', 'boots', 'heels', 'sandals', 'footwear',
    'hat', 'cap', 'beanie',
    'accessories', 'jewelry', 'watch', 'bag', 'purse', 'backpack',
    'socks', 'underwear', 'lingerie',
    'suit', 'tie', 'formal wear',
    'athletic wear', 'sportswear', 'activewear', 'gym wear',
    'swimwear', 'bikini', 'swimsuit',
    'pajamas', 'sleepwear', 'loungewear'
})

# Non-clothing labels that indicate the image is NOT clothing
# Used by both Imagga and AWS Rekognition
NON_CLOTHING_LABELS = frozenset({
    'house', 'building', 'home', 'residence', 'architecture', 'structure',
    'furniture', 'table', 'chair', 'desk', 'sofa', 'couch', 'bed', 'cabinet',
    'vehicle', 'car', 'truck', 'motorcycle', 'bicycle', 'bike', 'automobile',
    'food', 'meal', 'dish', 'restaurant', 'cooking', 'recipe',
    'animal', 'pet', 'dog', 'cat', 'bird', 'wildlife',
    'landscape', 'nature', 'mountain', 'forest', 'beach', 'ocean', 'sky',
    'electronics', 'computer', 'phone', 'laptop', 'device',
    'appliance', 'refrigerator', 'oven', 'microwave',
    'plant', 'tree', 'flower', 'garden',
    'tool', 'wrench', 'hammer', 'hardware', 'equipment'
    # Note: 'person', 'people', 'group', 'crowd' are NOT in this list
    # because people can wear clothing, so we check for clothing first
})

# Legacy aliases for backward compatibility
CLOTHING_TAGS = CLOTHING_LABELS
NON_CLOTHING_KEYWORDS = NON_CLOTHING_LABELS

# ============================================================================
# SECURITY & VALIDATION FUNCTIONS
# ============================================================================

def validate_file_path(file_path: str) -> Tuple[bool, Optional[str]]:
    """
    Validate that a file path is safe and exists.
    
    Args:
        file_path: Path to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        # Convert to Path object for safer path handling
        path = Path(file_path).resolve()
        
        # Check if file exists
        if not path.exists():
            return False, "Image file not found."
        
        # Check if it's actually a file (not a directory)
        if not path.is_file():
            return False, "Invalid file path."
        
        # Check file size
        file_size = path.stat().st_size
        
        if file_size < MIN_IMAGE_SIZE_BYTES:
            return False, f"Image file is too small (minimum {MIN_IMAGE_SIZE_BYTES} bytes)."
        
        if file_size > MAX_IMAGE_SIZE_BYTES:
            return False, f"Image file is too large (maximum {MAX_IMAGE_SIZE_BYTES / (1024*1024):.1f}MB)."
        
        return True, None
        
    except (OSError, ValueError) as e:
        logger.error(f"File path validation error: {e}")
        return False, "Invalid file path or file access error."


def sanitize_error_message(error: Exception, api_name: str = "API") -> str:
    """
    Sanitize error messages to prevent information leakage.
    
    Args:
        error: The exception that occurred
        api_name: Name of the API/service
        
    Returns:
        Safe error message for user display
    """
    error_str = str(error)
    
    # Don't expose internal paths, credentials, or stack traces
    if any(sensitive in error_str.lower() for sensitive in ['key', 'secret', 'password', 'token', 'credential']):
        return f"{api_name} authentication error. Please contact administrator."
    
    # Don't expose full exception details
    if 'traceback' in error_str.lower() or 'file "' in error_str:
        return f"{api_name} service error. Please try again or contact support."
    
    # Return generic message for unknown errors
    return f"{api_name} error occurred. Please try again."


def validate_clothing_image(image_path: str, api_key: str, api_secret: str) -> Tuple[bool, Optional[str]]:
    """
    Validate if an uploaded image contains clothing items using Imagga API.
    FIXED: Checks for clothing FIRST before applying negative filters.
    
    Args:
        image_path: Path to the uploaded image file
        api_key: Imagga API key
        api_secret: Imagga API secret
        
    Returns:
        Tuple of (is_valid, error_message)
        - is_valid: True if image contains clothing, False otherwise
        - error_message: Error message if validation failed, None if successful
    """
    if not api_key or not api_secret:
        return False, "Imagga API credentials not configured. Please contact administrator."
    
    if not os.path.exists(image_path):
        return False, "Image file not found."
    
    try:
        # Prepare request to Imagga Tagging API
        url = "https://api.imagga.com/v2/tags"
        
        # Use file upload method (more reliable than base64 for large images)
        files = {'image': open(image_path, 'rb')}
        auth = (api_key, api_secret)
        
        response = requests.post(url, files=files, auth=auth, timeout=30)
        files['image'].close()  # Close the file after request
        
        if response.status_code != 200:
            error_msg = f"API request failed with status {response.status_code}"
            try:
                error_data = response.json()
                if 'message' in error_data:
                    error_msg = error_data['message']
            except:
                pass
            return False, f"Image validation error: {error_msg}"
        
        # Parse response
        data = response.json()
        
        if 'result' not in data or 'tags' not in data['result']:
            return False, "Could not analyze image. Please try a different image."
        
        tags = data['result']['tags']
        
        # Get top 5 tags for analysis (most confident predictions)
        top_tags = tags[:5]
        
        # STEP 1: Check for clothing keywords FIRST (prioritize clothing detection)
        # This ensures images of people wearing clothing are accepted
        clothing_found = False
        max_confidence = 0.0
        clothing_in_top = False
        matched_tags = []
        
        # Check top 3 tags first (most important)
        for tag_info in top_tags[:3]:
            tag_name = tag_info.get('tag', {}).get('en', '').lower()
            confidence = float(tag_info.get('confidence', 0))
            
            # Check if tag matches any clothing keyword
            for clothing_keyword in CLOTHING_TAGS:
                if clothing_keyword in tag_name:
                    clothing_found = True
                    clothing_in_top = True
                    if confidence > max_confidence:
                        max_confidence = confidence
                    matched_tags.append((tag_name, confidence))
                    break
        
        # If not found in top 3, check tags 4-10 (but require higher confidence)
        if not clothing_in_top:
            for tag_info in tags[3:10]:
                tag_name = tag_info.get('tag', {}).get('en', '').lower()
                confidence = float(tag_info.get('confidence', 0))
                
                # Only accept if confidence is very high (>= 50%)
                for clothing_keyword in CLOTHING_TAGS:
                    if clothing_keyword in tag_name and confidence >= 50.0:
                        clothing_found = True
                        if confidence > max_confidence:
                            max_confidence = confidence
                        matched_tags.append((tag_name, confidence))
                        break
        
        # STEP 2: If clothing is found with sufficient confidence, accept immediately
        # This allows images of people wearing clothing to pass
        # Lowered thresholds to be more permissive for people wearing clothes
        if clothing_in_top and max_confidence >= 30.0:
            return True, None
        elif clothing_found and max_confidence >= 50.0:
            return True, None
        
        # STEP 3: Only check for negative keywords if clothing was NOT found
        # This prevents rejecting valid clothing images that show a person
        if not clothing_found or max_confidence < 30.0:
            for tag_info in top_tags:
                tag_name = tag_info.get('tag', {}).get('en', '').lower()
                confidence = float(tag_info.get('confidence', 0))
                
                # If a non-clothing keyword appears with high confidence, reject
                # Note: "person", "people", "group", "crowd" are NOT in NON_CLOTHING_KEYWORDS
                # because people can wear clothing
                for negative_keyword in NON_CLOTHING_KEYWORDS:
                    if negative_keyword in tag_name and confidence >= 30.0:
                        top_tag_names = [t.get('tag', {}).get('en', '') for t in top_tags[:3]]
                        return False, f"Image does not appear to contain clothing. Detected: {', '.join(top_tag_names)}. Please upload an image of a clothing item."
        
        # STEP 4: Final validation - if we reach here, clothing wasn't found with sufficient confidence
        if clothing_found:
            return False, f"Image may contain clothing, but it's not clearly the main subject (confidence: {max_confidence:.1f}%). Please upload a clear, focused image of the clothing item."
        else:
            # Get top tags for debugging/feedback
            top_tag_names = [tag_info.get('tag', {}).get('en', '') for tag_info in top_tags[:3]]
            return False, f"Image does not appear to contain clothing items. Detected: {', '.join(top_tag_names)}. Please upload an image of a clothing item."
        
    except requests.exceptions.Timeout:
        return False, "Image validation timed out. Please try again."
    except requests.exceptions.RequestException as e:
        return False, f"Network error during image validation: {str(e)}"
    except Exception as e:
        return False, f"Unexpected error during image validation: {str(e)}"


def validate_clothing_image_rekognition(image_path: str, aws_access_key_id: str, aws_secret_access_key: str, aws_region: str = "us-east-1") -> Tuple[bool, Optional[str]]:
    """
    Validate if an uploaded image contains clothing items using AWS Rekognition.
    This is the RECOMMENDED method - reliable, free tier available, and part of AWS.
    
    Free Tier: 5,000 images/month for first 12 months
    
    Args:
        image_path: Path to the uploaded image file
        aws_access_key_id: AWS Access Key ID
        aws_secret_access_key: AWS Secret Access Key
        aws_region: AWS region (default: us-east-1)
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not BOTO3_AVAILABLE:
        logger.error("boto3 library not installed")
        return False, "Image validation service not available. Please contact administrator."
    
    if not aws_access_key_id or not aws_secret_access_key:
        logger.warning("AWS credentials not configured")
        return False, "Image validation service not configured. Please contact administrator."
    
    # Validate file path and size
    is_valid_path, error_msg = validate_file_path(image_path)
    if not is_valid_path:
        logger.warning(f"File validation failed: {error_msg}")
        return False, error_msg
    
    try:
        # Initialize Rekognition client
        rekognition_client = boto3.client(
            'rekognition',
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            region_name=aws_region
        )
        
        # Read image file
        with open(image_path, 'rb') as image_file:
            image_bytes = image_file.read()
        
        # Call DetectLabels API
        response = rekognition_client.detect_labels(
            Image={'Bytes': image_bytes},
            MaxLabels=REKOGNITION_MAX_LABELS,
            MinConfidence=REKOGNITION_MIN_CONFIDENCE
        )
        
        logger.debug(f"AWS Rekognition API call successful. Detected {len(response.get('Labels', []))} labels.")
        
        # Extract labels and their confidence scores
        labels = response.get('Labels', [])
        
        if not labels:
            logger.warning("No labels returned from AWS Rekognition")
            return False, "Could not analyze image. Please try a different image."
        
        # Check for clothing labels
        clothing_found = False
        max_clothing_confidence = 0.0
        detected_clothing = []
        
        for label in labels:
            label_name = label.get('Name', '').lower()
            confidence = float(label.get('Confidence', 0))
            
            # Check if it's a clothing item (use module-level constant)
            for clothing_keyword in CLOTHING_LABELS:
                if clothing_keyword in label_name:
                    clothing_found = True
                    detected_clothing.append(f"{label.get('Name')} ({confidence:.1f}%)")
                    if confidence > max_clothing_confidence:
                        max_clothing_confidence = confidence
                    break
        
        # If clothing found with sufficient confidence, accept
        if clothing_found and max_clothing_confidence >= REKOGNITION_MIN_CONFIDENCE:
            logger.info(f"Image accepted: Clothing detected with {max_clothing_confidence:.1f}% confidence")
            return True, None
        
        # Check for non-clothing labels with high confidence
        for label in labels:
            label_name = label.get('Name', '').lower()
            confidence = float(label.get('Confidence', 0))
            
            for non_clothing_keyword in NON_CLOTHING_LABELS:
                if non_clothing_keyword in label_name and confidence >= REKOGNITION_NON_CLOTHING_MIN_CONFIDENCE:
                    top_labels = [f"{l.get('Name')} ({l.get('Confidence', 0):.1f}%)" for l in labels[:3]]
                    logger.info(f"Image rejected: Non-clothing detected ({non_clothing_keyword} at {confidence:.1f}%)")
                    return False, f"Image does not appear to contain clothing. Detected: {', '.join(top_labels)}. Please upload an image of a clothing item."
        
        # No clothing found
        top_labels = [f"{l.get('Name')} ({l.get('Confidence', 0):.1f}%)" for l in labels[:3]]
        logger.info(f"Image rejected: No clothing detected. Top labels: {', '.join(top_labels)}")
        return False, f"No clothing items detected in the image. Detected: {', '.join(top_labels)}. Please upload an image of a clothing item."
        
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        error_message = e.response.get('Error', {}).get('Message', '')
        logger.error(f"AWS Rekognition ClientError: {error_code} - {error_message}")
        
        # Sanitize error messages for user display
        if error_code in ['InvalidParameterException', 'ImageTooLargeException']:
            return False, "Image file is invalid or too large. Please try a different image."
        elif error_code in ['InvalidS3ObjectException', 'InvalidImageFormatException']:
            return False, "Invalid image format. Please upload a valid image file (JPG, PNG, etc.)."
        elif error_code in ['AccessDeniedException', 'InvalidAccessKeyId', 'SignatureDoesNotMatch']:
            return False, "Image validation service authentication error. Please contact administrator."
        else:
            return False, sanitize_error_message(e, "AWS Rekognition")
            
    except BotoCoreError as e:
        logger.error(f"AWS BotoCoreError: {e}")
        return False, sanitize_error_message(e, "AWS")
    except Exception as e:
        logger.exception(f"Unexpected error during image validation: {e}")
        return False, sanitize_error_message(e, "Image validation")


def validate_clothing_image_from_bytes(image_bytes: bytes, api_key: str, api_secret: str) -> Tuple[bool, Optional[str]]:
    """
    Validate if an uploaded image (as bytes) contains clothing items using Imagga API.
    Alternative method that works with in-memory image data.
    Uses the same fixed logic as validate_clothing_image.
    
    Args:
        image_bytes: Image file content as bytes
        api_key: Imagga API key
        api_secret: Imagga API secret
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not api_key or not api_secret:
        return False, "Imagga API credentials not configured. Please contact administrator."
    
    try:
        # Prepare request to Imagga Tagging API
        url = "https://api.imagga.com/v2/tags"
        
        # Use file upload method with BytesIO
        from io import BytesIO
        files = {'image': BytesIO(image_bytes)}
        auth = (api_key, api_secret)
        
        response = requests.post(url, files=files, auth=auth, timeout=30)
        
        if response.status_code != 200:
            error_msg = f"API request failed with status {response.status_code}"
            try:
                error_data = response.json()
                if 'message' in error_data:
                    error_msg = error_data['message']
            except:
                pass
            return False, f"Image validation error: {error_msg}"
        
        # Parse response (same logic as validate_clothing_image)
        data = response.json()
        
        if 'result' not in data or 'tags' not in data['result']:
            return False, "Could not analyze image. Please try a different image."
        
        tags = data['result']['tags']
        
        # Get top 5 tags for analysis (most confident predictions)
        top_tags = tags[:5]
        
        # STEP 1: Check for clothing keywords FIRST (prioritize clothing detection)
        clothing_found = False
        max_confidence = 0.0
        clothing_in_top = False
        
        # Check top 3 tags first (most important)
        for tag_info in top_tags[:3]:
            tag_name = tag_info.get('tag', {}).get('en', '').lower()
            confidence = float(tag_info.get('confidence', 0))
            
            for clothing_keyword in CLOTHING_TAGS:
                if clothing_keyword in tag_name:
                    clothing_found = True
                    clothing_in_top = True
                    if confidence > max_confidence:
                        max_confidence = confidence
                    break
        
        # If not found in top 3, check tags 4-10
        if not clothing_in_top:
            for tag_info in tags[3:10]:
                tag_name = tag_info.get('tag', {}).get('en', '').lower()
                confidence = float(tag_info.get('confidence', 0))
                
                for clothing_keyword in CLOTHING_TAGS:
                    if clothing_keyword in tag_name and confidence >= 50.0:
                        clothing_found = True
                        if confidence > max_confidence:
                            max_confidence = confidence
                        break
        
        # STEP 2: If clothing found with sufficient confidence, accept
        if clothing_in_top and max_confidence >= 30.0:
            return True, None
        elif clothing_found and max_confidence >= 50.0:
            return True, None
        
        # STEP 3: Check negative keywords only if clothing not found
        if not clothing_found or max_confidence < 30.0:
            for tag_info in top_tags:
                tag_name = tag_info.get('tag', {}).get('en', '').lower()
                confidence = float(tag_info.get('confidence', 0))
                
                for negative_keyword in NON_CLOTHING_KEYWORDS:
                    if negative_keyword in tag_name and confidence >= 30.0:
                        top_tag_names = [t.get('tag', {}).get('en', '') for t in top_tags[:3]]
                        return False, f"Image does not appear to contain clothing. Detected: {', '.join(top_tag_names)}. Please upload an image of a clothing item."
        
        # STEP 4: Final validation
        if clothing_found:
            return False, f"Image may contain clothing, but it's not clearly the main subject (confidence: {max_confidence:.1f}%). Please upload a clear, focused image of the clothing item."
        else:
            top_tag_names = [tag_info.get('tag', {}).get('en', '') for tag_info in top_tags[:3]]
            return False, f"Image does not appear to contain clothing items. Detected: {', '.join(top_tag_names)}. Please upload an image of a clothing item."
        
    except requests.exceptions.Timeout:
        return False, "Image validation timed out. Please try again."
    except requests.exceptions.RequestException as e:
        return False, f"Network error during image validation: {str(e)}"
    except Exception as e:
        return False, f"Unexpected error during image validation: {str(e)}"


def validate_clothing_image_rekognition(image_path: str, aws_access_key_id: str, aws_secret_access_key: str, aws_region: str = "us-east-1") -> Tuple[bool, Optional[str]]:
    """
    Validate if an uploaded image contains clothing items using AWS Rekognition.
    This is the RECOMMENDED method - reliable, free tier available, and part of AWS.
    
    Free Tier: 5,000 images/month for first 12 months
    
    Args:
        image_path: Path to the uploaded image file
        aws_access_key_id: AWS Access Key ID
        aws_secret_access_key: AWS Secret Access Key
        aws_region: AWS region (default: us-east-1)
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not BOTO3_AVAILABLE:
        logger.error("boto3 library not installed")
        return False, "Image validation service not available. Please contact administrator."
    
    if not aws_access_key_id or not aws_secret_access_key:
        logger.warning("AWS credentials not configured")
        return False, "Image validation service not configured. Please contact administrator."
    
    # Validate file path and size
    is_valid_path, error_msg = validate_file_path(image_path)
    if not is_valid_path:
        logger.warning(f"File validation failed: {error_msg}")
        return False, error_msg
    
    try:
        # Initialize Rekognition client
        rekognition_client = boto3.client(
            'rekognition',
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            region_name=aws_region
        )
        
        # Read image file
        with open(image_path, 'rb') as image_file:
            image_bytes = image_file.read()
        
        # Call DetectLabels API
        response = rekognition_client.detect_labels(
            Image={'Bytes': image_bytes},
            MaxLabels=REKOGNITION_MAX_LABELS,
            MinConfidence=REKOGNITION_MIN_CONFIDENCE
        )
        
        logger.debug(f"AWS Rekognition API call successful. Detected {len(response.get('Labels', []))} labels.")
        
        # Extract labels and their confidence scores
        labels = response.get('Labels', [])
        
        if not labels:
            logger.warning("No labels returned from AWS Rekognition")
            return False, "Could not analyze image. Please try a different image."
        
        # Check for clothing labels
        clothing_found = False
        max_clothing_confidence = 0.0
        detected_clothing = []
        
        for label in labels:
            label_name = label.get('Name', '').lower()
            confidence = float(label.get('Confidence', 0))
            
            # Check if it's a clothing item (use module-level constant)
            for clothing_keyword in CLOTHING_LABELS:
                if clothing_keyword in label_name:
                    clothing_found = True
                    detected_clothing.append(f"{label.get('Name')} ({confidence:.1f}%)")
                    if confidence > max_clothing_confidence:
                        max_clothing_confidence = confidence
                    break
        
        # If clothing found with sufficient confidence, accept
        if clothing_found and max_clothing_confidence >= REKOGNITION_MIN_CONFIDENCE:
            logger.info(f"Image accepted: Clothing detected with {max_clothing_confidence:.1f}% confidence")
            return True, None
        
        # Check for non-clothing labels with high confidence
        for label in labels:
            label_name = label.get('Name', '').lower()
            confidence = float(label.get('Confidence', 0))
            
            for non_clothing_keyword in NON_CLOTHING_LABELS:
                if non_clothing_keyword in label_name and confidence >= REKOGNITION_NON_CLOTHING_MIN_CONFIDENCE:
                    top_labels = [f"{l.get('Name')} ({l.get('Confidence', 0):.1f}%)" for l in labels[:3]]
                    logger.info(f"Image rejected: Non-clothing detected ({non_clothing_keyword} at {confidence:.1f}%)")
                    return False, f"Image does not appear to contain clothing. Detected: {', '.join(top_labels)}. Please upload an image of a clothing item."
        
        # No clothing found
        top_labels = [f"{l.get('Name')} ({l.get('Confidence', 0):.1f}%)" for l in labels[:3]]
        logger.info(f"Image rejected: No clothing detected. Top labels: {', '.join(top_labels)}")
        return False, f"No clothing items detected in the image. Detected: {', '.join(top_labels)}. Please upload an image of a clothing item."
        
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        error_message = e.response.get('Error', {}).get('Message', '')
        logger.error(f"AWS Rekognition ClientError: {error_code} - {error_message}")
        
        # Sanitize error messages for user display
        if error_code in ['InvalidParameterException', 'ImageTooLargeException']:
            return False, "Image file is invalid or too large. Please try a different image."
        elif error_code in ['InvalidS3ObjectException', 'InvalidImageFormatException']:
            return False, "Invalid image format. Please upload a valid image file (JPG, PNG, etc.)."
        elif error_code in ['AccessDeniedException', 'InvalidAccessKeyId', 'SignatureDoesNotMatch']:
            return False, "Image validation service authentication error. Please contact administrator."
        else:
            return False, sanitize_error_message(e, "AWS Rekognition")
            
    except BotoCoreError as e:
        logger.error(f"AWS BotoCoreError: {e}")
        return False, sanitize_error_message(e, "AWS")
    except Exception as e:
        logger.exception(f"Unexpected error during image validation: {e}")
        return False, sanitize_error_message(e, "Image validation")


def validate_clothing_image_api4ai(image_path: str, api_key: str) -> Tuple[bool, Optional[str]]:
    """
    Validate if an uploaded image contains clothing items using api4ai Fashion API.
    This API is specifically designed for clothing detection and is more accurate.
    
    Args:
        image_path: Path to the uploaded image file
        api_key: api4ai API key (get from https://api4.ai/)
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not api_key:
        return False, "api4ai API key not configured. Please contact administrator."
    
    print(f"DEBUG: api4ai validation - API key present: {bool(api_key)}, key length: {len(api_key)}")
    
    if not os.path.exists(image_path):
        return False, "Image file not found."
    
    print(f"DEBUG: api4ai validation - Image path: {image_path}, exists: {os.path.exists(image_path)}")
    
    try:
        # Prepare request to api4ai Fashion API
        # Try multiple possible endpoints and authentication methods
        # api4ai can be accessed directly or through RapidAPI
        
        # Read image file once
        with open(image_path, 'rb') as image_file:
            image_data = image_file.read()
        
        # Try different endpoint/header combinations
        # api4ai Fashion API endpoints (based on official documentation)
        attempts = [
            {
                'url': 'https://api4ai.cloud/fashion/v1/results',
                'headers': {'x-api-key': api_key},
                'files': {'image': (os.path.basename(image_path), image_data, 'image/jpeg')}
            },
            {
                'url': 'https://demo.api4ai.cloud/fashion/v1/results',
                'headers': {'x-api-key': api_key},
                'files': {'image': (os.path.basename(image_path), image_data, 'image/jpeg')}
            },
            {
                'url': 'https://fashion4.p.rapidapi.com/v1/results',
                'headers': {'X-RapidAPI-Key': api_key, 'X-RapidAPI-Host': 'fashion4.p.rapidapi.com'},
                'files': {'image': (os.path.basename(image_path), image_data, 'image/jpeg')}
            },
            {
                'url': 'https://api4ai.cloud/api/v1/fashion',
                'headers': {'x-api-key': api_key},
                'files': {'image': (os.path.basename(image_path), image_data, 'image/jpeg')}
            }
        ]
        
        response = None
        last_error = None
        
        # Try each endpoint/header combination until one works
        for attempt in attempts:
            try:
                print(f"DEBUG: Trying api4ai endpoint: {attempt['url']}")
                response = requests.post(
                    attempt['url'],
                    files=attempt['files'],
                    headers=attempt['headers'],
                    timeout=30
                )
                print(f"DEBUG: Response status: {response.status_code}")
                if response.status_code == 200:
                    print(f"DEBUG: Success with endpoint: {attempt['url']}")
                    break
                elif response.status_code == 401:
                    # Wrong auth format, try next
                    try:
                        error_data = response.json()
                        print(f"DEBUG: 401 error details: {error_data}")
                    except:
                        pass
                    last_error = f"Authentication failed (401) with {attempt['url']}"
                    continue
                else:
                    # Log non-200 responses for debugging
                    try:
                        error_data = response.json()
                        print(f"DEBUG: Error response: {error_data}")
                    except:
                        print(f"DEBUG: Non-JSON error response: {response.text[:200]}")
            except requests.exceptions.RequestException as e:
                print(f"DEBUG: Request exception: {type(e).__name__}: {str(e)}")
                last_error = f"{attempt['url']}: {str(e)}"
                continue
        
        if not response or response.status_code != 200:
            error_msg = f"API request failed with status {response.status_code if response else 'connection error'}"
            try:
                if response:
                    error_data = response.json()
                    if 'message' in error_data:
                        error_msg = error_data['message']
                    elif 'error' in error_data:
                        error_msg = error_data['error']
                    elif 'detail' in error_data:
                        error_msg = error_data['detail']
            except:
                pass
            if last_error:
                error_msg += f" (Last attempt: {last_error})"
            return False, f"Image validation error: {error_msg}"
        
        # Parse response
        data = response.json()
        
        # api4ai Fashion API can return results in different formats
        # Check multiple possible response structures
        detected_items = []
        
        # Format 1: results.entities[].classes[].name
        if 'results' in data:
            for result in data.get('results', []):
                if 'entities' in result:
                    for entity in result['entities']:
                        if 'classes' in entity:
                            for cls in entity['classes']:
                                if 'name' in cls:
                                    detected_items.append(cls['name'])
        
        # Format 2: data.entities[].classes[].name
        if 'entities' in data and not detected_items:
            for entity in data['entities']:
                if 'classes' in entity:
                    for cls in entity['classes']:
                        if 'name' in cls:
                            detected_items.append(cls['name'])
        
        # Format 3: data.items[] or data.detected_items[]
        if not detected_items:
            if 'items' in data:
                detected_items = data['items']
            elif 'detected_items' in data:
                detected_items = data['detected_items']
            elif 'clothing' in data:
                detected_items = data['clothing']
        
        # If any clothing items detected, image is valid
        if detected_items and len(detected_items) > 0:
            return True, None
        else:
            return False, "No clothing items detected in the image. Please upload an image of a clothing item."
        
    except requests.exceptions.Timeout:
        return False, "Image validation timed out. Please try again."
    except requests.exceptions.RequestException as e:
        return False, f"Network error during image validation: {str(e)}"
    except Exception as e:
        return False, f"Unexpected error during image validation: {str(e)}"


def validate_clothing_image_rekognition(image_path: str, aws_access_key_id: str, aws_secret_access_key: str, aws_region: str = "us-east-1") -> Tuple[bool, Optional[str]]:
    """
    Validate if an uploaded image contains clothing items using AWS Rekognition.
    This is the RECOMMENDED method - reliable, free tier available, and part of AWS.
    
    Free Tier: 5,000 images/month for first 12 months
    
    Args:
        image_path: Path to the uploaded image file
        aws_access_key_id: AWS Access Key ID
        aws_secret_access_key: AWS Secret Access Key
        aws_region: AWS region (default: us-east-1)
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not BOTO3_AVAILABLE:
        logger.error("boto3 library not installed")
        return False, "Image validation service not available. Please contact administrator."
    
    if not aws_access_key_id or not aws_secret_access_key:
        logger.warning("AWS credentials not configured")
        return False, "Image validation service not configured. Please contact administrator."
    
    # Validate file path and size
    is_valid_path, error_msg = validate_file_path(image_path)
    if not is_valid_path:
        logger.warning(f"File validation failed: {error_msg}")
        return False, error_msg
    
    try:
        # Initialize Rekognition client
        rekognition_client = boto3.client(
            'rekognition',
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            region_name=aws_region
        )
        
        # Read image file
        with open(image_path, 'rb') as image_file:
            image_bytes = image_file.read()
        
        # Call DetectLabels API
        response = rekognition_client.detect_labels(
            Image={'Bytes': image_bytes},
            MaxLabels=REKOGNITION_MAX_LABELS,
            MinConfidence=REKOGNITION_MIN_CONFIDENCE
        )
        
        logger.debug(f"AWS Rekognition API call successful. Detected {len(response.get('Labels', []))} labels.")
        
        # Extract labels and their confidence scores
        labels = response.get('Labels', [])
        
        if not labels:
            logger.warning("No labels returned from AWS Rekognition")
            return False, "Could not analyze image. Please try a different image."
        
        # Check for clothing labels
        clothing_found = False
        max_clothing_confidence = 0.0
        detected_clothing = []
        
        for label in labels:
            label_name = label.get('Name', '').lower()
            confidence = float(label.get('Confidence', 0))
            
            # Check if it's a clothing item (use module-level constant)
            for clothing_keyword in CLOTHING_LABELS:
                if clothing_keyword in label_name:
                    clothing_found = True
                    detected_clothing.append(f"{label.get('Name')} ({confidence:.1f}%)")
                    if confidence > max_clothing_confidence:
                        max_clothing_confidence = confidence
                    break
        
        # If clothing found with sufficient confidence, accept
        if clothing_found and max_clothing_confidence >= REKOGNITION_MIN_CONFIDENCE:
            logger.info(f"Image accepted: Clothing detected with {max_clothing_confidence:.1f}% confidence")
            return True, None
        
        # Check for non-clothing labels with high confidence
        for label in labels:
            label_name = label.get('Name', '').lower()
            confidence = float(label.get('Confidence', 0))
            
            for non_clothing_keyword in NON_CLOTHING_LABELS:
                if non_clothing_keyword in label_name and confidence >= REKOGNITION_NON_CLOTHING_MIN_CONFIDENCE:
                    top_labels = [f"{l.get('Name')} ({l.get('Confidence', 0):.1f}%)" for l in labels[:3]]
                    logger.info(f"Image rejected: Non-clothing detected ({non_clothing_keyword} at {confidence:.1f}%)")
                    return False, f"Image does not appear to contain clothing. Detected: {', '.join(top_labels)}. Please upload an image of a clothing item."
        
        # No clothing found
        top_labels = [f"{l.get('Name')} ({l.get('Confidence', 0):.1f}%)" for l in labels[:3]]
        logger.info(f"Image rejected: No clothing detected. Top labels: {', '.join(top_labels)}")
        return False, f"No clothing items detected in the image. Detected: {', '.join(top_labels)}. Please upload an image of a clothing item."
        
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        error_message = e.response.get('Error', {}).get('Message', '')
        logger.error(f"AWS Rekognition ClientError: {error_code} - {error_message}")
        
        # Sanitize error messages for user display
        if error_code in ['InvalidParameterException', 'ImageTooLargeException']:
            return False, "Image file is invalid or too large. Please try a different image."
        elif error_code in ['InvalidS3ObjectException', 'InvalidImageFormatException']:
            return False, "Invalid image format. Please upload a valid image file (JPG, PNG, etc.)."
        elif error_code in ['AccessDeniedException', 'InvalidAccessKeyId', 'SignatureDoesNotMatch']:
            return False, "Image validation service authentication error. Please contact administrator."
        else:
            return False, sanitize_error_message(e, "AWS Rekognition")
            
    except BotoCoreError as e:
        logger.error(f"AWS BotoCoreError: {e}")
        return False, sanitize_error_message(e, "AWS")
    except Exception as e:
        logger.exception(f"Unexpected error during image validation: {e}")
        return False, sanitize_error_message(e, "Image validation")

