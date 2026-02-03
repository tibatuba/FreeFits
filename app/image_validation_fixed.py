"""
Image validation module for verifying uploaded images contain clothing items.
Uses Imagga API for image recognition and tagging.
FIXED VERSION: Checks for clothing FIRST before rejecting based on negative keywords
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

# Negative keywords - if these appear in top tags WITHOUT clothing, reject
NON_CLOTHING_KEYWORDS = {
    'house', 'building', 'home', 'residence', 'architecture', 'structure',
    'furniture', 'table', 'chair', 'desk', 'sofa', 'couch', 'bed', 'cabinet',
    'vehicle', 'car', 'truck', 'motorcycle', 'bicycle', 'bike', 'automobile',
    'food', 'meal', 'dish', 'restaurant', 'cooking', 'recipe',
    'animal', 'pet', 'dog', 'cat', 'bird', 'wildlife',
    'landscape', 'nature', 'mountain', 'forest', 'beach', 'ocean', 'sky',
    'electronics', 'computer', 'phone', 'laptop', 'device',
    'appliance', 'refrigerator', 'oven', 'microwave',
    'plant', 'tree', 'flower', 'garden'
    # Note: 'person', 'people', 'group', 'crowd' are NOT in this list
    # because people can wear clothing, so we check for clothing first
}


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

