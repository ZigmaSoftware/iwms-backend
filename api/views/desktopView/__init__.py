# Geography
from .masters.continent_viewset import ContinentViewSet
from .masters.country_viewset import CountryViewSet
from .masters.state_viewset import StateViewSet
from .masters.district_viewset import DistrictViewSet
from .masters.city_viewset import CityViewSet

from .masters.zone_viewset import ZoneViewSet
from .masters.ward_viewset import WardViewSet

# Assets
from .assets.fuel_viewset import FuelViewSet
from .assets.property_viewset import PropertyViewSet
from .assets.subproperty_viewset import SubPropertyViewSet

# Customers
from .customers.customercreation_viewset import CustomerCreationViewSet
from .customers.wastecollection_viewset import WasteCollectionViewSet
from .customers.feedback_viewset import FeedBackViewSet

# Users
from .users.usertype_viewset import UserTypeViewSet
from .users.user_viewset import UserViewSet
from .users.mainuserscreen_viewset import MainUserScreenViewSet
from .users.userscreen_viewset import UserScreenViewSet
from .users.userpermission_viewset import UserPermissionViewSet
from .users.staffusertype_viewset import StaffUserTypeViewSet
from .masters.staffcreation_viewset import StaffcreationViewset
from .users.login_viewset import LoginViewSet

# Vehicles
from .vehicles.vehicletypecreation_viewset import VehicleTypeCreationViewSet
from .vehicles.vehiclecreation_viewset import VehicleCreationViewSet

# Complaints
from .complaints.complaint_viewset import ComplaintViewSet


__all__ = [
    # Geography
    "ContinentViewSet",
    "CountryViewSet",
    "StateViewSet",
    "DistrictViewSet",
    "CityViewSet",
    "ZoneViewSet",
    "WardViewSet",
      # <-- fixed comma

    # Assets
    "FuelViewSet",
    "PropertyViewSet",
    "SubPropertyViewSet",

    # Customers
    "CustomerCreationViewSet",
    "WasteCollectionViewSet",
    "FeedBackViewSet",

    # Users
    "UserTypeViewSet",
    "UserViewSet",
    "MainUserScreenViewSet",
    "UserScreenViewSet",
    "UserPermissionViewSet",
    "StaffUserTypeViewSet",
    "StaffcreationViewset",
    "LoginViewSet",

    # Vehicles
    "VehicleTypeCreationViewSet",
    "VehicleCreationViewSet",

    # Complaints
    "ComplaintViewSet",
]
