"""
Aggregate exports for the models package.
Structured to mirror API router groupings.
"""

# ============================================================
# GROUP: COMMON MASTERS
# ============================================================
from .common_masters.continent import Continent
from .common_masters.country import Country
from .common_masters.state import State


# ============================================================
# GROUP: MASTERS
# ============================================================
from .masters.district import District
from .masters.city import City
from .masters.zone import Zone
from .masters.ward import Ward
from .masters.department import Department
from .masters.designation import Designation
from .masters.panchayat_leader_login import PanchayatLeaderLogin


# ============================================================
# GROUP: ASSETS
# ============================================================
from .transport_masters.fuel import Fuel


# ============================================================
# GROUP: TENANCY / SUPERADMIN
# ============================================================
from .superadmin_masters.company import Company
from .superadmin_masters.project import Project
from .superadmin_masters.auth_user import User


# ============================================================
# GROUP: WASTE TYPES
# ============================================================
from .waste_types.property import Property
from .waste_types.subproperty import SubProperty


# ============================================================
# GROUP: PROCESS
# ============================================================
from .process.zone_property_load_tracker import ZonePropertyLoadTracker
from .process.routeplan import RoutePlan


# ============================================================
# GROUP: USERS & ROLE ASSIGNMENT
# ============================================================
from .role_assigns.userType import UserType
from .role_assigns.staffUserType import StaffUserType


# ============================================================
# GROUP: SCREEN MANAGEMENT / PERMISSIONS
# ============================================================
from .screen_managements.mainscreentype import MainScreenType
from .screen_managements.mainscreen import MainScreen
from .screen_managements.userscreen import UserScreen
from .screen_managements.userscreenaction import UserScreenAction
from .screen_managements.userscreencolumn import UserScreenColumn
from .screen_managements.companyuserscreenpermission import CompanyUserScreenPermission
from .screen_managements.companyuserscreencolumnpermission import CompanyUserScreenColumnPermission


# ============================================================
# GROUP: USER CREATION & STAFF
# ============================================================
from .user_creations.staffcreation import (
    StaffcreationOfficeDetails,
    StaffPersonalDetails,
)
from .user_creations.stafftemplate import StaffTemplate
from .user_creations.alternative_staff_template import AlternativeStaffTemplate
from .user_creations.supervisor_zone_map import SupervisorZoneMap
from .user_creations.unassigned_staff_pool import UnassignedStaffPool


# ============================================================
# GROUP: AUTH / LOGIN / AUDIT (USER)
# ============================================================
from .user_creations.loginAudit import LoginAudit
from .user_creations.auditlog import AuditLog


# ============================================================
# GROUP: CUSTOMER MODULES
# ============================================================
from .customers.customercreation import CustomerCreation
from .customers.wastecollection import WasteCollection
from .customers.feedback import FeedBack
from .customers.userchargerule import UserChargeRule


# ============================================================
# GROUP: GRIEVANCES
# ============================================================
from .grivences.complaints import Complaint
from .grivences.main_category_citizenGrievance import MainCategory
from .grivences.sub_category_citizenGrievance import SubCategory


# ============================================================
# GROUP: BLUETOOTH / MOBILE WASTE COLLECTION
# ============================================================
from .user_creations.waste_collection_bluetooth import (
    WasteCollectionSub,
    WasteType,
    WasteCollectionMain,
)


# ============================================================
# GROUP: ATTENDANCE (MOBILE)
# ============================================================
from .user_creations.attendance import Employee, Recognized


# ============================================================
# GROUP: TRANSPORT MASTERS & TRIPS
# ============================================================
from .transport_masters.vehicleTypeCreation import VehicleTypeCreation
from .transport_masters.vehicleCreation import VehicleCreation
from .transport_masters.trip_definition import TripDefinition
from .transport_masters.trip_instance import TripInstance
from .transport_masters.trip_attendance import TripAttendance
from .transport_masters.daily_trip_assignment import DailyTripAssignment
from .transport_masters.daily_trip_log import DailyTripLog
from .transport_masters.daily_trip_collection_point import DailyTripCollectionPoint
from .transport_masters.bin_collection_event import BinCollectionEvent


# ============================================================
# GROUP: AUDITS
# ============================================================
from .audits.staff_template_audit_log import StaffTemplateAuditLog
from .audits.supervisor_zone_access_audit import SupervisorZoneAccessAudit
from .audits.trip_exception_log import TripExceptionLog
from .audits.vehicle_trip_audit import VehicleTripAudit
from app.utils.common_audit import CommonAudit
from app.models.collections.ward_wise_collection import WardCollection
from app.models.collections.zone_wise_collection import ZoneCollection
from app.models.collections.panchayat_wise_collection import PanchayatCollection
from app.models.assets.point_collection import PointCollection
from app.models.reports.monthly_weight_report import MonthlyWeightReport



# ============================================================
# EXPORTS
# ============================================================
__all__ = [
    # Common Masters
    "Continent",
    "Country",
    "State",

    # Masters
    "District",
    "City",
    "Zone",
    "Ward",
    "Department",
    "Designation",
    "PanchayatLeaderLogin",

    # Assets
    "Fuel",

    # Tenancy
    "Company",
    "Project",
    "User",

    # Waste Types
    "Property",
    "SubProperty",

    # Process
    "ZonePropertyLoadTracker",
    "RoutePlan",

    # Users & Roles
    "UserType",
    "StaffUserType",

    # Screen Management
    "MainScreenType",
    "MainScreen",
    "UserScreen",
    "UserScreenAction",
    "UserScreenColumn",
    "CompanyUserScreenPermission",
    "CompanyUserScreenColumnPermission",

    # User Creation & Staff
    "StaffcreationOfficeDetails",
    "StaffPersonalDetails",
    "StaffTemplate",
    "AlternativeStaffTemplate",
    "SupervisorZoneMap",
    "UnassignedStaffPool",

    # Auth / Audit
    "LoginAudit",
    "AuditLog",

    # Customers
    "CustomerCreation",
    "WasteCollection",
    "FeedBack",
    "UserChargeRule",

    # Grievances
    "Complaint",
    "MainCategory",
    "SubCategory",

    # Bluetooth Waste
    "WasteCollectionSub",
    "WasteType",
    "MonthlyWeightReport",
    "WasteCollectionMain",

    # Attendance
    "Employee",
    "Recognized",

    # Transport
    "VehicleTypeCreation",
    "VehicleCreation",
    "TripDefinition",
    "TripInstance",
    "TripAttendance",

    # Audits
    "StaffTemplateAuditLog",
    "SupervisorZoneAccessAudit",
    "TripExceptionLog",
    "VehicleTripAudit",

    # Daily Trip Assignment
    "DailyTripAssignment",
    "DailyTripLog",
    "DailyTripCollectionPoint",
    "BinCollectionEvent",
]
