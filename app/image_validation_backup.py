"""
Image validation module for verifying uploaded images contain clothing items.
Supports multiple APIs:
1. Imagga API - General image tagging (current implementation)
2. api4ai Fashion API - Specialized clothing detection (alternative, more accurate)
"""

import requests
import base64
import os
from typing import Tuple, Optional


# Clothing-related tags that indicate the image contains clothing
CLOTHING_TAGS = {
    'clothing', 'apparel', 'fashion', 'garment', 'outfit', 'wardrobe',
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
}

# Negative keywords - if these appear in top tags, reject immediately
NON_CLOTHING_KEYWORDS = {
    'house', 'building', 'home', 'residence', 'architecture', 'structure',
    'furniture', 'table', 'chair', 'desk', 'sofa', 'couch', 'bed', 'cabinet',
    'vehicle', 'car', 'truck', 'motorcycle', 'bicycle', 'bike', 'automobile',
    'food', 'meal', 'dish', 'restaurant', 'cooking', 'recipe',
    'animal', 'pet', 'dog', 'cat', 'bird', 'wildlife',
    'landscape', 'nature', 'mountain', 'forest', 'beach', 'ocean', 'sky',
    'electronics', 'computer', 'phone', 'laptop', 'device',
    'appliance', 'refrigerator', 'oven', 'microwave',
    'plant', 'tree', 'flower', 'garden',
    'person', 'people', 'crowd', 'group'  # Only reject if person is main subject without clothing focus
}


def validate_clothing_image(image_path: str, api_key: str, api_secret: str) -> Tuple[bool, Optional[str]]:
    """
    Validate if an uploaded image contains clothing items using Imagga API.
    
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
        # Read image file and encode to base64
        with open(image_path, 'rb') as image_file:
            image_data = image_file.read()
        
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
        all_tag_names = [tag_info.get('tag', {}).get('en', '').lower() for tag_info in tags]
        
        # STEP 1: Check for negative keywords in top tags (reject immediately)
        for tag_info in top_tags:
            tag_name = tag_info.get('tag', {}).get('en', '').lower()
            confidence = float(tag_info.get('confidence', 0))
            
            # If a non-clothing keyword appears with high confidence, reject
            for negative_keyword in NON_CLOTHING_KEYWORDS:
                if negative_keyword in tag_name and confidence >= 30.0:
                    top_tag_names = [t.get('tag', {}).get('en', '') for t in top_tags[:3]]
                    return False, f"Image does not appear to contain clothing. Detected: {', '.join(top_tag_names)}. Please upload an image of a clothing item."
        
        # STEP 2: Check for clothing keywords in top tags only
        # We require clothing to be in the TOP tags, not just anywhere
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
        
        # STEP 3: Strict validation rules
        # Require clothing to be in top 3 tags with at least 40% confidence
        # OR in top 10 with at least 60% confidence
        if clothing_in_top and max_confidence >= 40.0:
            return True, None
        elif clothing_found and max_confidence >= 60.0:
            return True, None
        else:
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


def validate_clothing_image_from_bytes(image_bytes: bytes, api_key: str, api_secret: str) -> Tuple[bool, Optional[str]]:
    """
    Validate if an uploaded image (as bytes) contains clothing items using Imagga API.
    Alternative method that works with in-memory image data.
    
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
        all_tag_names = [tag_info.get('tag', {}).get('en', '').lower() for tag_info in tags]
        
        # STEP 1: Check for negative keywords in top tags (reject immediately)
        for tag_info in top_tags:
            tag_name = tag_info.get('tag', {}).get('en', '').lower()
            confidence = float(tag_info.get('confidence', 0))
            
            # If a non-clothing keyword appears with high confidence, reject
            for negative_keyword in NON_CLOTHING_KEYWORDS:
                if negative_keyword in tag_name and confidence >= 30.0:
                    top_tag_names = [t.get('tag', {}).get('en', '') for t in top_tags[:3]]
                    return False, f"Image does not appear to contain clothing. Detected: {', '.join(top_tag_names)}. Please upload an image of a clothing item."
        
        # STEP 2: Check for clothing keywords in top tags only
        # We require clothing to be in the TOP tags, not just anywhere
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
        
        # STEP 3: Strict validation rules
        # Require clothing to be in top 3 tags with at least 40% confidence
        # OR in top 10 with at least 60% confidence
        if clothing_in_top and max_confidence >= 40.0:
            return True, None
        elif clothing_found and max_confidence >= 60.0:
            return True, None
        else:
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
    
    if not os.path.exists(image_path):
        return False, "Image file not found."
    
    try:
        # Read image file
        with open(image_path, 'rb') as image_file:
            image_data = image_file.read()
        
        # Prepare request to api4ai Fashion API
        url = "https://api4.ai/apis/fashion/v1/results"
        headers = {
            'X-RapidAPI-Key': api_key,
            'X-RapidAPI-Host': 'api4.ai'
        }
        files = {'image': open(image_path, 'rb')}
        
        response = requests.post(url, files=files, headers=headers, timeout=30)
        files['image'].close()
        
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
        
        # api4ai Fashion API returns results in a specific format
        # Check if any clothing items were detected
        if 'results' in data and len(data['results']) > 0:
            # If API returns clothing items, image is valid
            detected_items = []
            for result in data['results']:
                if 'entities' in result:
                    for entity in result['entities']:
                        if 'classes' in entity:
                            for cls in entity['classes']:
                                if 'name' in cls:
                                    detected_items.append(cls['name'])
            
            if detected_items:
                return True, None
            else:
                return False, "No clothing items detected in the image. Please upload an image of a clothing item."
        else:
            return False, "Could not analyze image. Please try a different image."
        
    except requests.exceptions.Timeout:
        return False, "Image validation timed out. Please try again."
    except requests.exceptions.RequestException as e:
        return False, f"Network error during image validation: {str(e)}"
    except Exception as e:
        return False, f"Unexpected error during image validation: {str(e)}"
