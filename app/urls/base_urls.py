from django.urls import include, path

from .custom_router import GroupedRouter

# ============================================================
# IMPORTS
# ============================================================

# Super admin masters
from ..viewsets.superadminmasters.company_management import PlatformCompanyCreateViewSet
from ..viewsets.superadminmasters.project_management import CompanyProjectCreateViewSet


# Common masters
from ..viewsets.common_masters.continent_viewset import ContinentViewSet
from ..viewsets.common_masters.country_viewset import CountryViewSet
from ..viewsets.common_masters.state_viewset import StateViewSet

# Masters
from ..viewsets.masters.city_viewset import CityViewSet
from ..viewsets.masters.district_viewset import DistrictViewSet
from ..viewsets.masters.zone_viewset import ZoneViewSet
from ..viewsets.masters.ward_viewset import WardViewSet

from ..viewsets.masters.panchayat_viweset import PanhayatViewSet
from ..viewsets.masters.areatype_viewset import AreaTypeViewSet
from ..viewsets.masters.hierarchy_viewset import AdministrativeHierarchyViewSet
from ..viewsets.masters.department_viewset import DepartmentViewSet
from ..viewsets.masters.designation_viewset import DesignationViewSet

from ..viewsets.assets.collection_point_viewset import CollectionPointViewSet
from ..viewsets.assets.bins_viewset import BinsViewSet
from ..viewsets.assets.point_collection_viewset import PointCollectionViewSet
from ..viewsets.assets.bins_viewset import BinsViewSet
from ..viewsets.collections.panchayat_wise_collection_viewset import PanchayatWiseCollectionViewSet
from ..viewsets.assets.weighbridge_viewset import WeighbridgeCheckViewSet
from ..viewsets.collections.ward_wise_collection_viewset import WardWiseCollectionViewSet
from ..viewsets.collections.zone_wise_collection_viewset import ZoneWiseCollectionViewSet

# Waste types
from ..viewsets.waste_types.property_viewset import PropertyViewSet
from ..viewsets.waste_types.subproperty_viewset import SubPropertyViewSet

# Processes
from ..viewsets.process.routeplan_viewset import RoutePlanViewSet
from ..viewsets.process.zone_property_load_tracker_viewset import ZonePropertyLoadTrackerViewSet

# Customer modules
from ..viewsets.customers.customercreation_viewset import CustomerCreationViewSet
from ..viewsets.customers.wastecollection_viewset import WasteCollectionViewSet
from ..viewsets.customers.feedback_viewset import FeedBackViewSet
from ..viewsets.customers.userchargerule_viewset import UserChargeRuleViewSet

# Role assignments
from ..viewsets.role_assigns.usertype_viewset import UserTypeViewSet
from ..viewsets.role_assigns.staffusertype_viewset import StaffUserTypeViewSet
from ..viewsets.role_assigns.contractorusertype_viewset import ContractorUserTypeViewSet

# User creations
from ..viewsets.user_creations.staff_viewset import StaffViewSet
from ..viewsets.user_creations.staffcreation_viewset import StaffcreationViewset
from ..viewsets.user_creations.stafftemplate_viewset import StaffTemplateViewSet
from ..viewsets.user_creations.alternative_stafftemplate_viewset import AlternativeStaffTemplateViewSet
from ..viewsets.user_creations.supervisor_zone_map_viewset import SupervisorZoneMapViewSet
from ..viewsets.user_creations.unassigned_staff_pool_viewset import UnassignedStaffPoolViewSet

# Authentication
from ..viewsets.login.login_viewset import LoginViewSet as DesktopLoginViewSet
from ..viewsets.login.permission_viewset import PermissionViewSet

# Screen management
from ..viewsets.screen_managements.mainscreentype_viewset import MainScreenTypeViewSet
from ..viewsets.screen_managements.mainscreen_viewset import MainScreenViewSet
from ..viewsets.screen_managements.userscreen_viewset import UserScreenViewSet
from ..viewsets.screen_managements.userscreenaction_viewset import UserScreenActionViewSet
from ..viewsets.screen_managements.companyuserscreenpermission_viewset import CompanyUserScreenPermissionViewSet
from ..viewsets.screen_managements.companyuserscreencolumnpermission_viewset import CompanyUserScreenColumnPermissionViewSet
from ..viewsets.screen_managements.permission_api_views import (
    CompanyPermissionsAPIView,
    PermissionAssignAPIView,
    UserScreenColumnsAPIView,
)

# Transport masters
from ..viewsets.transport_masters.vehicletypecreation_viewset import VehicleTypeCreationViewSet
from ..viewsets.transport_masters.vehicleCreation_viewset import VehicleCreationViewSet
from ..viewsets.transport_masters.trip_definition_viewset import TripDefinitionViewSet
from ..viewsets.transport_masters.trip_instance_viewset import TripInstanceViewSet
from ..viewsets.transport_masters.fuel_viewset import FuelViewSet
from ..viewsets.transport_masters.trip_attendance_viewset import TripAttendanceViewSet
from ..viewsets.transport_masters.trip_viewset import TripViewSet

# Daily Trip Assignment
from ..viewsets.transport_masters.daily_trip_assignment_viewset import DailyTripAssignmentViewSet
from ..viewsets.transport_masters.daily_trip_log_viewset import DailyTripLogViewSet

# Operator mobile
from ..viewsets.operator_mobile.my_trip_today_viewset import MyTripTodayViewSet
from ..viewsets.operator_mobile.validate_bin_qr_viewset import ValidateBinQrViewSet
from ..viewsets.operator_mobile.scan_bin_viewset import ScanBinViewSet
from ..viewsets.operator_mobile.trip_history_viewset import TripHistoryViewSet

# Audits
from ..viewsets.audits.vehicle_trip_audit_viewset import VehicleTripAuditViewSet
from ..viewsets.audits.trip_exception_log_viewset import TripExceptionLogViewSet
from ..viewsets.audits.supervisor_zone_access_audit_viewset import SupervisorZoneAccessAuditViewSet
from ..viewsets.audits.staff_template_audit_log_viewset import StaffTemplateAuditLogViewSet
from ..viewsets.audits.audit_log_viewset import AuditLogViewSet
from ..viewsets.audits.login_audit_viewset import LoginAuditViewSet

from ..viewsets.audits.common_audit_viewset import CommonAuditViewSet

# Grivences
from ..viewsets.grivences.complaint_viewset import ComplaintViewSet
from ..viewsets.grivences.main_category_viewset import MainCategoryViewSet
from ..viewsets.grivences.sub_category_viewset import SubCategoryViewSet

# Mobile
from ..viewsets.waste_collection_bluetooth.waste_bluetooth_viewset import WasteCollectionBluetoothViewSet
from ..viewsets.waste_collection_bluetooth.waste_type_viewset import WasteTypeViewSet
from ..viewsets.waste_collection_bluetooth.waste_collection_sub_viewset import WasteCollectionSubViewSet
from ..viewsets.waste_collection_bluetooth.waste_collection_main_viewset import WasteCollectionMainViewSet
from ..viewsets.attendance_view.register import RegisterViewSet
from ..viewsets.attendance_view.recognize import RecognizeViewSet
from ..viewsets.attendance_view.employee_viewset import EmployeeViewSet
from ..viewsets.attendance_view.staff_profile_viewset import StaffProfileViewSet
from ..viewsets.attendance_view.attendance_list import AttendanceListViewSet
from ..viewsets.reports.monthly_waste_comparison_viewset import MonthlyWasteComparisonReportViewSet


router = GroupedRouter()
# customer_property_user_count = CustomerCreationViewSet.as_view(
#     {"get": "property_user_count"}
# )

# ============================================================
# GROUP: SUPERADMIN MASTERS
# ============================================================
router.register_group("superadmin","company",PlatformCompanyCreateViewSet)
router.register_group("superadmin","project",CompanyProjectCreateViewSet)

# ============================================================
# GROUP: COMMON MASTERS
# ============================================================
router.register_group("common-masters", "continents",    ContinentViewSet)
router.register_group("common-masters", "countries",     CountryViewSet)
router.register_group("common-masters", "states",        StateViewSet)


# ============================================================
# GROUP: MASTERS
# ============================================================
router.register_group("masters", "districts",     DistrictViewSet)
router.register_group("masters", "cities",        CityViewSet)
router.register_group("masters", "zones",         ZoneViewSet)
router.register_group("masters", "wards",         WardViewSet)
router.register_group("masters", "panchayat",         PanhayatViewSet)
router.register_group("masters", "areatypes",         AreaTypeViewSet)
router.register_group("masters", "hierarchy",         AdministrativeHierarchyViewSet)
router.register_group("masters", "departments",       DepartmentViewSet)
router.register_group("masters", "designations",      DesignationViewSet)



# ============================================================
# GROUP: Waste-Type
# ============================================================
router.register_group("waste-types", "properties",    PropertyViewSet)
router.register_group("waste-types", "subproperties", SubPropertyViewSet)


# ============================================================
# GROUP: Assets
# ============================================================

router.register_group("assets", "collection-point", CollectionPointViewSet)
router.register_group("assets","waste-types", WasteTypeViewSet)
router.register_group("assets", "bins", BinsViewSet)


# ============================================================
# GROUP: SCREEN MANAGEMENT (separate group)
# ============================================================
router.register_group("screen-managements", "mainscreentype",        MainScreenTypeViewSet)
router.register_group("screen-managements", "mainscreens",           MainScreenViewSet)
router.register_group("screen-managements", "userscreens",           UserScreenViewSet)
router.register_group("screen-managements", "userscreen-action",     UserScreenActionViewSet)
router.register_group("screen-managements", "companywisescreenpermissions", CompanyUserScreenPermissionViewSet)
router.register_group("screen-managements", "column-permissions", CompanyUserScreenColumnPermissionViewSet)


# ============================================================
# GROUP: USER & ROLE ASSIGNMENT 
# ============================================================
router.register_group("role-assigns", "user-type",           UserTypeViewSet)
router.register_group("role-assigns", "staffusertypes",      StaffUserTypeViewSet)
router.register_group("role-assigns", "staffusertypes",      StaffUserTypeViewSet, basename="staffusertype-roletype")
router.register_group("role-assigns", "contractorusertypes", ContractorUserTypeViewSet)
router.register_group("role-assigns", "contractorusertypes", ContractorUserTypeViewSet, basename="contractorusertype-roletype")

# ============================================================
# GROUP: USER CREATION
# ============================================================
router.register_group("user-creations", "users-creation",  StaffViewSet)
router.register_group("user-creations", "staffcreation",   StaffcreationViewset)
router.register_group("user-creations", "stafftemplate-creation",  StaffTemplateViewSet)
router.register_group("user-creations", "alternative-stafftemplate",  AlternativeStaffTemplateViewSet)
router.register_group("user-creations", "supervisor-zone-map", SupervisorZoneMapViewSet)
router.register_group("user-creations", "unassigned-staff-pool", UnassignedStaffPoolViewSet)



# ============================================================
# GROUP: PROCESS
# ============================================================
router.register_group("process-items", "route-plans",    RoutePlanViewSet)
router.register_group("process-items", "zone-property-load-tracker", ZonePropertyLoadTrackerViewSet)


# ============================================================
# GROUP: AUTHENTICATION
# ============================================================
router.register_group("login", "login-user",      DesktopLoginViewSet)
router.register_group("login", "my-permissions",     PermissionViewSet, basename="user-permissions")


# ============================================================
# GROUP: CUSTOMER MODULES
# ============================================================
router.register_group("customer-masters", "customercreations", CustomerCreationViewSet)
router.register_group("customer-masters", "wastecollections",  WasteCollectionViewSet)
router.register_group("customer-masters", "feedbacks",         FeedBackViewSet)
router.register_group("customer-masters", "user-charge-rules", UserChargeRuleViewSet)


# ============================================================
# GROUP: GRIEVANCES
# ============================================================
router.register_group("grivences", "complaints", ComplaintViewSet)
router.register_group("grivences","main-category", MainCategoryViewSet, basename="main-category")
router.register_group("grivences","sub-category", SubCategoryViewSet, basename="sub-category")

# ============================================================
# GROUP: TRANSPORT MASTERS
# ============================================================
router.register_group("transport-masters", "vehicle-type",     VehicleTypeCreationViewSet)
router.register_group("transport-masters", "vehicle-creation", VehicleCreationViewSet)
router.register_group("transport-masters", "trip-definition",  TripDefinitionViewSet)
router.register_group("transport-masters", "trip-instance",    TripInstanceViewSet)
router.register_group("transport-masters", "trip-attendance", TripAttendanceViewSet)
router.register_group("transport-masters", "fuels",         FuelViewSet)
router.register_group("transport-masters", "daily-trip-assignments",         DailyTripAssignmentViewSet)
router.register_group("transport-masters", "daily-trip-logs",         DailyTripLogViewSet)
# Alias for frontend and existing clients using singular path
router.register_group(
    "transport-masters",
    "daily-trip-assignment",
    DailyTripAssignmentViewSet,
    basename="transport-masters-daily-trip-assignment",
)
router.register_group(
    "transport-masters",
    "daily-trip-log",
    DailyTripLogViewSet,
    basename="transport-masters-daily-trip-log",
)

# ============================================================
# GROUP: OPERATOR MOBILE
# ============================================================
router.register_group(
    "operator-mobile",
    "my-trip-today",
    MyTripTodayViewSet,
    basename="operator-mobile-my-trip-today",
)
router.register_group(
    "operator-mobile",
    "validate-bin-qr",
    ValidateBinQrViewSet,
    basename="operator-mobile-validate-bin-qr",
)
router.register_group(
    "operator-mobile",
    "scan-bin",
    ScanBinViewSet,
    basename="operator-mobile-scan-bin",
)
router.register_group(
    "operator-mobile",
    "trip-history",
    TripHistoryViewSet,
    basename="operator-mobile-trip-history",
)


# ============================================================
# GROUP: AUDIT
# ============================================================
router.register_group("audits", "vehicle-trip-audit",    VehicleTripAuditViewSet)
router.register_group("audits", "trip-exception-log",    TripExceptionLogViewSet)
router.register_group("audits", "supervisor-zone-access-audit", SupervisorZoneAccessAuditViewSet)
router.register_group("audits", "stafftemplate-audit-log", StaffTemplateAuditLogViewSet)
router.register_group("audits", "audit-log", AuditLogViewSet)
router.register_group("audits", "login-audit", LoginAuditViewSet)

router.register_group("audits", "common-audit", CommonAuditViewSet)

# ============================================================
# GROUP: WASTE BLUETOOTH
# ============================================================
router.register_group("waste-bluetooth", "types", WasteTypeViewSet)
router.register_group("waste-bluetooth", "collection-sub", WasteCollectionSubViewSet)
router.register_group("waste-bluetooth", "collection-main", WasteCollectionMainViewSet)


# ============================================================
# GROUP: TRIP ASSIGNMENTS
# ============================================================
# router.register_group("trip-assignments", "daily", DailyTripAssignmentViewSet)


# ============================================================
# GROUP: COLLECTIONS
# ============================================================
router.register_group("collections", "point-collection", PointCollectionViewSet)
router.register_group("collections", "panchayat-wise", PanchayatWiseCollectionViewSet)
router.register_group("collections", "ward-wise", WardWiseCollectionViewSet)
router.register_group("collections", "zone-wise", ZoneWiseCollectionViewSet)

# ============================================================
# GROUP: REPORTS
# ============================================================
router.register_group("reports", "monthly-waste-comparison", MonthlyWasteComparisonReportViewSet, basename="monthly-waste-comparison")

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
    path(
        "permissions/userscreen/<str:userscreen_id>/columns/",
        UserScreenColumnsAPIView.as_view(),
    ),
    path("permissions/assign/", PermissionAssignAPIView.as_view()),
    path("permissions/company/<str:company_id>/", CompanyPermissionsAPIView.as_view()),
    path("", include(router.urls)),
]
