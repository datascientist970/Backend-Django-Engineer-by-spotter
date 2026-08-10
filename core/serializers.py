"""
Serializers for API requests and responses.
"""

from rest_framework import serializers


class RouteOptimizeRequestSerializer(serializers.Serializer):
    """Serializer for route optimization request."""
    
    start = serializers.CharField(
        max_length=255,
        help_text="Starting location (address or city, state)"
    )
    finish = serializers.CharField(
        max_length=255,
        help_text="Destination location (address or city, state)"
    )

    def validate(self, data):
        """Validate that locations are in the USA."""
        # Basic validation - can be enhanced
        start = data.get('start', '').strip()
        finish = data.get('finish', '').strip()
        
        if not start:
            raise serializers.ValidationError({"start": "Start location is required"})
        if not finish:
            raise serializers.ValidationError({"finish": "Finish location is required"})
        
        return data


class FuelStopSerializer(serializers.Serializer):
    """Serializer for individual fuel stop."""
    
    station_id = serializers.IntegerField()
    name = serializers.CharField()
    address = serializers.CharField()
    city = serializers.CharField()
    state = serializers.CharField()
    price = serializers.FloatField()
    latitude = serializers.FloatField()
    longitude = serializers.FloatField()
    fuel_purchased = serializers.FloatField(
        help_text="Gallons of fuel purchased"
    )
    cost = serializers.FloatField(
        help_text="Cost of fuel purchased in USD"
    )
    distance_from_start = serializers.FloatField(
        help_text="Distance from start in miles"
    )


class RouteOptimizeResponseSerializer(serializers.Serializer):
    """Serializer for route optimization response."""
    
    start = serializers.CharField()
    finish = serializers.CharField()
    total_distance_miles = serializers.FloatField()
    total_duration_seconds = serializers.FloatField()
    total_fuel_cost = serializers.FloatField()
    total_fuel_gallons = serializers.FloatField()
    fuel_efficiency_mpg = serializers.IntegerField()
    vehicle_range_miles = serializers.IntegerField()
    fuel_stops = FuelStopSerializer(many=True)
    route_geometry = serializers.CharField(
        help_text="Encoded polyline for route visualization"
    )
    route_coordinates = serializers.ListField(
        child=serializers.ListField(
            child=serializers.FloatField()
        ),
        help_text="List of [lat, lng] coordinates"
    )