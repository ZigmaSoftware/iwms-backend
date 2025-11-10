from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ContinentViewSet, 
    CountryViewSet, 
    StateViewSet, 
    DistrictViewSet, 
    CityViewSet, 
    ZoneViewSet, 
    WardViewSet, 
    FuelViewSet, 
    PropertyViewSet, 
    SubPropertyViewSet,
    CustomerCreationViewSet, 
    WasteCollectionViewSet, 
    FeedBackViewSet, 
    UserTypeViewSet,
    UserViewSet, 
    VehicleTypeCreationViewSet,
    VehicleCreationViewSet,
    ComplaintViewSet,
    MainUserScreenViewSet,
    UserScreenViewSet,
    UserPermissionViewSet,
    )


router = DefaultRouter()
router.register(r'continents', ContinentViewSet)
router.register(r'countries', CountryViewSet)
router.register(r'states', StateViewSet)
router.register(r'districts', DistrictViewSet)
router.register(r'cities', CityViewSet)
router.register(r'zones', ZoneViewSet)
router.register(r'wards', WardViewSet)
router.register(r'fuels',FuelViewSet)
router.register(r'properties', PropertyViewSet)
router.register(r'subproperties', SubPropertyViewSet)
router.register(r'customercreations',CustomerCreationViewSet)
router.register(r'wastecollections', WasteCollectionViewSet)
router.register(r'feedbacks', FeedBackViewSet)
router.register(r'user-type', UserTypeViewSet, basename='user-type')
router.register(r'user', UserViewSet, basename='user')
router.register(r'vehicle-type', VehicleTypeCreationViewSet, basename='vehicle-type')
router.register(r'vehicle-creation', VehicleCreationViewSet, basename='vehicle-creation')
router.register(r'complaints',ComplaintViewSet , basename='complaints')  
router.register(r'mainuserscreen', MainUserScreenViewSet)
router.register(r'userscreens',UserScreenViewSet)
router.register(r'userpermissions',UserPermissionViewSet)






urlpatterns = [
    path('', include(router.urls)),
]
