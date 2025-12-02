"""
Geocoding utilities for converting postal codes and locations to coordinates.
Uses Nominatim (OpenStreetMap) API - free, no API key required.
"""
import requests
import time
from typing import Optional, Tuple

# Rate limiting: Nominatim allows 1 request per second
_last_request_time = 0
_min_request_interval = 1.0  # seconds

def geocode_postal_code(postal_code: str, country_code: str = None) -> Optional[Tuple[float, float]]:
    """
    Convert a postal code to latitude and longitude coordinates.
    
    Args:
        postal_code: Postal/ZIP code (e.g., "M5H 2N2", "90210")
        country_code: Optional ISO country code (e.g., "CA", "US") to narrow search
    
    Returns:
        Tuple of (latitude, longitude) if found, None otherwise
    """
    global _last_request_time
    
    # Rate limiting
    current_time = time.time()
    time_since_last = current_time - _last_request_time
    if time_since_last < _min_request_interval:
        time.sleep(_min_request_interval - time_since_last)
    _last_request_time = time.time()
    
    try:
        # Build query
        query = postal_code.strip()
        if country_code:
            query = f"{postal_code}, {country_code}"
        
        # Use Nominatim API (OpenStreetMap)
        url = "https://nominatim.openstreetmap.org/search"
        params = {
            "q": query,
            "format": "json",
            "limit": 1,
            "addressdetails": 1
        }
        
        headers = {
            "User-Agent": "FreeFits/1.0"  # Required by Nominatim
        }
        
        response = requests.get(url, params=params, headers=headers, timeout=5)
        response.raise_for_status()
        
        data = response.json()
        if data and len(data) > 0:
            lat = float(data[0]["lat"])
            lon = float(data[0]["lon"])
            return (lat, lon)
        
        return None
    except Exception as e:
        print(f"Geocoding error for '{postal_code}': {e}")
        return None

def geocode_location(location: str) -> Optional[Tuple[float, float, str]]:
    """
    Convert a location string (city, address, postal code) to coordinates.
    
    Args:
        location: Location string (e.g., "Toronto, ON", "M5H 2N2", "New York, NY")
    
    Returns:
        Tuple of (latitude, longitude, formatted_location) if found, None otherwise
    """
    global _last_request_time
    
    print(f"DEBUG GEOCODING: Attempting to geocode '{location}'")
    
    # Rate limiting
    current_time = time.time()
    time_since_last = current_time - _last_request_time
    if time_since_last < _min_request_interval:
        time.sleep(_min_request_interval - time_since_last)
    _last_request_time = time.time()
    
    try:
        # Check if location contains a partial postal code (like "L6M, Oakville, Ontario")
        # Extract city/province for better geocoding
        location_parts = location.split(',')
        city_province = None
        postal_prefix = None
        
        # Look for postal code pattern (3 characters: letter-digit-letter)
        import re
        postal_pattern = re.compile(r'\b([A-Za-z]\d[A-Za-z])\b')
        for part in location_parts:
            part = part.strip()
            if postal_pattern.match(part):
                postal_prefix = part
            elif len(part) > 2 and not postal_pattern.match(part):
                # Likely a city or province name
                if city_province is None:
                    city_province = part
                else:
                    city_province = f"{city_province}, {part}"
        
        # Try geocoding with full location first
        url = "https://nominatim.openstreetmap.org/search"
        params = {
            "q": f"{location.strip()}, Canada",
            "format": "json",
            "limit": 5,
            "addressdetails": 1,
            "countrycodes": "ca"
        }
        
        headers = {
            "User-Agent": "FreeFits/1.0"
        }
        
        print(f"DEBUG GEOCODING: Making request to Nominatim with params: {params}")
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        print(f"DEBUG GEOCODING: Got {len(data) if data else 0} results")
        
        if data and len(data) > 0:
            result = data[0]
            lat = float(result["lat"])
            lon = float(result["lon"])
            # Get formatted display name
            display_name = result.get("display_name", location)
            print(f"DEBUG GEOCODING: Successfully geocoded '{location}' to ({lat}, {lon})")
            return (lat, lon, display_name)
        
        # If that failed and we have city/province, try geocoding just the city
        if city_province and city_province != location.strip():
            print(f"DEBUG GEOCODING: Retrying with city/province only: '{city_province}'")
            params = {
                "q": f"{city_province}, Canada",
                "format": "json",
                "limit": 5,
                "addressdetails": 1,
                "countrycodes": "ca"
            }
            
            # Rate limiting
            current_time = time.time()
            time_since_last = current_time - _last_request_time
            if time_since_last < _min_request_interval:
                time.sleep(_min_request_interval - time_since_last)
            _last_request_time = time.time()
            
            response = requests.get(url, params=params, headers=headers, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            print(f"DEBUG GEOCODING: Got {len(data) if data else 0} results for city/province")
            
            if data and len(data) > 0:
                result = data[0]
                lat = float(result["lat"])
                lon = float(result["lon"])
                display_name = result.get("display_name", location)
                print(f"DEBUG GEOCODING: Successfully geocoded '{city_province}' to ({lat}, {lon})")
                return (lat, lon, display_name)
        
        print(f"DEBUG GEOCODING: No results found for '{location}'")
        return None
    except Exception as e:
        print(f"DEBUG GEOCODING: Error geocoding '{location}': {e}")
        import traceback
        traceback.print_exc()
        return None

def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the distance between two coordinates using the Haversine formula.
    
    Args:
        lat1, lon1: First point coordinates
        lat2, lon2: Second point coordinates
    
    Returns:
        Distance in kilometers
    """
    from math import radians, sin, cos, sqrt, atan2
    
    # Earth's radius in kilometers
    R = 6371.0
    
    # Convert to radians
    lat1_rad = radians(lat1)
    lon1_rad = radians(lon1)
    lat2_rad = radians(lat2)
    lon2_rad = radians(lon2)
    
    # Haversine formula
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad
    
    a = sin(dlat / 2)**2 + cos(lat1_rad) * cos(lat2_rad) * sin(dlon / 2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    
    distance = R * c
    return distance


