"""
Geocoding service using Nominatim (OpenStreetMap) with caching and rate limiting.
"""

import logging
import time
import requests
from django.core.cache import cache
from django.conf import settings
from core.models import CachedGeocode

logger = logging.getLogger(__name__)


class GeocodingService:
    """Service for geocoding addresses to coordinates with caching and rate limiting."""
    
    BASE_URL = "https://nominatim.openstreetmap.org/search"
    TIMEOUT = 10
    _last_request_time = 0
    _min_request_interval = 1.0  # 1 second between requests (respecting Nominatim policy)
    
    @classmethod
    def geocode(cls, address: str, retry_count: int = 0) -> tuple:
        """
        Geocode an address to (latitude, longitude) with rate limiting.
        
        Args:
            address: Address string to geocode
            retry_count: Number of retries attempted
            
        Returns:
            Tuple of (latitude, longitude)
            
        Raises:
            ValueError: If geocoding fails
        """
        if not address:
            raise ValueError("Address cannot be empty")
        
        address = address.strip()
        
        # Skip Canadian addresses (only geocode US)
        if address.endswith(', AB, USA') or address.endswith(', BC, USA') or \
           address.endswith(', ON, USA') or address.endswith(', QC, USA') or \
           address.endswith(', MB, USA') or address.endswith(', SK, USA'):
            raise ValueError(f"Skipping Canadian address: {address}")
        
        # Check Django cache first (fastest)
        cache_key = f"geocode:{address}"
        cached_result = cache.get(cache_key)
        if cached_result:
            logger.info(f"Geocode cache hit: {address[:50]}")
            return cached_result['lat'], cached_result['lng']
        
        # Check database cache
        cached = cls._get_cached(address)
        if cached:
            logger.info(f"Geocode DB cache hit: {address[:50]}")
            cache.set(cache_key, {'lat': cached.latitude, 'lng': cached.longitude}, timeout=86400*7)
            return cached.latitude, cached.longitude
        
        # Rate limiting - respect Nominatim's usage policy
        current_time = time.time()
        time_since_last = current_time - cls._last_request_time
        if time_since_last < cls._min_request_interval:
            time.sleep(cls._min_request_interval - time_since_last)
        
        # Call external API
        try:
            logger.info(f"Geocoding: {address[:50]}")
            cls._last_request_time = time.time()
            
            response = requests.get(
                cls.BASE_URL,
                params={
                    'q': address,
                    'format': 'json',
                    'limit': 1,
                    'addressdetails': 1,
                    'countrycodes': 'us',  # Only US addresses
                },
                headers={
                    'User-Agent': settings.NOMINATIM_USER_AGENT,
                },
                timeout=cls.TIMEOUT,
            )
            
            if response.status_code == 429:  # Too many requests
                if retry_count < 3:
                    wait_time = (retry_count + 1) * 5  # Exponential backoff
                    logger.warning(f"Rate limited, waiting {wait_time} seconds...")
                    time.sleep(wait_time)
                    return cls.geocode(address, retry_count + 1)
                else:
                    raise ValueError(f"Rate limited after {retry_count} retries")
            
            response.raise_for_status()
            
            data = response.json()
            if not data:
                raise ValueError(f"Address not found: {address}")
            
            lat = float(data[0]['lat'])
            lng = float(data[0]['lon'])
            
            # Validate US location
            display_name = data[0].get('display_name', '').lower()
            if 'canada' in display_name or 'canada' in address.lower():
                raise ValueError(f"Address is in Canada, not USA: {address}")
            
            # Cache results
            cls._save_cache(address, lat, lng)
            cache.set(cache_key, {'lat': lat, 'lng': lng}, timeout=86400 * 7)
            
            logger.info(f"Geocoded: {address[:50]} → ({lat:.4f}, {lng:.4f})")
            return lat, lng
            
        except requests.RequestException as e:
            logger.error(f"Geocoding API error for {address}: {e}")
            if retry_count < 3:
                time.sleep(2)
                return cls.geocode(address, retry_count + 1)
            raise ValueError(f"Geocoding service error: {str(e)}")
    
    @classmethod
    def _get_cached(cls, address: str):
        """Get cached geocode from database."""
        try:
            return CachedGeocode.objects.get(address=address)
        except CachedGeocode.DoesNotExist:
            return None
    
    @classmethod
    def _save_cache(cls, address: str, lat: float, lng: float):
        """Save geocode to database cache."""
        try:
            CachedGeocode.objects.update_or_create(
                address=address,
                defaults={'latitude': lat, 'longitude': lng}
            )
        except Exception as e:
            logger.warning(f"Failed to save geocode cache: {e}")