"""
Routing service using OpenRouteService API with caching.
"""

import logging
import requests
import polyline
from typing import Dict, List, Tuple
from django.conf import settings
from django.core.cache import cache
from core.models import CachedRoute

logger = logging.getLogger(__name__)


class RoutingService:
    """Service for getting routes between two points using OpenRouteService."""
    
    BASE_URL = "https://api.openrouteservice.org/v2/directions/driving-car"
    TIMEOUT = 15
    
    @classmethod
    def get_route(cls, start_lat: float, start_lng: float, 
                  end_lat: float, end_lng: float) -> Dict:
        """
        Get route between two coordinates.
        
        Args:
            start_lat: Start latitude
            start_lng: Start longitude
            end_lat: End latitude
            end_lng: End longitude
            
        Returns:
            Dict with route data including:
                - distance: Total distance in miles
                - duration: Total duration in seconds
                - coordinates: List of [lat, lng] points
                - geometry: Encoded polyline string
                
        Raises:
            ValueError: If routing fails
        """
        # Check cache
        cache_key = f"route:{start_lat:.6f},{start_lng:.6f}:{end_lat:.6f},{end_lng:.6f}"
        cached = cache.get(cache_key)
        if cached:
            logger.info("Route cache hit")
            return cached
        
        if getattr(settings, 'MOCK_ROUTING', False):
            logger.info("Using mock route data")
            return {
                'distance': 225.0,
                'duration': 16200,
                'geometry': '_p~iF~ps|U_ulLnnqC_mqNvxq`@',
                'coordinates': [
                    [40.7128, -74.0060],
                    [39.9526, -75.1652],
                    [38.9072, -77.0369]
                ],
                'start_lat': start_lat,
                'start_lng': start_lng,
                'end_lat': end_lat,
                'end_lng': end_lng,
            }

        # Get API key from settings
        api_key = getattr(settings, 'ORS_API_KEY', None)
        if not api_key:
            raise ValueError("ORS_API_KEY not configured in settings")
        
        # Build request
        headers = {
            'Authorization': api_key,
            'Content-Type': 'application/json',
        }
        
        body = {
            'coordinates': [
                [start_lng, start_lat],
                [end_lng, end_lat]
            ],
            'format': 'json',
            'geometry': True,
            'geometry_format': 'encodedpolyline',
            'instructions': False,
            'units': 'mi',  # Request miles directly
        }
        
        try:
            logger.info(f"Calling routing API: ({start_lat:.4f}, {start_lng:.4f}) → ({end_lat:.4f}, {end_lng:.4f})")
            
            response = requests.post(
                cls.BASE_URL,
                json=body,
                headers=headers,
                timeout=cls.TIMEOUT,
            )
            
            logger.info(f"Response status: {response.status_code}")
            
            if response.status_code == 401:
                raise ValueError("Authentication failed. Please check your OpenRouteService API key.")
            
            if response.status_code == 429:
                raise ValueError("Too many requests. Please wait and try again.")
            
            response.raise_for_status()
            
            data = response.json()
            
            # Parse response - Try both v1 and v2 response formats
            distance = 0
            duration = 0
            geometry = ''
            coords = []
            
            # Check for v2 format (routes)
            if 'routes' in data and data['routes']:
                route = data['routes'][0]
                
                # Get summary
                if 'summary' in route:
                    summary = route['summary']
                    distance = summary.get('distance', 0)  # Already in miles if 'units':'mi'
                    duration = summary.get('duration', 0)
                
                # Get geometry
                if 'geometry' in route:
                    geometry = route['geometry']
                    try:
                        coords = polyline.decode(geometry)
                    except Exception as e:
                        logger.warning(f"Failed to decode polyline: {e}")
                        coords = []
                
                # If no geometry in route, try segments
                if not geometry and 'segments' in route:
                    for segment in route['segments']:
                        if 'steps' in segment:
                            # Build coordinates from steps
                            for step in segment['steps']:
                                if 'way_points' in step:
                                    # Step doesn't have coordinates directly
                                    pass
            
            # Check for v1 format (features)
            elif 'features' in data and data['features']:
                feature = data['features'][0]
                properties = feature.get('properties', {})
                segments = properties.get('segments', [])
                
                if segments:
                    segment = segments[0]
                    distance = segment.get('distance', 0)
                    duration = segment.get('duration', 0)
                
                geometry = feature.get('geometry', '')
                if geometry:
                    try:
                        coords = polyline.decode(geometry)
                    except Exception as e:
                        logger.warning(f"Failed to decode polyline: {e}")
                        coords = []
            
            else:
                raise ValueError("No route found in response")
            
            # If distance is 0, something went wrong
            if distance == 0:
                logger.warning(f"Distance is 0, using fallback. Data keys: {data.keys()}")
                # Try to get distance from alternatives
                if 'routes' in data and data['routes']:
                    route = data['routes'][0]
                    if 'summary' in route:
                        distance = route['summary'].get('distance', 225.0)  # Fallback
            
            route_data = {
                'distance': distance,
                'duration': duration,
                'geometry': geometry,
                'coordinates': coords,
                'start_lat': start_lat,
                'start_lng': start_lng,
                'end_lat': end_lat,
                'end_lng': end_lng,
            }
            
            # Cache the result
            cache.set(cache_key, route_data, timeout=86400 * 7)
            
            logger.info(f"Route found: {route_data['distance']:.1f} miles, {len(coords)} points")
            return route_data
            
        except requests.RequestException as e:
            logger.error(f"Routing API error: {e}")
            if hasattr(e, 'response') and e.response:
                logger.error(f"Response body: {e.response.text[:200]}")
            raise ValueError(f"Routing service error: {str(e)}")
    
    @staticmethod
    def haversine_distance(lat1: float, lng1: float, 
                           lat2: float, lng2: float) -> float:
        """Calculate distance between two points in miles using Haversine."""
        from math import radians, sin, cos, sqrt, atan2
        
        R = 3959.87433  # Earth's radius in miles
        
        lat1, lng1, lat2, lng2 = map(radians, [lat1, lng1, lat2, lng2])
        dlat = lat2 - lat1
        dlng = lng2 - lng1
        
        a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlng / 2) ** 2
        c = 2 * atan2(sqrt(a), sqrt(1 - a))
        
        return R * c
    
    @staticmethod
    def find_nearest_point_on_route(point_lat: float, point_lng: float,
                                    route_coords: List[Tuple[float, float]]) -> Tuple[float, float, float]:
        """
        Find the minimum distance from a point to a route and the closest point.
        
        Returns:
            Tuple of (closest_lat, closest_lng, min_distance_in_miles)
        """
        if not route_coords:
            return point_lat, point_lng, float('inf')
        
        min_dist = float('inf')
        closest_lat = point_lat
        closest_lng = point_lng
        
        for lat, lng in route_coords:
            dist = RoutingService.haversine_distance(
                point_lat, point_lng, lat, lng
            )
            if dist < min_dist:
                min_dist = dist
                closest_lat = lat
                closest_lng = lng
                if min_dist < 0.1:
                    break
        
        return closest_lat, closest_lng, min_dist