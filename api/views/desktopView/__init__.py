# This file should NOT define viewsets.
# It should ONLY expose the classes for clean imports.

# ==============================
# Masters
# ==============================
from .masters.continent_viewset import ContinentViewSet
from .masters.country_viewset import CountryViewSet
from .masters.state_viewset import StateViewSet
from .masters.district_viewset import DistrictViewSet
from .masters.city_viewset import CityViewSet
from .masters.zone_viewset import ZoneViewSet
from .masters.ward_viewset import WardViewSet

# ==============================
# Assets
# ==============================
from .assets.fuel_viewset import FuelViewSet
from .assets.property_viewset import PropertyViewSet
from .assets.subproperty_viewset import SubPropertyViewSet

# ==============================
# Customers
# ==============================
from .customers.customercreation_viewset import CustomerCreationViewSet
from .customers.wastecollection_viewset import WasteCollectionViewSet
from .customers.feedback_viewset import FeedBackViewSet
from .customers.household_pickup_event_viewset import HouseholdPickupEventViewSet

# ==============================
# Users
# ==============================
from .users.usertype_viewset import UserTypeViewSet
from .users.user_viewset import UserViewSet
from .users.staffusertype_viewset import StaffUserTypeViewSet
from .users.login_viewset import LoginViewSet
from .users.userscreen_viewset import UserScreenViewSet
from .users.mainscreentype_viewset import MainScreenTypeViewSet
from .users.mainscreen_viewset import MainScreenViewSet
from .users.userscreenaction_viewset import UserScreenActionViewSet
from .users.userscreenpermission_viewset import UserScreenPermissionViewSet
from .users.staffcreation_viewset import StaffcreationViewset
from .users.stafftemplate_viewset import StaffTemplateViewSet
from .users.staff_template_audit_log_viewset import StaffTemplateAuditLogViewSet
from .users.alternative_stafftemplate_viewset import AlternativeStaffTemplateViewSet

# ==============================
# Vehicles
# ==============================
from .vehicles.vehicletypecreation_viewset import VehicleTypeCreationViewSet
from .vehicles.vehicleCreation_viewset import VehicleCreationViewSet
from .vehicles.trip_instance_viewset import TripInstanceViewSet

# ==============================
# Complaints
# ==============================
from .complaints.complaint_viewset import ComplaintViewSet


# ==============================
# EXPORTS
# ==============================
__all__ = [
    # Masters
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
    "HouseholdPickupEventViewSet",

    # Users
    "UserTypeViewSet",
    "UserViewSet",
    "StaffUserTypeViewSet",
    "LoginViewSet",
    "MainScreenTypeViewSet",
    "MainScreenViewSet",
    "UserScreenViewSet",
    "UserScreenActionViewSet",
    "UserScreenPermissionViewSet",
    "StaffcreationViewset",
    "StaffTemplateViewSet",
    "StaffTemplateAuditLogViewSet",
    "AlternativeStaffTemplateViewSet",

    # Vehicles
    "VehicleTypeCreationViewSet",
    "VehicleCreationViewSet",
    "TripInstanceViewSet",

    # Complaints
    "ComplaintViewSet",
]
