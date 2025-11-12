# Geography
from .geography.continent_viewset import ContinentViewSet
from .geography.country_viewset import CountryViewSet
from .geography.state_viewset import StateViewSet
from .geography.district_viewset import DistrictViewSet
from .geography.city_viewset import CityViewSet
from .geography.zone_viewset import ZoneViewSet
from .geography.ward_viewset import WardViewSet

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

    # Vehicles
    "VehicleTypeCreationViewSet",
    "VehicleCreationViewSet",

    # Complaints
    "ComplaintViewSet",
]
