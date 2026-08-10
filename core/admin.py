"""
Admin configuration for core models.
"""

from django.contrib import admin
from core.models import FuelStation, CachedGeocode, CachedRoute


@admin.register(FuelStation)
class FuelStationAdmin(admin.ModelAdmin):
    list_display = ('name', 'city', 'state', 'retail_price', 'opis_id')
    list_filter = ('state',)
    search_fields = ('name', 'address', 'city', 'state', 'opis_id')
    ordering = ('state', 'city', 'name')


@admin.register(CachedGeocode)
class CachedGeocodeAdmin(admin.ModelAdmin):
    list_display = ('address', 'latitude', 'longitude', 'created_at')
    search_fields = ('address',)
    ordering = ('-created_at',)


@admin.register(CachedRoute)
class CachedRouteAdmin(admin.ModelAdmin):
    list_display = ('start_address', 'end_address', 'created_at')
    search_fields = ('start_address', 'end_address')
    ordering = ('-created_at',)