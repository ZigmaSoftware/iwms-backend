from rest_framework.routers import DefaultRouter
from django.urls import path

# ==============================
#   Import All ViewSets
# ==============================

# Masters
from ..views.desktopView.masters.continent_viewset import ContinentViewSet
from ..views.desktopView.masters.country_viewset import CountryViewSet
from ..views.desktopView.masters.state_viewset import StateViewSet
from ..views.desktopView.masters.district_viewset import DistrictViewSet
from ..views.desktopView.masters.city_viewset import CityViewSet
from ..views.desktopView.masters.zone_viewset import ZoneViewSet
from ..views.desktopView.masters.ward_viewset import WardViewSet

# Assets
from ..views.desktopView.assets.fuel_viewset import FuelViewSet
from ..views.desktopView.assets.property_viewset import PropertyViewSet
from ..views.desktopView.assets.subproperty_viewset import SubPropertyViewSet

# Customers
from ..views.desktopView.customers.customercreation_viewset import CustomerCreationViewSet
from ..views.desktopView.customers.wastecollection_viewset import WasteCollectionViewSet
from ..views.desktopView.customers.feedback_viewset import FeedBackViewSet

# Users
from ..views.desktopView.users.usertype_viewset import UserTypeViewSet
from ..views.desktopView.users.user_viewset import UserViewSet
from ..views.desktopView.users.mainuserscreen_viewset import MainUserScreenViewSet
from ..views.desktopView.users.userscreen_viewset import UserScreenViewSet
from ..views.desktopView.users.userpermission_viewset import UserPermissionViewSet
from ..views.desktopView.users.staffusertype_viewset import StaffUserTypeViewSet
from ..views.desktopView.masters.staffcreation_viewset import StaffcreationViewset

# Vehicles
from ..views.desktopView.vehicles.vehicletypecreation_viewset import VehicleTypeCreationViewSet
from ..views.desktopView.vehicles.vehiclecreation_viewset import VehicleCreationViewSet

# Complaints
from ..views.desktopView.complaints.complaint_viewset import ComplaintViewSet

# New Config Endpoint
from ..views.desktopView.users.userType_config_viewset import UserTypeConfigView

from ..views.desktopView.users.login_viewset import LoginViewSet



# ==============================
#   Router Registration
# ==============================

router = DefaultRouter()

# Masters
router.register(r'continents', ContinentViewSet)
router.register(r'countries', CountryViewSet)
router.register(r'states', StateViewSet)
router.register(r'districts', DistrictViewSet)
router.register(r'cities', CityViewSet)
router.register(r'zones', ZoneViewSet)
router.register(r'wards', WardViewSet)
router.register(r'staffcreation', StaffcreationViewset)

# Assets
router.register(r'fuels', FuelViewSet)
router.register(r'properties', PropertyViewSet)
router.register(r'subproperties', SubPropertyViewSet)

# Customers
router.register(r'customercreations', CustomerCreationViewSet)
router.register(r'wastecollections', WasteCollectionViewSet)
router.register(r'feedbacks', FeedBackViewSet)

# Users
router.register(r'user-type', UserTypeViewSet)
router.register(r'staffusertypes', StaffUserTypeViewSet)
router.register(r'user', UserViewSet)
router.register(r'mainuserscreen', MainUserScreenViewSet)           
router.register(r'userscreens', UserScreenViewSet)
router.register(r'userpermissions', UserPermissionViewSet)
router.register(r'login-user', LoginViewSet, basename='login-user')


# Vehicles
router.register(r'vehicle-type', VehicleTypeCreationViewSet)
router.register(r'vehicle-creation', VehicleCreationViewSet)

# Complaints
router.register(r'complaints', ComplaintViewSet)


# ==============================
#   Final URL Patterns
# ==============================

urlpatterns = router.urls 

# + [
#     path('user-type-config/<int:pk>/', UserTypeConfigView.as_view(), name="user-type-config"),
# ]
