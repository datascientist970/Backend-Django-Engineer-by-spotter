# Fuel Optimization API — Backend Django Engineer (Spotter Assessment)

> A Django REST API that plans the most cost-effective fuel stops along a driving route in the USA, based on real fuel-station price data.

![Python](https://img.shields.io/badge/Python-3.10-blue)
![Django](https://img.shields.io/badge/Django-4.2.7-green)
![DRF](https://img.shields.io/badge/Django_REST_Framework-3.14-red)
![License](https://img.shields.io/badge/Status-Assessment_Project-orange)

## Overview

This project was built as a backend engineering assessment. Given a start and finish location in the USA, the API calculates the driving route, then selects optimal fuel stops along it — taking into account the vehicle's range and fuel efficiency — so the total fuel cost of the trip is minimized. Fuel-station data (including retail prices) is imported from the provided CSV dataset (`data/fuel-prices-for-be-assessment.csv`), geocoded, and cached to keep API responses fast and external API calls low.

## Key Features

- **Route optimization endpoint** — `POST /api/optimize/` returns the route with an optimized set of fuel stops
- **Cost-aware stop selection** — the optimizer service weighs station prices (`core/services/optimizer.py`) along the route geometry (`core/services/routing.py`)
- **Vehicle constraints** — plans for a 500-mile range at 10 MPG, inserting multiple stops on long routes
- **Station import pipeline** — management command `import_stations` loads stations from the assessment CSV
- **Geocoding pipeline** — management command `geocode_stations` + `core/services/geocoding.py` resolve station coordinates, with results cached in the database (`CachedGeocode`, `CachedRoute` models)
- **Health check endpoint** — `GET /api/health/`
- **Clean service-layer architecture** — business logic lives in `core/services/`, separate from views and serializers

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.10 |
| Framework | Django 4.2.7, Django REST Framework 3.14 |
| Routing | OpenRouteService API |
| Geocoding | Nominatim (via geopy) |
| Database | SQLite3 |
| Caching | Django cache framework + DB-backed route/geocode caches |
| Other | polyline, django-cors-headers, Pillow, requests |

## Project Structure

```
├── assessment/            # Django project settings & URLs
├── core/
│   ├── models.py          # FuelStation, CachedGeocode, CachedRoute
│   ├── serializers.py
│   ├── views.py           # RouteOptimizeView, HealthCheckView
│   ├── urls.py            # /optimize/, /health/
│   ├── services/
│   │   ├── routing.py     # Route fetching/decoding
│   │   ├── geocoding.py   # Address → coordinates
│   │   └── optimizer.py   # Fuel-stop optimization algorithm
│   └── management/commands/
│       ├── import_stations.py
│       └── geocode_stations.py
├── data/
│   └── fuel-prices-for-be-assessment.csv
├── commands.txt           # Step-by-step run book used for this project
├── requirements.txt
└── manage.py
```

## Getting Started

```bash
git clone https://github.com/datascientist970/Backend-Django-Engineer-by-spotter.git
cd Backend-Django-Engineer-by-spotter

python -m venv venv
venv\Scripts\activate        # Windows  (use source venv/bin/activate on Linux/macOS)

pip install -r requirements.txt
python manage.py migrate
python manage.py createcachetable
```

### Import and geocode the station data

```bash
python manage.py import_stations --csv data/fuel-prices-for-be-assessment.csv --clear --skip-geocode
python manage.py geocode_stations
```

### Run the server

```bash
python manage.py runserver
```

## Usage

Optimize a route:

```bash
curl -X POST http://127.0.0.1:8000/api/optimize/ \
  -H "Content-Type: application/json" \
  -d '{"start": "New York, NY", "finish": "Chicago, IL"}'
```

The response describes the route and the recommended fuel stops with prices and the estimated total fuel cost for the trip. See `commands.txt` in the repository for the full setup/run sequence used during development.

## Author

**Muhammad Dawood** — AI & Data Science Engineer
GitHub: https://github.com/datascientist970 · Mardan, Pakistan
