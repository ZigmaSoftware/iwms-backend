from django.urls import include, path

from .custom_router import GroupedRouter

# ============================================================
# IMPORTS
# ============================================================

# Superadmin masters
from ..viewsets.superadminmasters.company_management import PlatformCompanyCreateViewSet
from ..viewsets.superadminmasters.project_management import CompanyProjectCreateViewSet

# Common masters
from ..viewsets.superadmin.common_masters.continent_viewset import ContinentViewSet
from ..viewsets.superadmin.common_masters.country_viewset import CountryViewSet
from ..viewsets.superadmin.common_masters.state_viewset import StateViewSet

# Masters
from ..viewsets.masters.district_viewset import DistrictViewSet
from ..viewsets.masters.city_viewset import CityViewSet
from ..viewsets.masters.zone_viewset import ZoneViewSet
from ..viewsets.masters.ward_viewset import WardViewSet
from ..viewsets.masters.panchayat_viweset import PanhayatViewSet
from ..viewsets.masters.leader_management.panchayat_leader_viewset import PanchayatLeaderLoginViewSet
from ..viewsets.masters.leader_management.district_leader_viewset import DistrictLeaderLoginViewSet
from ..viewsets.masters.hierarchy_viewset import AdministrativeHierarchyViewSet
from ..viewsets.masters.department_viewset import DepartmentViewSet
from ..viewsets.masters.designation_viewset import DesignationViewSet

# Waste types (merged from the legacy "assets" group)
from ..viewsets.masters.waste_masters.property_viewset import PropertyViewSet
from ..viewsets.masters.waste_masters.subproperty_viewset import SubPropertyViewSet
from ..viewsets.waste_collection_bluetooth.waste_type_viewset import WasteTypeViewSet
from ..viewsets.masters.waste_masters.bins_viewset import BinsViewSet

# Screen management
from ..viewsets.superadmin.screen_management.mainscreentype_viewset import MainScreenTypeViewSet
from ..viewsets.superadmin.screen_management.mainscreen_viewset import MainScreenViewSet
from ..viewsets.superadmin.screen_management.userscreen_viewset import UserScreenViewSet
from ..viewsets.superadmin.screen_management.userscreenaction_viewset import UserScreenActionViewSet
from ..viewsets.superadmin.screen_management.companyuserscreenpermission_viewset import CompanyUserScreenPermissionViewSet
from ..viewsets.superadmin.screen_management.companyuserscreencolumnpermission_viewset import CompanyUserScreenColumnPermissionViewSet
from ..viewsets.superadmin.screen_management.permission_api_views import (
    CompanyPermissionsAPIView,
    PermissionAssignAPIView,
    UserScreenColumnsAPIView,
)

# Role assignments
from ..viewsets.superadmin.role_management.usertype_viewset import UserTypeViewSet
from ..viewsets.superadmin.role_management.staffusertype_viewset import StaffUserTypeViewSet
from ..viewsets.superadmin.role_management.contractorusertype_viewset import ContractorUserTypeViewSet

# User creations
from ..viewsets.superadmin.staff_management.staff_viewset import StaffViewSet
from ..viewsets.superadmin.staff_management.staffcreation_viewset import StaffcreationViewset
from ..viewsets.superadmin.staff_management.staff_access_configuration_viewset import (
    StaffAccessConfigurationViewSet,
)
from ..viewsets.superadmin.staff_management.unassigned_staff_pool_viewset import UnassignedStaffPoolViewSet

# Authentication
from ..viewsets.login.login_viewset import LoginViewSet as DesktopLoginViewSet
from ..viewsets.login.permission_viewset import PermissionViewSet
from ..viewsets.auth.forgot_password_viewset import (
    ForgotPasswordView,
    VerifyOTPView,
    ResetPasswordView,
)
from ..viewsets.auth.change_password_viewset import (
    ChangePasswordView,
    AdminChangePasswordView,
)

# Customer modules
from ..viewsets.masters.customer_masters.customercreation_viewset import CustomerCreationViewSet
from ..viewsets.core_modules.daily_operations.wastecollection_viewset import WasteCollectionViewSet
from ..viewsets.masters.customer_masters.feedback_viewset import FeedBackViewSet
from ..viewsets.masters.customer_masters.userchargerule_viewset import UserChargeRuleViewSet

# Complaint ticket (renamed from the legacy "grivences" group)
from ..viewsets.core_modules.complaint_management.complaint_viewset import ComplaintViewSet
from ..viewsets.core_modules.complaint_management.main_category_viewset import MainCategoryViewSet
from ..viewsets.core_modules.complaint_management.sub_category_viewset import SubCategoryViewSet
from ..viewsets.core_modules.complaint_management.complaint_ticket_stub_viewsets import (
    ComplaintModuleViewSet,
    ComplaintPriorityViewSet,
    ComplaintStatusViewSet,
    ComplaintSourceViewSet,
    ComplaintLanguageViewSet,
    ComplaintTeamViewSet,
    ComplaintSlaRuleViewSet,
    ComplaintRoutingRuleViewSet,
    ComplaintFeedbackViewSet,
    ComplaintReopenHistoryViewSet,
    ComplaintNotificationViewSet,
    ComplaintAddressChangeViewSet,
)

# Transport masters
from ..viewsets.masters.transport_masters.vehicletypecreation_viewset import VehicleTypeCreationViewSet
from ..viewsets.masters.transport_masters.vehicleCreation_viewset import VehicleCreationViewSet
from ..viewsets.masters.transport_masters.trip_attendance_viewset import TripAttendanceViewSet
from ..viewsets.masters.transport_masters.fuel_viewset import FuelViewSet

# Schedule masters
from ..viewsets.core_modules.schedule_setup.staff_template_viewset import StaffTemplateViewSet
from ..viewsets.core_modules.schedule_setup.alternative_staff_template_viewset import AlternativeStaffTemplateViewSet
from ..viewsets.core_modules.schedule_setup.collection_point_viewset import CollectionPointViewSet
from ..viewsets.core_modules.schedule_setup.trip_plan_viewset import TripPlanViewSet
from ..viewsets.core_modules.daily_operations.daily_trip_assignment_viewset import DailyTripAssignmentViewSet
from ..viewsets.core_modules.daily_operations.daily_trip_collection_point_viewset import DailyTripCollectionPointViewSet
from ..viewsets.core_modules.daily_operations.daily_trip_household_collection_viewset import DailyTripHouseholdCollectionViewSet
from ..viewsets.core_modules.daily_operations.bin_collection_event_viewset import BinCollectionEventViewSet
from ..viewsets.core_modules.daily_operations.daily_trip_log_viewset import DailyTripLogViewSet
from ..viewsets.reports.waste_reports.monthly_waste_comparison_viewset import MonthlyWasteComparisonReportViewSet
from ..viewsets.reports.waste_reports.daily_waste_comparison_viewset import DailyWasteComparisonViewSet
from ..viewsets.core_modules.daily_operations.vehicle_breakdown_viewset import VehicleBreakdownViewSet

# Audits
from ..viewsets.superadmin.audits.login_audit_viewset import LoginAuditViewSet
from ..viewsets.superadmin.audits.common_audit_viewset import CommonAuditViewSet

# Palakad district admin portal
from ..viewsets.palakad.palakad_login_viewset import PalakadLoginViewSet

# Localbody
from ..viewsets.localbody.localbody_dashboard_viewset import LocalBodyDashboardViewSet
# District dashboard
from ..viewsets.district.district_dashboard_viewset import DistrictDashboardViewSet

# Operator mobile
from ..viewsets.operator_mobile.my_trip_today_viewset import MyTripTodayViewSet
from ..viewsets.operator_mobile.validate_bin_qr_viewset import ValidateBinQrViewSet
from ..viewsets.operator_mobile.scan_bin_viewset import ScanBinViewSet
from ..viewsets.operator_mobile.trip_history_viewset import TripHistoryViewSet

# Waste bluetooth
from ..viewsets.waste_collection_bluetooth.waste_bluetooth_viewset import WasteCollectionBluetoothViewSet
from ..viewsets.waste_collection_bluetooth.waste_collection_sub_viewset import WasteCollectionSubViewSet
from ..viewsets.waste_collection_bluetooth.waste_collection_main_viewset import WasteCollectionMainViewSet

# Mobile
from ..viewsets.core_modules.attendance.register import RegisterViewSet
from ..viewsets.core_modules.attendance.recognize import RecognizeViewSet
from ..viewsets.core_modules.attendance.employee_viewset import EmployeeViewSet
from ..viewsets.core_modules.attendance.staff_profile_viewset import StaffProfileViewSet
from ..viewsets.core_modules.attendance.attendance_list import AttendanceListViewSet
from ..viewsets.core_modules.attendance.external_attendance import ExternalAttendanceViewSet


router = GroupedRouter()

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
router.register_group("masters", "panchayat-leaders", PanchayatLeaderLoginViewSet)
router.register_group("masters", "district-leaders", DistrictLeaderLoginViewSet)
router.register_group("masters", "hierarchy",         AdministrativeHierarchyViewSet)
router.register_group("masters", "departments",       DepartmentViewSet)
router.register_group("masters", "designations",      DesignationViewSet)


# ============================================================
# GROUP: Waste-Type (merged from the legacy "assets" group — the
# old assets/waste-types + assets/bins endpoints now live here as
# waste-types/wastetypes + waste-types/bins, matching the government
# reference app's grouping exactly)
# ============================================================
router.register_group("waste-types", "properties",    PropertyViewSet)
router.register_group("waste-types", "subproperties", SubPropertyViewSet)
router.register_group("waste-types", "wastetypes",    WasteTypeViewSet)
router.register_group("waste-types", "bins",          BinsViewSet)

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
router.register_group(
    "user-creations", "staff-access-configuration", StaffAccessConfigurationViewSet
)

# ============================================================
# GROUP: AUTHENTICATION
# ============================================================
router.register_group("login", "login-user",      DesktopLoginViewSet)
router.register_group("login", "my-permissions",     PermissionViewSet, basename="user-permissions")

# ============================================================
# GROUP: CUSTOMER MODULES
# ============================================================
router.register_group("customer-masters", "customercreations", CustomerCreationViewSet)
router.register_group("customer-masters", "feedbacks",         FeedBackViewSet)
router.register_group("customer-masters", "user-charge-rules", UserChargeRuleViewSet)

# ============================================================
# GROUP: COMPLAINT TICKET (renamed from the legacy "grivences" group;
# tickets/categories/subcategories are the existing resources, renamed
# to match government's naming. The remaining entries are stub
# ViewSets (no backing model yet) mirroring government's fuller
# complaint-ticket sub-resource set — see
# app/viewsets/grivences/complaint_ticket_stub_viewsets.py.
# ============================================================
router.register_group("complaint-ticket", "tickets", ComplaintViewSet)
router.register_group("complaint-ticket", "categories", MainCategoryViewSet)
router.register_group("complaint-ticket", "subcategories", SubCategoryViewSet)
router.register_group("complaint-ticket", "modules", ComplaintModuleViewSet, basename="complaint-ticket-modules")
router.register_group("complaint-ticket", "priorities", ComplaintPriorityViewSet, basename="complaint-ticket-priorities")
router.register_group("complaint-ticket", "statuses", ComplaintStatusViewSet, basename="complaint-ticket-statuses")
router.register_group("complaint-ticket", "sources", ComplaintSourceViewSet, basename="complaint-ticket-sources")
router.register_group("complaint-ticket", "languages", ComplaintLanguageViewSet, basename="complaint-ticket-languages")
router.register_group("complaint-ticket", "teams", ComplaintTeamViewSet, basename="complaint-ticket-teams")
router.register_group("complaint-ticket", "sla-rules", ComplaintSlaRuleViewSet, basename="complaint-ticket-sla-rules")
router.register_group("complaint-ticket", "routing-rules", ComplaintRoutingRuleViewSet, basename="complaint-ticket-routing-rules")
router.register_group("complaint-ticket", "feedback", ComplaintFeedbackViewSet, basename="complaint-ticket-feedback")
router.register_group("complaint-ticket", "reopen-history", ComplaintReopenHistoryViewSet, basename="complaint-ticket-reopen-history")
router.register_group("complaint-ticket", "notifications", ComplaintNotificationViewSet, basename="complaint-ticket-notifications")
router.register_group("complaint-ticket", "address-change", ComplaintAddressChangeViewSet, basename="complaint-ticket-address-change")

# ============================================================
# GROUP: TRANSPORT MASTERS
# ============================================================
router.register_group("transport-masters", "vehicle-type",     VehicleTypeCreationViewSet)
router.register_group("transport-masters", "vehicle-creation", VehicleCreationViewSet)
router.register_group("transport-masters", "trip-attendance", TripAttendanceViewSet)
router.register_group("transport-masters", "fuels",         FuelViewSet)

# ============================================================
# GROUP: SCHEDULE SETUP (split from the legacy "schedule-masters"
# group — template/plan setup resources)
# ============================================================
router.register_group("schedule-setup", "staff-templates", StaffTemplateViewSet)
router.register_group("schedule-setup", "alternative-staff-templates", AlternativeStaffTemplateViewSet)
router.register_group("schedule-setup", "collection-points", CollectionPointViewSet)
router.register_group("schedule-setup", "trip-plans", TripPlanViewSet)

# ============================================================
# GROUP: SCHEDULE OPERATIONS (split from the legacy "schedule-masters"
# group — day-to-day execution resources)
# ============================================================
router.register_group("schedule-operations", "daily-trip-assignments", DailyTripAssignmentViewSet)
router.register_group("schedule-operations", "daily-trip-collection-points", DailyTripCollectionPointViewSet)
router.register_group("schedule-operations", "daily-trip-household-collections", DailyTripHouseholdCollectionViewSet)
router.register_group("schedule-operations", "bin-collection-events", BinCollectionEventViewSet)
router.register_group("schedule-operations", "daily-trip-logs", DailyTripLogViewSet)
router.register_group("schedule-operations", "wastecollections", WasteCollectionViewSet)
router.register_group("schedule-operations", "vehicle-breakdowns", VehicleBreakdownViewSet)

# ============================================================
# GROUP: SCHEDULE MASTERS (legacy name — kept alive only for the
# reporting sub-resources, matching the government reference app's
# equivalent split; setup/operations resources above are no longer
# registered under this group)
# ============================================================
router.register_group("schedule-masters", "daily-waste-comparisons", DailyWasteComparisonViewSet)
router.register_group("schedule-masters", "monthly-waste-comparison", MonthlyWasteComparisonReportViewSet, basename="monthly-waste-comparison")

# ============================================================
# GROUP: REPORTS (aliases used by the admin frontend)
# ============================================================
router.register_group("reports", "monthly-waste-comparison", MonthlyWasteComparisonReportViewSet, basename="reports-monthly-waste-comparison")
router.register_group("reports", "daily-waste-comparisons", DailyWasteComparisonViewSet, basename="reports-daily-waste-comparisons")

# ============================================================
# GROUP: AUDIT
# ============================================================
router.register_group("audits", "login-audit", LoginAuditViewSet)
router.register_group("audits", "common-audit", CommonAuditViewSet)

# ============================================================
# GROUP: EXTERNAL ATTENDANCE
# ============================================================
router.register_group(
    "attendance",
    "external-records",
    ExternalAttendanceViewSet,
    basename="external-attendance",
)

# ============================================================
# GROUP: PALAKAD (company admin district portal)
# ============================================================
router.register_group("palakad", "login-user", PalakadLoginViewSet, basename="palakad-login")

# ============================================================
# GROUP: LOCALBODY (panchayat leader portal — auth-only, no module permission check)
# ============================================================
router.register_group("localbody", "dashboard", LocalBodyDashboardViewSet, basename="localbody-dashboard")
# ============================================================
# GROUP: DISTRICT (district member portal)
# ============================================================
router.register_group("district", "dashboard", DistrictDashboardViewSet, basename="district-dashboard")

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
# GROUP: WASTE BLUETOOTH
# ============================================================
router.register_group("waste-bluetooth", "types", WasteTypeViewSet)
router.register_group("waste-bluetooth", "collection-sub", WasteCollectionSubViewSet)
router.register_group("waste-bluetooth", "collection-main", WasteCollectionMainViewSet)


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
    # Password reset flow (public — no authentication required)
    path("auth/forgot-password/", ForgotPasswordView.as_view(), name="auth-forgot-password"),
    path("auth/verify-otp/", VerifyOTPView.as_view(), name="auth-verify-otp"),
    path("auth/reset-password/", ResetPasswordView.as_view(), name="auth-reset-password"),
    # Authenticated password change (self-service and admin)
    path("auth/change-password/", ChangePasswordView.as_view(), name="auth-change-password"),
    path("auth/admin-change-password/", AdminChangePasswordView.as_view(), name="auth-admin-change-password"),

    path(
        "permissions/userscreen/<str:userscreen_id>/columns/",
        UserScreenColumnsAPIView.as_view(),
    ),
    path("permissions/assign/", PermissionAssignAPIView.as_view()),
    path("permissions/company/<str:company_id>/", CompanyPermissionsAPIView.as_view()),
    path("", include(router.urls)),
]
