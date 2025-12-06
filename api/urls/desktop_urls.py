from .custom_router import GroupedRouter

# Masters
from ..views.desktopView.masters.continent_viewset import ContinentViewSet
from ..views.desktopView.masters.country_viewset import CountryViewSet
from ..views.desktopView.masters.state_viewset import StateViewSet
from ..views.desktopView.masters.district_viewset import DistrictViewSet
from ..views.desktopView.masters.city_viewset import CityViewSet
from ..views.desktopView.masters.zone_viewset import ZoneViewSet
from ..views.desktopView.masters.ward_viewset import WardViewSet
from ..views.desktopView.masters.staffcreation_viewset import StaffcreationViewset

# Assets
from ..views.desktopView.assets.fuel_viewset import FuelViewSet
from ..views.desktopView.assets.property_viewset import PropertyViewSet
from ..views.desktopView.assets.subproperty_viewset import SubPropertyViewSet

# Customers
from ..views.desktopView.customers.customercreation_viewset import CustomerCreationViewSet
from ..views.desktopView.customers.wastecollection_viewset import WasteCollectionViewSet
from ..views.desktopView.customers.feedback_viewset import FeedBackViewSet

# Users & Access
from ..views.desktopView.users.usertype_viewset import UserTypeViewSet
from ..views.desktopView.users.user_viewset import UserViewSet
from ..views.desktopView.users.staffusertype_viewset import StaffUserTypeViewSet
from ..views.desktopView.users.userscreenaction_viewset import UserScreenActionViewSet
from ..views.desktopView.users.mainscreentype_viewset import MainScreenTypeViewSet
from ..views.desktopView.users.mainscreen_viewset import MainScreenViewSet
from ..views.desktopView.users.userscreen_viewset import UserScreenViewSet
from ..views.desktopView.users.userscreenpermission_viewset import UserScreenPermissionViewSet
from ..views.desktopView.users.login_viewset import LoginViewSet

# Vehicles
from ..views.desktopView.vehicles.vehicletypecreation_viewset import VehicleTypeCreationViewSet
from ..views.desktopView.vehicles.vehiclecreation_viewset import VehicleCreationViewSet

# Complaints
from ..views.desktopView.complaints.complaint_viewset import ComplaintViewSet


# -------------------------------------------------------------------
# Register grouped router
# -------------------------------------------------------------------
router = GroupedRouter()

# Masters
router.register_group("masters", "continents", ContinentViewSet)
router.register_group("masters", "countries", CountryViewSet)
router.register_group("masters", "states", StateViewSet)
router.register_group("masters", "districts", DistrictViewSet)
router.register_group("masters", "cities", CityViewSet)
router.register_group("masters", "zones", ZoneViewSet)
router.register_group("masters", "wards", WardViewSet)
router.register_group("masters", "staffcreation", StaffcreationViewset)

# Assets
router.register_group("assets", "fuels", FuelViewSet)
router.register_group("assets", "properties", PropertyViewSet)
router.register_group("assets", "subproperties", SubPropertyViewSet)

# Customers
router.register_group("customers", "customercreations", CustomerCreationViewSet)
router.register_group("customers", "wastecollections", WasteCollectionViewSet)
router.register_group("customers", "feedbacks", FeedBackViewSet)

# Users
router.register_group("users", "user-type", UserTypeViewSet)
router.register_group("users", "staffusertypes", StaffUserTypeViewSet)
router.register_group("users", "users", UserViewSet)
router.register_group("users", "login-user", LoginViewSet)
router.register_group("users", "userscreen-action", UserScreenActionViewSet)
router.register_group("users", "mainscreentype", MainScreenTypeViewSet)
router.register_group("users", "mainscreens", MainScreenViewSet)
router.register_group("users", "userscreens", UserScreenViewSet)
router.register_group("users", "userscreenpermissions", UserScreenPermissionViewSet)

# Vehicles
router.register_group("vehicles", "vehicle-type", VehicleTypeCreationViewSet)
router.register_group("vehicles", "vehicle-creation", VehicleCreationViewSet)

# Complaints
router.register_group("complaints", "complaints", ComplaintViewSet)


urlpatterns = router.urls
