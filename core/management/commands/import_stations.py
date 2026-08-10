"""
Management command to import fuel stations from CSV file.
"""

import csv
import os
import logging
import time
from django.core.management.base import BaseCommand
from django.conf import settings
from core.models import FuelStation

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Import fuel stations from CSV file'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--csv',
            type=str,
            default='fuel-prices-for-be-assessment.csv',
            help='Path to CSV file with fuel station data'
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing stations before import'
        )
        parser.add_argument(
            '--geocode',
            action='store_true',
            help='Geocode stations after import (slow, rate limited)'
        )
        parser.add_argument(
            '--limit-geocode',
            type=int,
            default=50,
            help='Maximum number of stations to geocode (default: 50)'
        )
        parser.add_argument(
            '--skip-geocode',
            action='store_true',
            help='Skip geocoding entirely'
        )
    
    def handle(self, *args, **options):
        csv_path = options['csv']
        clear = options['clear']
        should_geocode = options['geocode']
        limit_geocode = options['limit_geocode']
        skip_geocode = options['skip_geocode']
        
        # Check if file exists in multiple locations
        possible_paths = [
            csv_path,
            os.path.join('data', csv_path),
            os.path.join('data', os.path.basename(csv_path)),
            os.path.join(settings.BASE_DIR, csv_path),
            os.path.join(settings.BASE_DIR, 'data', csv_path),
            os.path.join(settings.BASE_DIR, 'data', os.path.basename(csv_path)),
        ]
        
        found_path = None
        for path in possible_paths:
            if os.path.exists(path):
                found_path = path
                break
        
        if found_path:
            csv_path = found_path
            self.stdout.write(f"Found CSV at: {csv_path}")
        else:
            self.stdout.write(self.style.ERROR("CSV file not found!"))
            self.stdout.write("Checked these locations:")
            for path in possible_paths:
                self.stdout.write(f"  - {path}")
            return
        
        if clear:
            self.stdout.write("Clearing existing stations...")
            count = FuelStation.objects.count()
            FuelStation.objects.all().delete()
            self.stdout.write(f"Deleted {count} stations.")
        
        self.stdout.write(f"Importing stations from {csv_path}...")
        
        try:
            with open(csv_path, 'r', encoding='utf-8') as file:
                # Try to detect the dialect
                sample = file.read(1024)
                file.seek(0)
                dialect = csv.Sniffer().sniff(sample)
                reader = csv.DictReader(file, dialect=dialect)
                
                imported_count = 0
                skipped_count = 0
                updated_count = 0
                
                # Get column names
                fieldnames = reader.fieldnames
                self.stdout.write(f"CSV columns: {fieldnames}")
                
                for row in reader:
                    try:
                        # Parse fields (handle different column names)
                        opis_id = self._get_field(row, ['OPIS Truckstop ID', 'OPIS_Truckstop_ID', 'Truckstop_ID'])
                        name = self._get_field(row, ['Truckstop Name', 'Truckstop_Name', 'Name'])
                        address = self._get_field(row, ['Address', 'Street Address'])
                        city = self._get_field(row, ['City'])
                        state = self._get_field(row, ['State'])
                        rack_id = self._get_field(row, ['Rack ID', 'Rack_ID'])
                        retail_price = self._get_field(row, ['Retail Price', 'Retail_Price', 'Price'])
                        
                        # Skip if missing required fields
                        if not all([opis_id, name, address, city, state, retail_price]):
                            skipped_count += 1
                            continue
                        
                        # Only import US states
                        state_upper = str(state).strip().upper()
                        us_states = ['AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA', 
                                   'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD', 
                                   'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ', 
                                   'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC', 
                                   'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY']
                        
                        if state_upper not in us_states:
                            skipped_count += 1
                            continue
                        
                        # Create or update station
                        station, created = FuelStation.objects.update_or_create(
                            opis_id=int(opis_id),
                            defaults={
                                'name': str(name).strip(),
                                'address': str(address).strip(),
                                'city': str(city).strip(),
                                'state': state_upper,
                                'rack_id': int(rack_id) if rack_id else 0,
                                'retail_price': float(retail_price),
                            }
                        )
                        
                        if created:
                            imported_count += 1
                        else:
                            updated_count += 1
                        
                        # Show progress every 1000 stations
                        if (imported_count + updated_count) % 1000 == 0:
                            self.stdout.write(f"  Processed {imported_count + updated_count} stations...")
                            
                    except Exception as e:
                        logger.warning(f"Error importing row: {e}")
                        skipped_count += 1
                        continue
                
                # Summary
                total_stations = FuelStation.objects.count()
                geocoded_total = FuelStation.objects.filter(latitude__isnull=False).count()
                
                self.stdout.write(self.style.SUCCESS(
                    f"\n{'='*50}\n"
                    f"IMPORT COMPLETED!\n"
                    f"{'='*50}\n"
                    f"  - New stations imported: {imported_count}\n"
                    f"  - Existing stations updated: {updated_count}\n"
                    f"  - Stations skipped: {skipped_count}\n"
                    f"  - Total stations in DB: {total_stations}\n"
                    f"  - Geocoded stations: {geocoded_total}\n"
                    f"{'='*50}"
                ))
                
                # Geocode stations if requested
                if should_geocode and not skip_geocode:
                    self.stdout.write("\nStarting geocoding...")
                    self._geocode_stations(limit_geocode)
                
        except FileNotFoundError:
            self.stdout.write(self.style.ERROR(f"CSV file not found: {csv_path}"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error importing stations: {e}"))
            import traceback
            traceback.print_exc()
    
    def _geocode_stations(self, limit=50):
        """Geocode stations without coordinates."""
        ungeocoded = FuelStation.objects.filter(latitude__isnull=True)
        total_ungeocoded = ungeocoded.count()
        
        if total_ungeocoded == 0:
            self.stdout.write(self.style.SUCCESS("All stations have coordinates!"))
            return
        
        self.stdout.write(f"Found {total_ungeocoded} stations without coordinates")
        
        # Limit the number to geocode
        limit = min(limit, total_ungeocoded)
        ungeocoded = ungeocoded[:limit]
        
        self.stdout.write(f"Geocoding {ungeocoded.count()} stations (this may take a while)...")
        self.stdout.write(f"Note: Nominatim limits requests to 1 per second, so this will take about {limit} seconds")
        
        geocoded_count = 0
        failed_count = 0
        
        for i, station in enumerate(ungeocoded, 1):
            try:
                from core.services.geocoding import GeocodingService
                address = f"{station.address}, {station.city}, {station.state}, USA"
                
                # Progress indicator
                if i % 10 == 0:
                    self.stdout.write(f"  Progress: {i}/{limit} ({int(i/limit*100)}%)")
                
                lat, lng = GeocodingService.geocode(address)
                station.latitude = lat
                station.longitude = lng
                station.save()
                geocoded_count += 1
                
            except Exception as e:
                logger.warning(f"Failed to geocode station {station.opis_id}: {e}")
                failed_count += 1
                # Don't retry immediately for rate limits
                if '429' in str(e) or 'Too many requests' in str(e):
                    self.stdout.write(self.style.WARNING("Rate limited, waiting 5 seconds..."))
                    time.sleep(5)
        
        self.stdout.write(self.style.SUCCESS(
            f"\nGeocoding completed!\n"
            f"  - Successfully geocoded: {geocoded_count}\n"
            f"  - Failed: {failed_count}\n"
            f"  - Remaining ungeocoded: {total_ungeocoded - geocoded_count}"
        ))
    
    def _get_field(self, row, field_names):
        """Get value from row using multiple possible field names."""
        for field in field_names:
            if field in row:
                value = row[field]
                if value and str(value).strip():
                    return str(value).strip()
        return None