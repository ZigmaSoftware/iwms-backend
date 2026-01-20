"""
Import models so Django registers them for this app.
"""

# Geography
from .apps.continent import Continent
from .apps.country import Country
from .apps.state import State
from .apps.district import District
from .apps.city import City
from .apps.zone import Zone
from .apps.ward import Ward
from .apps.bin import Bin

# Assets
from .apps.fuel import Fuel
from .apps.property import Property
from .apps.subproperty import SubProperty
from .apps.zone_property_load_tracker import ZonePropertyLoadTracker

# Staff
from .apps.staffcreation import StaffOfficeDetails, StaffPersonalDetails

# Users & Access
from .apps.userType import UserType
from .apps.staffUserType import StaffUserType
from .apps.userCreation import User
from .apps.mainscreentype import MainScreenType
from .apps.mainscreen import MainScreen
from .apps.userscreen import UserScreen
from .apps.userscreenaction import UserScreenAction
from .apps.userscreenpermission import UserScreenPermission
from .apps.mainuserscreen import MainUserScreen
from .apps.userpermission import UserPermission
from .apps.loginAudit import LoginAudit
from .apps.auditlog import AuditLog

# Customer / Waste / Feedback
from .apps.customercreation import CustomerCreation
from .apps.customer_tag import CustomerTag
from .apps.wastecollection import WasteCollection
from .apps.feedback import FeedBack
from .apps.household_pickup_event import HouseholdPickupEvent
from .apps.complaints import Complaint

# Citizen Grievance
from .apps.main_category_citizenGrievance import MainCategory
from .apps.sub_category_citizenGrievance import SubCategory

# Bluetooth Waste Collection
from .apps.waste_collection_bluetooth import (
    WasteCollectionSub,
    WasteType,
    WasteCollectionMain,
)

# Staff Templates / Routes
from .apps.stafftemplate import StaffTemplate
from .apps.alternative_staff_template import AlternativeStaffTemplate
from .apps.staff_template_audit_log import StaffTemplateAuditLog
from .apps.routeplan import RoutePlan
from .apps.supervisor_zone_map import SupervisorZoneMap
from .apps.supervisor_zone_access_audit import SupervisorZoneAccessAudit
from .apps.unassigned_staff_pool import UnassignedStaffPool

# Attendance
from .apps.attendance import Employee, Recognized

# Vehicles / Trips
from .apps.vehicleTypeCreation import VehicleTypeCreation
from .apps.vehicleCreation import VehicleCreation
from .apps.trip_definition import TripDefinition
from .apps.trip_instance import TripInstance
from .apps.trip_attendance import TripAttendance
from .apps.trip_exception_log import TripExceptionLog
from .apps.vehicle_trip_audit import VehicleTripAudit
from .apps.bin_load_log import BinLoadLog


__all__ = [
    # Geography
    "Continent",
    "Country",
    "State",
    "District",
    "City",
    "Zone",
    "Ward",
    "Bin",
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
    "UserScreenPermission",
    "MainUserScreen",
    "UserPermission",
    "LoginAudit",
    "AuditLog",
    # Customer / Waste / Feedback
    "CustomerCreation",
    "CustomerTag",
    "WasteCollection",
    "FeedBack",
    "HouseholdPickupEvent",
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
