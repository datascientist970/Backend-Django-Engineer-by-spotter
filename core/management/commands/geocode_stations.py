"""
Management command to geocode stations without coordinates.
"""

import logging
import time
from django.core.management.base import BaseCommand
from django.db.models import Q
from core.models import FuelStation
from core.services.geocoding import GeocodingService

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Geocode fuel stations without coordinates'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--limit',
            type=int,
            default=50,
            help='Maximum number of stations to geocode (default: 50)'
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Geocode all stations (may take a very long time due to rate limiting)'
        )
        parser.add_argument(
            '--rate-limit',
            type=float,
            default=1.0,
            help='Seconds between API requests (default: 1.0)'
        )
        parser.add_argument(
            '--state',
            type=str,
            help='Geocode stations only in a specific state (e.g., CA)'
        )
    
    def handle(self, *args, **options):
        limit = options['limit']
        geocode_all = options['all']
        rate_limit = options['rate_limit']
        state_filter = options.get('state')
        
        # US states list
        us_states = ['AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA', 
                    'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD', 
                    'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ', 
                    'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC', 
                    'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY']
        
        # Build query for ungeocoded US stations
        query = Q(latitude__isnull=True) & Q(state__in=us_states)
        
        if state_filter:
            state_upper = state_filter.upper()
            if state_upper not in us_states:
                self.stdout.write(self.style.ERROR(f"Invalid state: {state_filter}"))
                return
            query &= Q(state=state_upper)
            self.stdout.write(f"Filtering to state: {state_upper}")
        
        ungeocoded = FuelStation.objects.filter(query)
        total_ungeocoded = ungeocoded.count()
        
        if total_ungeocoded == 0:
            self.stdout.write(self.style.SUCCESS("All stations have coordinates!"))
            return
        
        self.stdout.write(f"Found {total_ungeocoded} stations without coordinates")
        
        if not geocode_all:
            limit = min(limit, total_ungeocoded)
            ungeocoded = ungeocoded[:limit]
        
        self.stdout.write(f"Geocoding {ungeocoded.count()} stations...")
        self.stdout.write(f"Rate limit: {rate_limit} second(s) between requests")
        
        estimated_time = ungeocoded.count() * rate_limit
        if estimated_time > 60:
            self.stdout.write(f"Estimated time: {estimated_time/60:.1f} minutes")
        else:
            self.stdout.write(f"Estimated time: {estimated_time:.0f} seconds")
        
        self.stdout.write("\nPress Ctrl+C to cancel...\n")
        
        geocoded_count = 0
        failed_count = 0
        skipped_count = 0
        
        for i, station in enumerate(ungeocoded, 1):
            try:
                # Progress indicator
                if i % 10 == 0:
                    percent = int(i / ungeocoded.count() * 100)
                    self.stdout.write(f"  Progress: {i}/{ungeocoded.count()} ({percent}%)")
                
                # Construct address - try different formats
                address_formats = [
                    f"{station.address}, {station.city}, {station.state}, USA",
                    f"{station.address}, {station.city}, {station.state}",
                    f"{station.city}, {station.state}, USA",
                ]
                
                lat = None
                lng = None
                last_error = None
                
                for address in address_formats:
                    try:
                        lat, lng = GeocodingService.geocode(address)
                        break
                    except Exception as e:
                        last_error = e
                        continue
                
                if lat is not None and lng is not None:
                    station.latitude = lat
                    station.longitude = lng
                    station.save()
                    geocoded_count += 1
                    
                    if geocoded_count % 5 == 0:
                        self.stdout.write(f"  ✓ Geocoded {geocoded_count} stations so far")
                else:
                    raise ValueError(f"Could not geocode after trying multiple formats: {last_error}")
                
                # Rate limiting
                if i < ungeocoded.count():
                    time.sleep(rate_limit)
                
            except KeyboardInterrupt:
                self.stdout.write(self.style.WARNING("\n\nCancelled by user"))
                break
                
            except Exception as e:
                error_msg = str(e)
                if '429' in error_msg or 'Too many requests' in error_msg:
                    self.stdout.write(self.style.WARNING(f"  ⚠ Rate limited, waiting 10 seconds..."))
                    time.sleep(10)
                    # Retry the same station
                    i -= 1
                    continue
                elif 'Canada' in error_msg:
                    skipped_count += 1
                    self.stdout.write(f"  ⚠ Skipped (Canada): {station.name[:30]}...")
                else:
                    failed_count += 1
                    if failed_count <= 5:  # Only show first 5 errors
                        self.stdout.write(self.style.ERROR(f"  ✗ Failed: {station.name[:30]}... - {error_msg[:50]}"))
                    logger.warning(f"Failed to geocode station {station.opis_id}: {e}")
        
        # Summary
        remaining = FuelStation.objects.filter(latitude__isnull=True, state__in=us_states).count()
        
        self.stdout.write(self.style.SUCCESS(
            f"\n{'='*50}\n"
            f"GEOCODING COMPLETED!\n"
            f"{'='*50}\n"
            f"  - Successfully geocoded: {geocoded_count}\n"
            f"  - Failed: {failed_count}\n"
            f"  - Skipped: {skipped_count}\n"
            f"  - Remaining ungeocoded: {remaining}\n"
            f"{'='*50}"
        ))
        
        if remaining > 0:
            self.stdout.write(f"\nTo geocode more stations, run:")
            self.stdout.write(f"  python manage.py geocode_stations --limit {min(remaining, 100)}")
            
            if state_filter:
                self.stdout.write(f"  python manage.py geocode_stations --state {state_filter} --limit {min(remaining, 100)}")