"""
Aggregate exports for the models package.
"""

# Common Masters
from .commonmasters.continent import Continent
from .commonmasters.country import Country
from .commonmasters.state import State

#Masters
from .masters.district import District
from .masters.city import City
from .masters.zone import Zone
from .masters.ward import Ward
from .masters.bin import Bin

# Tenancy
from .superadminmasters.company import Company
from .superadminmasters.project import Project

# Assets
from .assets.fuel import Fuel
from .assets.property import Property
from .assets.subproperty import SubProperty
from .assets.zone_property_load_tracker import ZonePropertyLoadTracker

# Staff
from .users.staffcreation import StaffOfficeDetails, StaffPersonalDetails

# Users & Access
from .users.userType import UserType
from .users.staffUserType import StaffUserType
from .superadminmasters.auth_user import User
from .screenmanagement.mainscreentype import MainScreenType
from .screenmanagement.mainscreen import MainScreen
from .screenmanagement.userscreen import UserScreen
from .screenmanagement.userscreenaction import UserScreenAction
from .screenmanagement.companyuserscreenpermission import CompanyUserScreenPermission
from .screenmanagement.userpermission import UserPermission
from .users.mainuserscreen import MainUserScreen
from .users.loginAudit import LoginAudit
from .users.auditlog import AuditLog

# Customer / Waste / Feedback
from .customers.customercreation import CustomerCreation
from .customers.wastecollection import WasteCollection
from .customers.feedback import FeedBack
from .complaints.complaints import Complaint

# Citizen Grievance
from .complaints.main_category_citizenGrievance import MainCategory
from .complaints.sub_category_citizenGrievance import SubCategory

# Bluetooth Waste Collection
from .users.waste_collection_bluetooth import (
    WasteCollectionSub,
    WasteType,
    WasteCollectionMain,
)

# Staff Templates / Routes
from .users.stafftemplate import StaffTemplate
from .users.alternative_staff_template import AlternativeStaffTemplate
from .users.staff_template_audit_log import StaffTemplateAuditLog
from .users.routeplan import RoutePlan
from .users.supervisor_zone_map import SupervisorZoneMap
from .users.supervisor_zone_access_audit import SupervisorZoneAccessAudit
from .users.unassigned_staff_pool import UnassignedStaffPool

# Attendance
from .users.attendance import Employee, Recognized

# Vehicles / Trips
from .vehicles.vehicleTypeCreation import VehicleTypeCreation
from .vehicles.vehicleCreation import VehicleCreation
from .vehicles.trip_definition import TripDefinition
from .vehicles.trip_instance import TripInstance
from .vehicles.trip_attendance import TripAttendance
from .vehicles.trip_exception_log import TripExceptionLog
from .vehicles.vehicle_trip_audit import VehicleTripAudit
from .vehicles.bin_load_log import BinLoadLog

__all__ = [
    # Common Master
    "Continent",
    "Country",
    "State",
    #Master
    "District",
    "City",
    "Zone",
    "Ward",
    "Bin",
    # Tenancy
    "Company",
    "Project",
    # Assets
    "Fuel",
    "Property",
    "SubProperty",
    "ZonePropertyLoadTracker",
    # Staff
    "StaffOfficeDetails",
    "StaffPersonalDetails",
    # Users & Access
    "UserType",
    "StaffUserType",
    "User",
    "MainScreenType",
    "MainScreen",
    "UserScreen",
    "UserScreenAction",
    "CompanyUserScreenPermission",
    "UserPermission",
    "MainUserScreen",
    "LoginAudit",
    "AuditLog",
    # Customer / Waste / Feedback
    "CustomerCreation",
    "WasteCollection",
    "FeedBack",
    "Complaint",
    # Citizen Grievance
    "MainCategory",
    "SubCategory",
    # Bluetooth Waste Collection
    "WasteCollectionSub",
    "WasteType",
    "WasteCollectionMain",
    # Staff Templates / Routes
    "StaffTemplate",
    "AlternativeStaffTemplate",
    "StaffTemplateAuditLog",
    "RoutePlan",
    "SupervisorZoneMap",
    "SupervisorZoneAccessAudit",
    "UnassignedStaffPool",
    # Attendance
    "Employee",
    "Recognized",
    # Vehicles / Trips
    "VehicleTypeCreation",
    "VehicleCreation",
    "TripDefinition",
    "TripInstance",
    "TripAttendance",
    "TripExceptionLog",
    "VehicleTripAudit",
    "BinLoadLog",
]
