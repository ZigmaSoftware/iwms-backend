from django.urls import path, include
from rest_framework.routers import DefaultRouter

# Import your mobile viewsets here when they exist
# from api.views.mobileView.geography.continent_viewset import ContinentMobileViewSet
# from api.views.mobileView.assets.fuel_viewset import FuelMobileViewSet
# etc.

router = DefaultRouter()

# Example registrations when you’re ready:
# router.register(r'continents', ContinentMobileViewSet, basename='mobile-continents')
# router.register(r'fuels', FuelMobileViewSet, basename='mobile-fuels')

# IMPORTANT: this must be a list, DRF gives a list-like object
urlpatterns = router.urls
