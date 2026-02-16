"""
Geocoding utilities: address/location to coordinates.
Uses Google Geocoding API, restricted to Canada (components=country:CA).
Requires GOOGLE_PLACES_API_KEY in environment (same key as Places API).
"""
import os
import re
import time
from typing import Optional, Tuple

import requests

# Rate limiting: avoid bursting Google API
_last_request_time = 0
_min_request_interval = 0.05  # 50ms between requests

# Canada-only component for all requests
_COMPONENTS_CA = "country:CA"

def _get_api_key() -> str:
    return (os.getenv("GOOGLE_PLACES_API_KEY") or "").strip()

def _rate_limit():
    global _last_request_time
    now = time.time()
    elapsed = now - _last_request_time
    if elapsed < _min_request_interval:
        time.sleep(_min_request_interval - elapsed)
    _last_request_time = time.time()

def geocode_postal_code(postal_code: str, country_code: str = None) -> Optional[Tuple[float, float]]:
    """
    Convert a postal code to (latitude, longitude). Canada-only.
    """
    key = _get_api_key()
    if not key:
        return None

    _rate_limit()
    query = postal_code.strip()
    if not query:
        return None

    try:
        url = "https://maps.googleapis.com/maps/api/geocode/json"
        params = {
            "address": query,
            "components": _COMPONENTS_CA,
            "key": key,
        }
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") != "OK" or not data.get("results"):
            return None
        loc = data["results"][0]["geometry"]["location"]
        return (float(loc["lat"]), float(loc["lng"]))
    except Exception as e:
        print(f"Geocoding error for '{postal_code}': {e}")
        return None

def geocode_location(location: str) -> Optional[Tuple[float, float, str]]:
    """
    Convert a location string (city, address, postal code) to (lat, lon, formatted_address).
    Canada-only. Returns None if no key or no result.
    """
    key = _get_api_key()
    if not key:
        return None

    _rate_limit()
    location = (location or "").strip()
    if not location:
        return None

    try:
        url = "https://maps.googleapis.com/maps/api/geocode/json"
        params = {
            "address": f"{location}, Canada",
            "components": _COMPONENTS_CA,
            "key": key,
        }
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") != "OK" or not data.get("results"):
            return None
        result = data["results"][0]
        loc = result["geometry"]["location"]
        formatted = result.get("formatted_address", location)
        return (float(loc["lat"]), float(loc["lng"]), formatted)
    except Exception as e:
        print(f"Geocoding error for '{location}': {e}")
        return None

def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Distance between two points in km (Haversine).
    """
    from math import radians, sin, cos, sqrt, atan2
    R = 6371.0  # km
    lat1_rad = radians(lat1)
    lon1_rad = radians(lon1)
    lat2_rad = radians(lat2)
    lon2_rad = radians(lon2)
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad
    a = sin(dlat / 2) ** 2 + cos(lat1_rad) * cos(lat2_rad) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return R * c
