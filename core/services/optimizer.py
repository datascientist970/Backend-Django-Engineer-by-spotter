"""
Fuel optimization algorithm using greedy approach with lookahead.
"""

import logging
from typing import Dict, List, Tuple, Optional
from math import ceil
from django.conf import settings
from django.db.models import Q
from core.models import FuelStation
from core.services.routing import RoutingService

logger = logging.getLogger(__name__)


class FuelOptimizer:
    """
    Optimizes fuel stops along a route using greedy with lookahead.
    
    Algorithm:
    1. Find all fuel stations within search radius of the route
    2. Sort stations by distance along the route
    3. Use greedy approach with lookahead:
       - At each station, look ahead to find cheapest station within range
       - If current station is cheapest within range, fill up
       - Otherwise, buy just enough to reach the cheaper station
    """
    
    def __init__(self, max_range: int = None, mpg: int = None):
        self.max_range = max_range or settings.VEHICLE_MAX_RANGE_MILES
        self.mpg = mpg or settings.VEHICLE_MPG
        self.search_radius = settings.STATION_SEARCH_RADIUS_MILES
        self.gallons_per_mile = 1 / self.mpg
    
    def optimize(self, start: str, end: str, 
                 route_data: Dict) -> Dict:
        """
        Find optimal fuel stops along the route.
        
        Args:
            start: Start location string
            end: End location string
            route_data: Route data from RoutingService
            
        Returns:
            Dict with:
                - stops: List of fuel stop details
                - total_cost: Total fuel cost
                - total_gallons: Total fuel purchased
                - stops_count: Number of fuel stops
        """
        route_coords = route_data.get('coordinates', [])
        if not route_coords:
            raise ValueError("Route has no coordinates")
        
        total_distance = route_data.get('distance', 0)
        
        # Get all stations near the route
        all_stations = self._find_stations_near_route(route_coords)
        
        if not all_stations:
            logger.warning("No fuel stations found near the route")
            return {
                'stops': [],
                'total_cost': 0,
                'total_gallons': 0,
                'stops_count': 0,
                'warning': 'No fuel stations found along the route. Please try a different route.'
            }
        
        # Sort stations by distance along the route
        stations_with_position = self._sort_stations_by_route_position(
            all_stations, route_coords
        )
        
        # Run optimization algorithm
        stops, total_cost, total_gallons = self._optimize_stops(
            stations_with_position, total_distance, route_coords
        )
        
        return {
            'stops': stops,
            'total_cost': round(total_cost, 2),
            'total_gallons': round(total_gallons, 2),
            'stops_count': len(stops),
            'warning': None
        }
    
    def _find_stations_near_route(self, route_coords: List[Tuple[float, float]]) -> List[FuelStation]:
        """Find all fuel stations within search radius of the route."""
        if not route_coords:
            return []
        
        # Get all stations
        all_stations = list(FuelStation.objects.filter(
            latitude__isnull=False,
            longitude__isnull=False
        ))
        
        if not all_stations:
            return []
        
        # Filter stations near the route
        stations_near_route = []
        for station in all_stations:
            # Find distance to route
            _, _, distance = RoutingService.find_nearest_point_on_route(
                station.latitude,
                station.longitude,
                route_coords
            )
            
            if distance <= self.search_radius:
                station.distance_to_route = distance
                stations_near_route.append(station)
        
        logger.info(f"Found {len(stations_near_route)} stations near route")
        return stations_near_route
    
    def _sort_stations_by_route_position(self, stations: List[FuelStation],
                                         route_coords: List[Tuple[float, float]]) -> List[Dict]:
        """Sort stations by their position along the route."""
        stations_with_position = []
        
        # Calculate cumulative distance along route for each station
        cumulative_distances = self._calculate_cumulative_distances(route_coords)
        
        for station in stations:
            # Find closest point on route
            closest_lat, closest_lng, min_dist = RoutingService.find_nearest_point_on_route(
                station.latitude,
                station.longitude,
                route_coords
            )
            
            # Find position along route
            position = self._find_position_on_route(
                closest_lat, closest_lng, route_coords, cumulative_distances
            )
            
            stations_with_position.append({
                'station': station,
                'position': position,
                'distance_to_route': min_dist,
                'closest_lat': closest_lat,
                'closest_lng': closest_lng,
            })
        
        # Sort by position along route
        stations_with_position.sort(key=lambda x: x['position'])
        
        return stations_with_position
    
    def _calculate_cumulative_distances(self, route_coords: List[Tuple[float, float]]) -> List[float]:
        """Calculate cumulative distance along route."""
        distances = [0.0]
        total = 0.0
        
        for i in range(1, len(route_coords)):
            lat1, lng1 = route_coords[i-1]
            lat2, lng2 = route_coords[i]
            dist = RoutingService.haversine_distance(lat1, lng1, lat2, lng2)
            total += dist
            distances.append(total)
        
        return distances
    
    def _find_position_on_route(self, lat: float, lng: float,
                                route_coords: List[Tuple[float, float]],
                                cumulative_distances: List[float]) -> float:
        """Find the position (distance from start) of a point on the route."""
        # Find nearest point on route
        min_dist = float('inf')
        best_index = 0
        
        for i, (rlat, rlng) in enumerate(route_coords):
            dist = RoutingService.haversine_distance(lat, lng, rlat, rlng)
            if dist < min_dist:
                min_dist = dist
                best_index = i
        
        return cumulative_distances[best_index] if best_index < len(cumulative_distances) else 0
    
    def _optimize_stops(self, stations_with_position: List[Dict],
                        total_distance: float,
                        route_coords: List[Tuple[float, float]]) -> Tuple[List[Dict], float, float]:
        """
        Optimize fuel stops using greedy with lookahead.
        
        Returns:
            Tuple of (stops, total_cost, total_gallons)
        """
        stops = []
        total_cost = 0.0
        total_gallons = 0.0
        
        if not stations_with_position:
            return stops, total_cost, total_gallons
        
        current_fuel = self.max_range  # Start with full tank
        current_position = 0.0
        
        # Add a virtual station at the end
        end_station = {
            'station': None,
            'position': total_distance,
            'is_end': True
        }
        stations_with_position.append(end_station)
        
        # Find the first station after start
        active_stations = [s for s in stations_with_position if s['position'] > 5]  # At least 5 miles from start
        
        for i, station_info in enumerate(active_stations):
            if station_info.get('is_end', False):
                # Reached destination
                break
            
            station = station_info['station']
            position = station_info['position']
            price = float(station.retail_price)
            
            # Distance from current position
            distance_to_station = position - current_position
            
            # If we can't reach this station, we have a problem
            if distance_to_station > current_fuel:
                # We should have stopped earlier
                logger.warning(f"Cannot reach station at {position:.1f} miles with {current_fuel:.1f} miles of fuel")
                # Find the last stop and refuel there
                if stops:
                    last_stop = stops[-1]
                    fuel_needed = distance_to_station - current_fuel
                    # Add emergency fuel at last stop
                    total_cost += fuel_needed * last_stop['price']
                    total_gallons += fuel_needed
                    current_fuel = self.max_range
                else:
                    # Cannot reach any station, use all remaining fuel and hope
                    break
            
            # Consume fuel to reach this station
            current_fuel -= distance_to_station
            current_position = position
            
            # Look ahead to find cheaper stations within range
            lookahead_limit = min(len(active_stations), i + 5)
            cheaper_found = False
            cheapest_future_price = price
            
            for j in range(i + 1, lookahead_limit):
                future_station = active_stations[j]
                if future_station.get('is_end', False):
                    # Don't need to buy extra fuel for destination
                    break
                
                future_pos = future_station['position']
                future_price = float(future_station['station'].retail_price)
                
                # Check if we can reach this future station
                distance_to_future = future_pos - position
                if distance_to_future <= self.max_range:
                    if future_price < cheapest_future_price:
                        cheapest_future_price = future_price
                        cheaper_found = True
            
            # Decide how much fuel to buy
            if cheaper_found:
                # Buy just enough to reach the cheaper station
                # But keep a small buffer
                distance_to_cheaper = self._find_distance_to_cheaper_station(
                    active_stations, i, cheapest_future_price
                )
                fuel_needed = distance_to_cheaper - current_fuel + 10  # Add 10 mile buffer
                if fuel_needed > 0:
                    # Cap by tank capacity
                    fuel_needed = min(fuel_needed, self.max_range - current_fuel)
                    if fuel_needed > 0:
                        cost = fuel_needed * price
                        total_cost += cost
                        total_gallons += fuel_needed
                        current_fuel += fuel_needed
                        
                        stops.append({
                            'station_id': station.opis_id,
                            'name': station.name,
                            'address': station.address,
                            'city': station.city,
                            'state': station.state,
                            'price': float(station.retail_price),
                            'latitude': station.latitude,
                            'longitude': station.longitude,
                            'fuel_purchased': round(fuel_needed, 2),
                            'cost': round(cost, 2),
                            'distance_from_start': round(position, 1)
                        })
            else:
                # Current station is the cheapest in range
                # Fill up to max range (but not over tank capacity)
                fuel_needed = self.max_range - current_fuel
                if fuel_needed > 0:
                    cost = fuel_needed * price
                    total_cost += cost
                    total_gallons += fuel_needed
                    current_fuel = self.max_range
                    
                    stops.append({
                        'station_id': station.opis_id,
                        'name': station.name,
                        'address': station.address,
                        'city': station.city,
                        'state': station.state,
                        'price': float(station.retail_price),
                        'latitude': station.latitude,
                        'longitude': station.longitude,
                        'fuel_purchased': round(fuel_needed, 2),
                        'cost': round(cost, 2),
                        'distance_from_start': round(position, 1)
                    })
        
        return stops, total_cost, total_gallons
    
    def _find_distance_to_cheaper_station(self, stations: List[Dict], 
                                          current_index: int, 
                                          cheaper_price: float) -> float:
        """Find the distance to the first cheaper station."""
        current_position = stations[current_index]['position']
        
        for i in range(current_index + 1, len(stations)):
            if stations[i].get('is_end', False):
                break
            station = stations[i]
            if float(station['station'].retail_price) <= cheaper_price:
                distance = station['position'] - current_position
                # Check if it's within range
                if distance <= self.max_range:
                    return distance
        
        # Default: look at next station
        if current_index + 1 < len(stations):
            return stations[current_index + 1]['position'] - current_position
        
        return self.max_range / 2  # Fallback