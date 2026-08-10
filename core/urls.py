"""
URL configuration for core app.
"""

from django.urls import path
from core.views import RouteOptimizeView, HealthCheckView

urlpatterns = [
    path('optimize/', RouteOptimizeView.as_view(), name='optimize-route'),
    path('health/', HealthCheckView.as_view(), name='health-check'),
]