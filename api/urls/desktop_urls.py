from django.urls import path, include

from .custom_router import GroupedRouter

# ============================================================
# IMPORTS
# ============================================================
# Masters
from ..viewsets.desktop.commonmasters.continent_viewset import ContinentViewSet
from ..viewsets.desktop.commonmasters.country_viewset import CountryViewSet
from ..viewsets.desktop.commonmasters.state_viewset import StateViewSet

from ..viewsets.desktop.masters.district_viewset import DistrictViewSet
from ..viewsets.desktop.masters.city_viewset import CityViewSet
from ..viewsets.desktop.masters.zone_viewset import ZoneViewSet
from ..viewsets.desktop.masters.ward_viewset import WardViewSet
from ..viewsets.desktop.masters.bin_viewset import BinViewSet



# Assets
from ..viewsets.desktop.assets.fuel_viewset import FuelViewSet
from ..viewsets.desktop.assets.property_viewset import PropertyViewSet
from ..viewsets.desktop.assets.subproperty_viewset import SubPropertyViewSet
from ..viewsets.desktop.assets.zone_property_load_tracker_viewset import ZonePropertyLoadTrackerViewSet

# Customer Modules
from ..viewsets.desktop.customers.customercreation_viewset import CustomerCreationViewSet
from ..viewsets.desktop.customers.wastecollection_viewset import WasteCollectionViewSet
from ..viewsets.desktop.customers.feedback_viewset import FeedBackViewSet

# Users - Role assignment
from ..viewsets.desktop.role_assign.usertype_viewset import UserTypeViewSet
from ..viewsets.desktop.role_assign.staffusertype_viewset import StaffUserTypeViewSet
# Users - Creation
from ..viewsets.desktop.user_creation.staff_viewset import StaffViewSet
from ..viewsets.desktop.users.login_viewset import LoginViewSet as DesktopLoginViewSet
from ..viewsets.desktop.user_creation.staffcreation_viewset import StaffcreationViewset
from ..viewsets.desktop.user_creation.stafftemplate_viewset import StaffTemplateViewSet
from ..viewsets.desktop.user_creation.alternative_stafftemplate_viewset import AlternativeStaffTemplateViewSet
from ..viewsets.desktop.user_creation.staff_template_audit_log_viewset import (
    StaffTemplateAuditLogViewSet,
)
from ..viewsets.desktop.user_creation.routeplan_viewset import RoutePlanViewSet
from ..viewsets.desktop.user_creation.supervisor_zone_map_viewset import SupervisorZoneMapViewSet
from ..viewsets.desktop.user_creation.supervisor_zone_access_audit_viewset import SupervisorZoneAccessAuditViewSet
from ..viewsets.desktop.user_creation.unassigned_staff_pool_viewset import UnassignedStaffPoolViewSet
from ..viewsets.desktop.vehicles.trip_attendance_viewset import TripAttendanceViewSet

# Screen Management
from ..viewsets.desktop.screenmanagement.mainscreentype_viewset import MainScreenTypeViewSet
from ..viewsets.desktop.screenmanagement.mainscreen_viewset import MainScreenViewSet
from ..viewsets.desktop.screenmanagement.userscreen_viewset import UserScreenViewSet
from ..viewsets.desktop.screenmanagement.userscreenaction_viewset import UserScreenActionViewSet
from ..viewsets.desktop.screenmanagement.companyuserscreenpermission_viewset import CompanyUserScreenPermissionViewSet

# Vehicles
from ..viewsets.desktop.vehicles.vehicletypecreation_viewset import VehicleTypeCreationViewSet
from ..viewsets.desktop.vehicles.vehicleCreation_viewset import VehicleCreationViewSet
from ..viewsets.desktop.vehicles.trip_definition_viewset import TripDefinitionViewSet
from ..viewsets.desktop.vehicles.trip_instance_viewset import TripInstanceViewSet
from ..viewsets.desktop.vehicles.vehicle_trip_audit_viewset import VehicleTripAuditViewSet
from ..viewsets.desktop.vehicles.trip_exception_log_viewset import TripExceptionLogViewSet
from ..viewsets.desktop.vehicles.bin_load_log_viewset import BinLoadLogViewSet

# Complaints
from ..viewsets.desktop.complaints.complaint_viewset import ComplaintViewSet

# Mobile
from api.viewsets.mobile.grievance.main_category_viewset import MainCategoryViewSet
from api.viewsets.mobile.grievance.sub_category_viewset import SubCategoryViewSet
from api.viewsets.mobile.waste_collection_bluetooth.waste_bluetooth_viewset import (WasteCollectionBluetoothViewSet,)
from api.viewsets.mobile.attendance_view.register import RegisterViewSet
from api.viewsets.mobile.attendance_view.recognize import RecognizeViewSet
from api.viewsets.mobile.attendance_view.employee_viewset import EmployeeViewSet
from api.viewsets.mobile.attendance_view.staff_profile_viewset import StaffProfileViewSet
from api.viewsets.mobile.attendance_view.attendance_list import AttendanceListViewSet

#Superadmin Masters


router = GroupedRouter()

# ============================================================
# GROUP: MASTERS
# ============================================================
router.register_group("common-masters", "continents",    ContinentViewSet)
router.register_group("common-masters", "countries",     CountryViewSet)
router.register_group("common-masters", "states",        StateViewSet)

# ============================================================
# GROUP: COMMON MASTERS
# ============================================================
router.register_group("masters", "districts",     DistrictViewSet)
router.register_group("masters", "cities",        CityViewSet)
router.register_group("masters", "zones",         ZoneViewSet)
router.register_group("masters", "wards",         WardViewSet)
router.register_group("masters", "bins",          BinViewSet)

# ============================================================
# GROUP: ASSETS
# ============================================================
router.register_group("assets", "fuels",         FuelViewSet)
router.register_group("assets", "properties",    PropertyViewSet)
router.register_group("assets", "subproperties", SubPropertyViewSet)
router.register_group("assets", "zone-property-load-tracker", ZonePropertyLoadTrackerViewSet)


# ============================================================
# GROUP: SCREEN MANAGEMENT (separate group)
# ============================================================
router.register_group("screen-management", "mainscreentype",        MainScreenTypeViewSet)
router.register_group("screen-management", "mainscreens",           MainScreenViewSet)
router.register_group("screen-management", "userscreens",           UserScreenViewSet)
router.register_group("screen-management", "userscreen-action",     UserScreenActionViewSet)
router.register_group("screen-management", "userscreenpermissions", CompanyUserScreenPermissionViewSet)


# ============================================================
# GROUP: USER & ROLE ASSIGNMENT
# ============================================================
router.register_group("role-assign", "user-type",      UserTypeViewSet)
router.register_group("role-assign", "staffusertypes", StaffUserTypeViewSet)

# ============================================================
# GROUP: USER CREATION (customer + staff + login)
# ============================================================
router.register_group("user-creation", "users-creation",  StaffViewSet)
router.register_group("user-creation", "staffcreation",   StaffcreationViewset)
router.register_group("user-creation", "stafftemplate-creation",  StaffTemplateViewSet)
router.register_group("user-creation", "alternative-stafftemplate",  AlternativeStaffTemplateViewSet)
router.register_group("user-creation", "stafftemplate-audit-log", StaffTemplateAuditLogViewSet)
router.register_group("user-creation", "route-plans",    RoutePlanViewSet)
router.register_group("user-creation", "supervisor-zone-map", SupervisorZoneMapViewSet)
router.register_group("user-creation", "supervisor-zone-access-audit", SupervisorZoneAccessAuditViewSet)
router.register_group("user-creation", "unassigned-staff-pool", UnassignedStaffPoolViewSet)


# ============================================================
# GROUP: login
# ============================================================
router.register_group("login", "login-user",      DesktopLoginViewSet)


# ============================================================
# GROUP: CUSTOMER MODULES
# ============================================================
router.register_group("customers", "customercreations", CustomerCreationViewSet)
router.register_group("customers", "wastecollections",  WasteCollectionViewSet)
router.register_group("customers", "feedbacks",         FeedBackViewSet)

# ============================================================
# GROUP: GRIVIENCE
# ============================================================
router.register_group("grivence", "complaints", ComplaintViewSet)
router.register_group("grivence","main-category", MainCategoryViewSet, basename="main-category")
router.register_group("grivence","sub-category", SubCategoryViewSet, basename="sub-category")

# ============================================================
# GROUP: VEHICLES
# ============================================================
router.register_group("vehicles", "vehicle-type",     VehicleTypeCreationViewSet)
router.register_group("vehicles", "vehicle-creation", VehicleCreationViewSet)
router.register_group("vehicles", "trip-definition",  TripDefinitionViewSet)
router.register_group("vehicles", "trip-instance",    TripInstanceViewSet)
router.register_group("vehicles", "bin-load-log",    BinLoadLogViewSet)
router.register_group("vehicles", "vehicle-trip-audit",    VehicleTripAuditViewSet)
router.register_group("vehicles", "trip-exception-log",    TripExceptionLogViewSet)
router.register_group("vehicles", "trip-attendance", TripAttendanceViewSet)


# ============================================================
# GROUP: MOBILE URLS
# ============================================================
router.register_group(
    "mobile",
    "login",
    DesktopLoginViewSet,
    basename="mobile-login",
    include_group_in_prefix=False,
)
router.register_group(
    "mobile",
    "main-category",
    MainCategoryViewSet,
    basename="mobile-main-category",
    include_group_in_prefix=False,
)
router.register_group(
    "mobile",
    "sub-category",
    SubCategoryViewSet,
    basename="mobile-sub-category",
    include_group_in_prefix=False,
)
router.register_group(
    "mobile",
    "register",
    RegisterViewSet,
    basename="mobile-register",
    include_group_in_prefix=False,
)
router.register_group(
    "mobile",
    "recognize",
    RecognizeViewSet,
    basename="mobile-recognize",
    include_group_in_prefix=False,
)
router.register_group(
    "mobile",
    "employee",
    EmployeeViewSet,
    basename="mobile-employee",
    include_group_in_prefix=False,
)
router.register_group(
    "mobile",
    "staff-profile",
    StaffProfileViewSet,
    basename="mobile-staff-profile",
    include_group_in_prefix=False,
)
router.register_group(
    "mobile",
    "waste",
    WasteCollectionBluetoothViewSet,
    basename="mobile-waste-collection",
    include_group_in_prefix=False,
)
router.register_group(
    "mobile",
    "attendance-list",
    AttendanceListViewSet,
    basename="mobile-attendance-list",
    include_group_in_prefix=False,
)


# ============================================================
# URLS
# ============================================================
urlpatterns = [
    path("", include(router.urls)),
]
