from django.urls import path, include
from rest_framework.routers import DefaultRouter

#  Geography
from .views.geography.continent_viewset import ContinentViewSet
from .views.geography.country_viewset import CountryViewSet
from .views.geography.state_viewset import StateViewSet
from .views.geography.district_viewset import DistrictViewSet
from .views.geography.city_viewset import CityViewSet
from .views.geography.zone_viewset import ZoneViewSet
from .views.geography.ward_viewset import WardViewSet

#  Assets
from .views.assets.fuel_viewset import FuelViewSet
from .views.assets.property_viewset import PropertyViewSet
from .views.assets.subproperty_viewset import SubPropertyViewSet

#  Customers
from .views.customers.customercreation_viewset import CustomerCreationViewSet
from .views.customers.wastecollection_viewset import WasteCollectionViewSet
from .views.customers.feedback_viewset import FeedBackViewSet

#  Users
from .views.users.usertype_viewset import UserTypeViewSet
from .views.users.user_viewset import UserViewSet
from .views.users.mainuserscreen_viewset import MainUserScreenViewSet
from .views.users.userscreen_viewset import UserScreenViewSet
from .views.users.userpermission_viewset import UserPermissionViewSet

#  Vehicles
from .views.vehicles.vehicletypecreation_viewset import VehicleTypeCreationViewSet
from .views.vehicles.vehiclecreation_viewset import VehicleCreationViewSet

#  Complaints
from .views.complaints.complaint_viewset import ComplaintViewSet


# Router registration
router = DefaultRouter()

#  Geography routes
router.register(r'continents', ContinentViewSet)
router.register(r'countries', CountryViewSet)
router.register(r'states', StateViewSet)
router.register(r'districts', DistrictViewSet)
router.register(r'cities', CityViewSet)
router.register(r'zones', ZoneViewSet)
router.register(r'wards', WardViewSet)

#  Assets routes
router.register(r'fuels', FuelViewSet)
router.register(r'properties', PropertyViewSet)
router.register(r'subproperties', SubPropertyViewSet)

#  Customer routes
router.register(r'customercreations', CustomerCreationViewSet)
router.register(r'wastecollections', WasteCollectionViewSet)
router.register(r'feedbacks', FeedBackViewSet)

#  User routes
router.register(r'user-type', UserTypeViewSet, basename='user-type')
router.register(r'user', UserViewSet, basename='user')
router.register(r'mainuserscreen', MainUserScreenViewSet)
router.register(r'userscreens', UserScreenViewSet)
router.register(r'userpermissions', UserPermissionViewSet)

#  Vehicle routes
router.register(r'vehicle-type', VehicleTypeCreationViewSet, basename='vehicle-type')
router.register(r'vehicle-creation', VehicleCreationViewSet, basename='vehicle-creation')

#  Complaint routes
router.register(r'complaints', ComplaintViewSet, basename='complaints')


urlpatterns = [
    path('', include(router.urls)),
]
