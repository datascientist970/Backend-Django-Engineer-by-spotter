from django.db import models


class FuelStation(models.Model):
    """Model representing a fuel station with price data."""
    
    opis_id = models.IntegerField(
        unique=True,
        db_index=True,
        help_text="OPIS Truckstop ID"
    )
    name = models.CharField(max_length=255, db_index=True)
    address = models.CharField(max_length=255)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=2, db_index=True)
    rack_id = models.IntegerField()
    retail_price = models.DecimalField(
        max_digits=8,
        decimal_places=4,
        db_index=True,
        help_text="Price per gallon in USD"
    )
    latitude = models.FloatField(null=True, blank=True, db_index=True)
    longitude = models.FloatField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['state', 'city']),
            models.Index(fields=['latitude', 'longitude']),
        ]
        ordering = ['state', 'city', 'name']

    def __str__(self):
        return f"{self.name} - {self.city}, {self.state} (${self.retail_price}/gal)"

    def to_dict(self):
        """Convert to dictionary for API responses."""
        return {
            'id': self.opis_id,
            'name': self.name,
            'address': self.address,
            'city': self.city,
            'state': self.state,
            'price': float(self.retail_price),
            'latitude': self.latitude,
            'longitude': self.longitude,
        }


class CachedGeocode(models.Model):
    """Cache for geocoding results."""
    
    address = models.TextField(unique=True, db_index=True)
    latitude = models.FloatField()
    longitude = models.FloatField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['address']),
        ]

    def __str__(self):
        return f"{self.address[:50]} → ({self.latitude}, {self.longitude})"


class CachedRoute(models.Model):
    """Cache for route responses to minimize external API calls."""
    
    start_address = models.TextField(db_index=True)
    end_address = models.TextField(db_index=True)
    start_coords = models.CharField(max_length=100)
    end_coords = models.CharField(max_length=100)
    route_data = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['start_address', 'end_address']
        indexes = [
            models.Index(fields=['start_address', 'end_address']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"Route: {self.start_address[:30]} → {self.end_address[:30]}"