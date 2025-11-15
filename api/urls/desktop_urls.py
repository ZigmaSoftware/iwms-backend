from django.urls import path, include
from rest_framework.routers import DefaultRouter

# Desktop ViewSets
from ..views.desktopView.geography.continent_viewset import ContinentViewSet
from ..views.desktopView.geography.country_viewset import CountryViewSet
from ..views.desktopView.geography.state_viewset import StateViewSet
from ..views.desktopView.geography.district_viewset import DistrictViewSet
from ..views.desktopView.geography.city_viewset import CityViewSet
from ..views.desktopView.geography.zone_viewset import ZoneViewSet
from ..views.desktopView.geography.ward_viewset import WardViewSet

from ..views.desktopView.assets.fuel_viewset import FuelViewSet
from ..views.desktopView.assets.property_viewset import PropertyViewSet
from ..views.desktopView.assets.subproperty_viewset import SubPropertyViewSet

from ..views.desktopView.customers.customercreation_viewset import CustomerCreationViewSet
from ..views.desktopView.customers.wastecollection_viewset import WasteCollectionViewSet
from ..views.desktopView.customers.feedback_viewset import FeedBackViewSet

from ..views.desktopView.users.usertype_viewset import UserTypeViewSet
from ..views.desktopView.users.user_viewset import UserViewSet
from ..views.desktopView.users.mainuserscreen_viewset import MainUserScreenViewSet
from ..views.desktopView.users.userscreen_viewset import UserScreenViewSet
from ..views.desktopView.users.userpermission_viewset import UserPermissionViewSet

from ..views.desktopView.vehicles.vehicletypecreation_viewset import VehicleTypeCreationViewSet
from ..views.desktopView.vehicles.vehiclecreation_viewset import VehicleCreationViewSet

from ..views.desktopView.complaints.complaint_viewset import ComplaintViewSet

router = DefaultRouter()

router.register(r'continents', ContinentViewSet)
router.register(r'countries', CountryViewSet)
router.register(r'states', StateViewSet)
router.register(r'districts', DistrictViewSet)
router.register(r'cities', CityViewSet)
router.register(r'zones', ZoneViewSet)
router.register(r'wards', WardViewSet)

router.register(r'fuels', FuelViewSet)
router.register(r'properties', PropertyViewSet)
router.register(r'subproperties', SubPropertyViewSet)

router.register(r'customercreations', CustomerCreationViewSet)
router.register(r'wastecollections', WasteCollectionViewSet)
router.register(r'feedbacks', FeedBackViewSet)

router.register(r'user-type', UserTypeViewSet)
router.register(r'user', UserViewSet)
router.register(r'mainuserscreen', MainUserScreenViewSet)
router.register(r'userscreens', UserScreenViewSet)
router.register(r'userpermissions', UserPermissionViewSet)

router.register(r'vehicle-type', VehicleTypeCreationViewSet)
router.register(r'vehicle-creation', VehicleCreationViewSet)

# router.register(r'customerCreations',CustomerCreationViewSet)
router.register(r'complaints', ComplaintViewSet)

urlpatterns = router.urls
