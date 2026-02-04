# This file should NOT define viewsets.
# It should ONLY expose the classes for clean imports.

# ==============================
# Masters
# ==============================
from .commonmasters.continent_viewset import ContinentViewSet
from .commonmasters.country_viewset import CountryViewSet
from .commonmasters.state_viewset import StateViewSet
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

# ==============================
# Role assignment
# ==============================
from .role_assign.usertype_viewset import UserTypeViewSet
from .role_assign.staffusertype_viewset import StaffUserTypeViewSet

# ==============================
# User creation
# ==============================
from .user_creation.staff_viewset import StaffViewSet
from .user_creation.staffcreation_viewset import StaffcreationViewset
from .user_creation.stafftemplate_viewset import StaffTemplateViewSet
from .user_creation.staff_template_audit_log_viewset import StaffTemplateAuditLogViewSet
from .user_creation.alternative_stafftemplate_viewset import AlternativeStaffTemplateViewSet
from .user_creation.routeplan_viewset import RoutePlanViewSet
from .user_creation.supervisor_zone_map_viewset import SupervisorZoneMapViewSet
from .user_creation.supervisor_zone_access_audit_viewset import SupervisorZoneAccessAuditViewSet
from .user_creation.unassigned_staff_pool_viewset import UnassignedStaffPoolViewSet

# ==============================
# Authentication
# ==============================
from .users.login_viewset import LoginViewSet

# ==============================
# Screen Management
# ==============================
from .screenmanagement.userscreen_viewset import UserScreenViewSet
from .screenmanagement.userscreenaction_viewset import UserScreenActionViewSet
from .screenmanagement.mainscreentype_viewset import MainScreenTypeViewSet
from .screenmanagement.mainscreen_viewset import MainScreenViewSet
from .screenmanagement.companyuserscreenpermission_viewset import CompanyUserScreenPermissionViewSet
from .screenmanagement.userpermission_viewset import UserPermissionViewSet

# ==============================
# Vehicles
# ==============================
from .vehicles.vehicletypecreation_viewset import VehicleTypeCreationViewSet
from .vehicles.vehicleCreation_viewset import VehicleCreationViewSet
from .vehicles.trip_instance_viewset import TripInstanceViewSet
from .vehicles.vehicle_trip_audit_viewset import VehicleTripAuditViewSet
from .vehicles.trip_exception_log_viewset import TripExceptionLogViewSet
from .vehicles.trip_attendance_viewset import TripAttendanceViewSet

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

    # Users
    "UserTypeViewSet",
    "StaffViewSet",
    "StaffUserTypeViewSet",
    "LoginViewSet",
    "MainScreenTypeViewSet",
    "MainScreenViewSet",
    "UserScreenViewSet",
    "UserScreenActionViewSet",
    "CompanyUserScreenPermissionViewSet",
    "UserPermissionViewSet",
    "StaffcreationViewset",
    "StaffTemplateViewSet",
    "StaffTemplateAuditLogViewSet",
    "AlternativeStaffTemplateViewSet",
    "UnassignedStaffPoolViewSet",
    "RoutePlanViewSet",
    "SupervisorZoneMapViewSet",
    "SupervisorZoneAccessAuditViewSet",

    # Vehicles
    "VehicleTypeCreationViewSet",
    "VehicleCreationViewSet",
    "TripInstanceViewSet",
    "VehicleTripAuditViewSet",
    "TripExceptionLogViewSet",
    "TripAttendanceViewSet",

    # Complaints
    "ComplaintViewSet",
]
