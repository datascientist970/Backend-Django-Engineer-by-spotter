# 🚛 Fuel Optimization API

A Django-based REST API that optimizes fuel stops along a route in the USA, finding the most cost-effective fuel stations based on real-time prices.

## 📋 Table of Contents
- [Features](#-features)
- [Tech Stack](#-tech-stack)
- [Prerequisites](#-prerequisites)
- [Installation](#-installation)
- [Database Setup](#-database-setup)
- [Import Fuel Stations](#-import-fuel-stations)
- [Geocode Stations](#-geocode-stations)
- [Run the Server](#-run-the-server)
- [API Endpoints](#-api-endpoints)
- [Testing with Postman](#-testing-with-postman)
- [Expected Response](#-expected-response)
- [Troubleshooting](#-troubleshooting)
- [Project Demo](#-project-demo)

## ✨ Features

- **Route Optimization**: Find optimal fuel stops along any route in the USA
- **Cost-Effective**: Algorithm considers fuel prices to minimize total cost
- **Vehicle Constraints**: 500-mile range with 10 MPG fuel efficiency
- **Multiple Fuel Stops**: Automatically calculates multiple stops for long routes
- **Fast Response**: Uses caching for geocoding and routing to minimize API calls
- **Clean Architecture**: Well-structured Django code with services layer
- **Error Handling**: Comprehensive error handling with meaningful messages

## 🛠️ Tech Stack

- **Backend**: Django 4.2.7, Django REST Framework 3.14
- **APIs**: OpenRouteService (routing), Nominatim (geocoding)
- **Database**: SQLite3 (with spatial support)
- **Caching**: Django Cache Framework
- **Additional**: Python 3.10+, polyline, requests

## 📦 Prerequisites

- Python 3.10 or higher
- pip (Python package manager)
- Git
- Postman (for API testing)
- OpenRouteService API Key (free)

### Get OpenRouteService API Key
1. Go to [OpenRouteService Sign Up](https://openrouteservice.org/sign-up/)
2. Create a free account
3. Navigate to [Developer Dashboard](https://openrouteservice.org/dev/#/home)
4. Click "Create new token"
5. Copy your API key

## 🚀 Installation

### 1. Clone the Repository
```bash
git clone https://github.com/yourusername/fuel-optimizer.git
cd fuel-optimizer
```

### 2. Create Virtual Environment
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Mac/Linux
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure API Keys
Open `assessment/settings.py` and update:
```python
ORS_API_KEY = 'your_openrouteservice_api_key_here'
```

### 5. Apply Migrations
```bash
python manage.py makemigrations
python manage.py migrate
python manage.py createcachetable
```

## 💾 Database Setup

### Import Fuel Stations
```bash
python manage.py import_stations --csv data/fuel-prices-for-be-assessment.csv --clear --skip-geocode
```

**Expected Output:**
```
Found CSV at: data/fuel-prices-for-be-assessment.csv
Importing stations from data/fuel-prices-for-be-assessment.csv...
  Processed 1000 stations...
  Processed 2000 stations...
  Processed 3000 stations...
  
==================================================
IMPORT COMPLETED!
==================================================
  - New stations imported: 8500
  - Existing stations updated: 0
  - Skipped (missing data): 0
  - Skipped (Canadian): 250
  - Skipped (non-US): 0
  - Total US stations in DB: 8500
  - Geocoded stations: 0
==================================================
```

### Check Database Status
```bash
python manage.py shell -c "from core.models import FuelStation; total=FuelStation.objects.count(); geocoded=FuelStation.objects.filter(latitude__isnull=False).count(); ungeocoded=FuelStation.objects.filter(latitude__isnull=True).count(); print(f'Total: {total}, Geocoded: {geocoded}, Ungeocoded: {ungeocoded}')"
```

## 🌍 Geocode Stations

### Geocode in Batches
```bash
# First batch of 50 stations
python manage.py geocode_stations --limit 50

# Geocode more stations
python manage.py geocode_stations --limit 100

# Geocode by state
python manage.py geocode_stations --state CA --limit 100
python manage.py geocode_stations --state NY --limit 50
python manage.py geocode_stations --state PA --limit 50
```

### Geocode All Stations (May take time)
```bash
python manage.py geocode_stations --all
```

### Check Geocoding Progress
```bash
python manage.py shell -c "from core.models import FuelStation; total=FuelStation.objects.count(); geocoded=FuelStation.objects.filter(latitude__isnull=False).count(); ungeocoded=FuelStation.objects.filter(latitude__isnull=True).count(); print(f'Total: {total}, Geocoded: {geocoded}, Ungeocoded: {ungeocoded}')"
```

## 🏃 Run the Server

```bash
python manage.py runserver
```

Server will start at: `http://127.0.0.1:8000/`

## 🔗 API Endpoints

### 1. Health Check
**GET** `/api/health/`

**Response:**
```json
{
    "status": "healthy",
    "stations_count": 8500,
    "geocoded_stations": 150,
    "vehicle_max_range": 500,
    "vehicle_mpg": 10,
    "search_radius_miles": 10
}
```

### 2. Optimize Route
**POST** `/api/optimize/`

**Request Body:**
```json
{
    "start": "New York, NY",
    "finish": "Washington, DC"
}
```

**GET Method (Browser Testing):**
```
http://127.0.0.1:8000/api/optimize/?start=New%20York,%20NY&finish=Washington,%20DC
```

## 📮 Testing with Postman

### Setup Postman Request
1. **Method**: POST
2. **URL**: `http://127.0.0.1:8000/api/optimize/`
3. **Headers**: 
   - `Content-Type: application/json`
4. **Body**: raw JSON

### Test Cases

#### Short Route
```json
{
    "start": "New York, NY",
    "finish": "Washington, DC"
}
```

#### Medium Route
```json
{
    "start": "Chicago, IL",
    "finish": "Denver, CO"
}
```

#### Long Route
```json
{
    "start": "New York, NY",
    "finish": "Los Angeles, CA"
}
```

#### Cross-Country
```json
{
    "start": "Miami, FL",
    "finish": "Seattle, WA"
}
```

#### Same State
```json
{
    "start": "San Francisco, CA",
    "finish": "Los Angeles, CA"
}
```

## 📊 Expected Response

### Success Response
```json
{
    "start": "New York, NY",
    "finish": "Washington, DC",
    "total_distance_miles": 225.0,
    "total_duration_seconds": 16200,
    "total_fuel_cost": 78.73,
    "total_fuel_gallons": 22.5,
    "fuel_efficiency_mpg": 10,
    "vehicle_range_miles": 500,
    "fuel_stops": [
        {
            "station_id": 12345,
            "name": "Pilot Travel Center",
            "address": "1000 I-95 Frontage Rd",
            "city": "Philadelphia",
            "state": "PA",
            "price": 3.499,
            "latitude": 39.9526,
            "longitude": -75.1652,
            "fuel_purchased": 22.5,
            "cost": 78.73,
            "distance_from_start": 125.0
        }
    ],
    "route_geometry": "_p~iF~ps|U_ulLnnqC_mqNvxq`@",
    "route_coordinates": [
        [40.7128, -74.006],
        [39.9526, -75.1652],
        [38.9072, -77.0369]
    ],
    "stops_count": 1,
    "warning": null
}
```

### No Stations Found Response
```json
{
    "start": "New York, NY",
    "finish": "Washington, DC",
    "total_distance_miles": 225.0,
    "total_duration_seconds": 16200,
    "total_fuel_cost": 0,
    "total_fuel_gallons": 0,
    "fuel_efficiency_mpg": 10,
    "vehicle_range_miles": 500,
    "fuel_stops": [],
    "route_geometry": "_p~iF~ps|U_ulLnnqC_mqNvxq`@",
    "route_coordinates": [
        [40.7128, -74.006],
        [39.9526, -75.1652],
        [38.9072, -77.0369]
    ],
    "stops_count": 0,
    "warning": "No fuel stations found along the route. Please try a different route."
}
```

## 🔧 Troubleshooting

### 1. API Key Issues
**Error**: `401 Client Error: Unauthorized`
**Solution**: 
```bash
# Check your API key in settings.py
# ORS_API_KEY = 'your_valid_api_key_here'
```

### 2. Rate Limiting
**Error**: `429 Too Many Requests`
**Solution**:
```bash
# Wait 5 minutes and try again with smaller batch
python manage.py geocode_stations --limit 20
```

### 3. No Stations Found
**Issue**: API returns empty fuel_stops
**Solution**:
```bash
# Geocode more stations along the route
python manage.py geocode_stations --state PA --limit 100
python manage.py geocode_stations --state MD --limit 100
```

### 4. Geocoding Fails
**Issue**: Stations not geocoding
**Solution**:
```bash
# Check if Nominatim is reachable
# Wait and retry with smaller batch
python manage.py geocode_stations --limit 10
```

### 5. Import Issues
**Issue**: CSV file not found
**Solution**:
```bash
# Make sure CSV is in correct location
# Check: data/fuel-prices-for-be-assessment.csv
# Or use full path
python manage.py import_stations --csv /path/to/your/file.csv
```

### 6. Caching Issues
**Issue**: Old data being returned
**Solution**:
```bash
# Clear cache
python manage.py shell -c "from django.core.cache import cache; cache.clear()"
```

## 📝 Helpful Commands

### Check Database Status
```bash
python manage.py shell -c "from core.models import FuelStation; total=FuelStation.objects.count(); geocoded=FuelStation.objects.filter(latitude__isnull=False).count(); print(f'Total: {total}, Geocoded: {geocoded}')"
```

### Stations by State
```bash
python manage.py shell -c "from core.models import FuelStation; from django.db.models import Count; states=FuelStation.objects.values('state').annotate(count=Count('id')).order_by('-count'); print('Stations by state:'); [print(f'{s[\"state\"]}: {s[\"count\"]}') for s in states[:10]]"
```

### Clear All Stations
```bash
python manage.py import_stations --clear
```

### Create Superuser (Admin Panel)
```bash
python manage.py createsuperuser
```

### Admin Panel URL
```
http://127.0.0.1:8000/admin/
```

## 🎯 Quick Demo Script

### Terminal Commands
```bash
# 1. Setup
venv\Scripts\activate
python manage.py migrate
python manage.py createcachetable

# 2. Import Data
python manage.py import_stations --csv data/fuel-prices-for-be-assessment.csv --clear --skip-geocode

# 3. Geocode Stations
python manage.py geocode_stations --limit 50
python manage.py geocode_stations --state PA --limit 50

# 4. Run Server
python manage.py runserver
```

### Browser URLs
```
http://127.0.0.1:8000/api/health/
http://127.0.0.1:8000/api/optimize/?start=New%20York,%20NY&finish=Washington,%20DC
```

### Postman Test
```
POST http://127.0.0.1:8000/api/optimize/
{
    "start": "New York, NY",
    "finish": "Washington, DC"
}
```

## 🎬 Project Demo
https://www.loom.com/share/f3dc9ddc9cf04d218bc62865b3146bac

The demo covers:
1. Project setup and installation
2. Data import and geocoding
3. API testing with Postman
4. Code walkthrough
5. Performance demonstration

## 📝 License

This project is for assessment purposes only.


