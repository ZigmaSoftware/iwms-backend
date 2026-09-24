"""
Aggregate exports for the models package.
Folders mirror the admin UI: superadmin/, masters/, core_modules/, reports/.
"""

# ============================================================
# GROUP: COMMON MASTERS
# ============================================================
from .superadmin.common_masters.continent import Continent
from .superadmin.common_masters.country import Country
from .superadmin.common_masters.state import State


# ============================================================
# GROUP: MASTERS
# ============================================================
from .masters.district import District
from .masters.city import City
from .masters.zone import Zone
from .masters.ward import Ward
from .masters.plant import Plant
from .superadmin.staff_management.department import Department
from .superadmin.staff_management.designation import Designation
from .masters.leader_management.panchayat_leader_login import PanchayatLeaderLogin
from .masters.leader_management.district_leader_login import DistrictLeaderLogin
from .masters.block_panchayat_union import BlockPanchayatUnion


# ============================================================
# GROUP: ASSETS
# ============================================================
from .masters.transport_masters.fuel import Fuel
from .masters.waste_masters.weighbridge import WeighbridgeCheck
from .masters.waste_masters.bins import Bins


# ============================================================
# GROUP: TENANCY / SUPERADMIN
# ============================================================
from .superadmin_masters.company import Company
from .superadmin_masters.project import Project
from .superadmin_masters.auth_user import User


# ============================================================
# GROUP: WASTE TYPES
# ============================================================
from .masters.waste_masters.property import Property
from .masters.waste_masters.subproperty import SubProperty

# ============================================================
# GROUP: USERS & ROLE ASSIGNMENT
# ============================================================
from .superadmin.role_management.userType import UserType
from .superadmin.role_management.staffUserType import StaffUserType
from .superadmin.role_management.projectStaffHierarchy import ProjectStaffHierarchy


# ============================================================
# GROUP: SCREEN MANAGEMENT / PERMISSIONS
# ============================================================
from .superadmin.screen_management.mainscreentype import MainScreenType
from .superadmin.screen_management.mainscreen import MainScreen
from .superadmin.screen_management.userscreen import UserScreen
from .superadmin.screen_management.userscreenaction import UserScreenAction
from .superadmin.screen_management.userscreencolumn import UserScreenColumn
from .superadmin.screen_management.companyuserscreenpermission import CompanyUserScreenPermission
from .superadmin.screen_management.companyuserscreencolumnpermission import CompanyUserScreenColumnPermission
from .superadmin.screen_management.app_module import AppModule


# ============================================================
# GROUP: USER CREATION & STAFF
# ============================================================
from .superadmin.staff_management.staffcreation import (
    StaffcreationOfficeDetails,
    StaffPersonalDetails,
)
from .core_modules.schedule_setup.staff_template import StaffTemplate
from .core_modules.schedule_setup.alternative_staff_template import AlternativeStaffTemplate
from .superadmin.staff_management.staff_access_configuration import (
    StaffAccessConfiguration,
    StaffAccessConfigurationPermission,
)


# ============================================================
# GROUP: AUTH / LOGIN / AUDIT (USER)
# ============================================================
from .superadmin.audits.loginAudit import LoginAudit
from .superadmin.audits.auditlog import AuditLog
from app.utils.common_audit import CommonAudit
from .superadmin.audits.permission_audit import PermissionAuditLog


# ============================================================
# GROUP: CUSTOMER MODULES
# ============================================================
from .masters.customer_masters.customercreation import CustomerCreation
from .masters.customer_masters.customer_access_configuration import CustomerAccessConfiguration
from .core_modules.daily_operations.wastecollection import WasteCollection
from .masters.customer_masters.password_reset_otp import PasswordResetOTP


# ============================================================
# GROUP: GRIEVANCES
# ============================================================
from .core_modules.complaint_management.complaints import Complaint
from .core_modules.complaint_management.main_category_citizenGrievance import MainCategory
from .core_modules.complaint_management.sub_category_citizenGrievance import SubCategory


# ============================================================
# GROUP: COMPLAINT MANAGEMENT (ticketed grievance workflow)
# ============================================================
from .core_modules.complaint_management import (
    ComplaintSource,
    ComplaintLanguage,
    ComplaintPriority,
    ComplaintStatus,
    ComplaintModule,
    ComplaintCategory,
    ComplaintSubcategory,
    ComplaintSlaRule,
    ComplaintTicket,
    ComplaintTicketExtraDetail,
    ComplaintAttachment,
    ComplaintStatusHistory,
    ComplaintAssignmentHistory,
    ComplaintComment,
    ComplaintRoutingRule,
    ComplaintEscalationHistory,
    ComplaintFeedback,
    ComplaintReopenHistory,
    ComplaintAddressChangeRequest,
    ComplaintNotification,
)


# ============================================================
# GROUP: STAFF NOTIFICATIONS
# ============================================================
from .core_modules.notifications.staff_notification import StaffNotification


# ============================================================
# GROUP: BLUETOOTH / MOBILE WASTE COLLECTION
# ============================================================
from .waste_collection_bluetooth.waste_collection_bluetooth import (
    WasteCollectionSub,
    WasteType,
    WasteCollectionMain,
)


# ============================================================
# GROUP: ATTENDANCE (MOBILE)
# ============================================================
from .core_modules.attendance.attendance import Employee, Recognized
from .core_modules.attendance.attendance_new import AttendanceNew


# ============================================================
# GROUP: TRANSPORT MASTERS & TRIPS
# ============================================================
from .masters.transport_masters.vehicleTypeCreation import VehicleTypeCreation
from .masters.transport_masters.vehicleCreation import VehicleCreation
from .core_modules.schedule_setup.trip_plan import TripPlan
from .core_modules.schedule_setup.trip_plan_collection_point import TripPlanCollectionPoint
from .core_modules.daily_operations.daily_trip_assignment import DailyTripAssignment
from .core_modules.daily_operations.daily_trip_log import DailyTripLog
from .core_modules.daily_operations.daily_trip_collection_point import DailyTripCollectionPoint
from .core_modules.daily_operations.daily_trip_household_collection import DailyTripHouseholdCollection
from .core_modules.daily_operations.bin_collection_event import BinCollectionEvent
from .core_modules.daily_operations.vehicle_breakdown import VehicleBreakdown
from .core_modules.daily_operations.trip_delay_report import TripDelayReport
from .core_modules.daily_operations.trip_retrip_request import TripRetripRequest
from .core_modules.schedule_setup.collection_point import Collection_point
from .core_modules.daily_operations.route_detour_waypoint import RouteDetourWaypoint
from .core_modules.daily_operations.scheduler_config import SchedulerConfig
from .reports.waste_reports.daily_waste_comparison import DailyWasteComparison
from .reports.waste_reports.monthly_weight_report import MonthlyWeightReport


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
    "DistrictLeaderLogin",
    "BlockPanchayatUnion",

    # Assets
    "Fuel",
    "WeighbridgeCheck",
    "Bins",

    # Tenancy
    "Company",
    "Project",
    "User",

    # Waste Types
    "Property",
    "SubProperty",

    # Users & Roles
    "UserType",
    "StaffUserType",
    "ProjectStaffHierarchy",

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
    "StaffAccessConfiguration",
    "StaffAccessConfigurationPermission",

    # Auth / Audit
    "LoginAudit",
    "AuditLog",

    # Customers
    "CustomerCreation",
    "WasteCollection",
    "PasswordResetOTP",

    # Grievances
    "Complaint",
    "MainCategory",
    "SubCategory",

    # Complaint Management (ticketed grievance workflow)
    "ComplaintSource",
    "ComplaintLanguage",
    "ComplaintPriority",
    "ComplaintStatus",
    "ComplaintModule",
    "ComplaintCategory",
    "ComplaintSubcategory",
    "ComplaintSlaRule",
    "ComplaintTicket",
    "ComplaintTicketExtraDetail",
    "ComplaintAttachment",
    "ComplaintStatusHistory",
    "ComplaintAssignmentHistory",
    "ComplaintComment",
    "ComplaintRoutingRule",
    "ComplaintEscalationHistory",
    "ComplaintFeedback",
    "ComplaintReopenHistory",
    "ComplaintAddressChangeRequest",
    "ComplaintNotification",

    # Staff Notifications
    "StaffNotification",

    # Bluetooth Waste
    "WasteCollectionSub",
    "WasteType",
    "WasteCollectionMain",

    # Attendance
    "Employee",
    "Recognized",
    "AttendanceNew",

    # Transport
    "VehicleTypeCreation",
    "VehicleCreation",
    "TripPlan",
    "TripPlanCollectionPoint",

    # Audits
    "PermissionAuditLog",

    # Daily Trip Assignment
    "DailyTripAssignment",
    "DailyTripLog",
    "DailyTripCollectionPoint",
    "DailyTripHouseholdCollection",
    "BinCollectionEvent",
    "VehicleBreakdown",
    "TripRetripRequest",
    "Collection_point",
    "RouteDetourWaypoint",
    "DailyWasteComparison",
    "SchedulerConfig",
    "MonthlyWeightReport",
]
