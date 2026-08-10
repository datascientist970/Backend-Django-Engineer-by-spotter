"""
API Views for fuel optimization.
"""

import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.core.cache import cache
from django.conf import settings

# Import the FuelStation model
from core.models import FuelStation
from core.serializers import (
    RouteOptimizeRequestSerializer,
    RouteOptimizeResponseSerializer,
    FuelStopSerializer
)
from core.services.geocoding import GeocodingService
from core.services.routing import RoutingService
from core.services.optimizer import FuelOptimizer

logger = logging.getLogger(__name__)


class RouteOptimizeView(APIView):
    """API endpoint for optimizing fuel stops along a route."""
    
    def get(self, request):
        """Handle GET requests for testing with query parameters."""
        start = request.query_params.get('start')
        finish = request.query_params.get('finish')
        
        if not start or not finish:
            return Response({
                'error': 'Please provide both "start" and "finish" parameters',
                'example': '/api/optimize/?start=New+York%2C+NY&finish=Washington%2C+DC'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Process the request
        return self._process_optimization(start, finish)
    
    def post(self, request):
        """Handle POST requests with JSON body."""
        serializer = RouteOptimizeRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'error': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        start = serializer.validated_data['start']
        finish = serializer.validated_data['finish']
        
        return self._process_optimization(start, finish)
    
    def _process_optimization(self, start, finish):
        """Shared logic for processing optimization."""
        try:
            logger.info(f"Processing route: {start} → {finish}")
            
            # Check cache first
            cache_key = f"optimize:{start}:{finish}"
            cached_response = cache.get(cache_key)
            if cached_response:
                logger.info(f"Returning cached response for {start} → {finish}")
                return Response(cached_response, status=status.HTTP_200_OK)
            
            # Step 1: Geocode locations
            start_lat, start_lng = GeocodingService.geocode(start + ", USA")
            end_lat, end_lng = GeocodingService.geocode(finish + ", USA")
            
            logger.info(f"Geocoded: ({start_lat}, {start_lng}) → ({end_lat}, {end_lng})")
            
            # Step 2: Get route
            route_data = RoutingService.get_route(
                start_lat, start_lng,
                end_lat, end_lng
            )
            
            logger.info(f"Route found: {route_data['distance']:.1f} miles")
            
            # Step 3: Optimize fuel stops
            optimizer = FuelOptimizer()
            optimization_result = optimizer.optimize(
                start, finish, route_data
            )
            
            logger.info(f"Optimization complete: {optimization_result['stops_count']} stops, ${optimization_result['total_cost']:.2f}")
            
            # Step 4: Build response
            response_data = {
                'start': start,
                'finish': finish,
                'total_distance_miles': round(route_data['distance'], 1),
                'total_duration_seconds': round(route_data['duration']),
                'total_fuel_cost': optimization_result['total_cost'],
                'total_fuel_gallons': optimization_result['total_gallons'],
                'fuel_efficiency_mpg': settings.VEHICLE_MPG,
                'vehicle_range_miles': settings.VEHICLE_MAX_RANGE_MILES,
                'fuel_stops': optimization_result['stops'],
                'route_geometry': route_data.get('geometry', ''),
                'route_coordinates': route_data.get('coordinates', []),
                'stops_count': optimization_result['stops_count'],
                'warning': optimization_result.get('warning'),
            }
            
            # Cache the response
            cache.set(cache_key, response_data, timeout=86400)  # 24 hours
            
            return Response(response_data, status=status.HTTP_200_OK)
            
        except ValueError as e:
            logger.error(f"Optimization error: {e}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Unexpected error: {e}", exc_info=True)
            return Response(
                {'error': f'An unexpected error occurred: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class HealthCheckView(APIView):
    """Health check endpoint."""
    
    def get(self, request):
        try:
            stations_count = FuelStation.objects.count()
            geocoded_count = FuelStation.objects.filter(latitude__isnull=False).count()
            
            return Response({
                'status': 'healthy',
                'stations_count': stations_count,
                'geocoded_stations': geocoded_count,
                'vehicle_max_range': settings.VEHICLE_MAX_RANGE_MILES,
                'vehicle_mpg': settings.VEHICLE_MPG,
                'search_radius_miles': settings.STATION_SEARCH_RADIUS_MILES,
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({
                'status': 'error',
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)