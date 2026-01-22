from django.urls import path, include
from .custom_router import GroupedRouter

from api.views.mobileView.citizen_login.new_login_views import LoginViewSet as MobileLoginViewSet
from api.views.mobileView.grievance.main_category_viewset import MainCategoryViewSet
from api.views.mobileView.grievance.sub_category_viewset import SubCategoryViewSet
from api.views.mobileView.attendance_view.register import RegisterViewSet
from api.views.mobileView.attendance_view.recognize import RecognizeViewSet
from api.views.mobileView.attendance_view.employee_viewset import EmployeeViewSet
from api.views.mobileView.attendance_view.staff_profile_viewset import StaffProfileViewSet
from api.views.mobileView.waste_collection_bluetooth.waste_bluetooth_viewset import WasteCollectionBluetoothViewSet
from api.views.mobileView.attendance_view.attendance_list import AttendanceListViewSet

router = GroupedRouter()

# Keep mobile endpoints clean under /api/mobile/<endpoint>/
router.register_group("mobile", "login", MobileLoginViewSet, basename="mobile-login", include_group_in_prefix=False)
router.register_group("mobile", "main-category", MainCategoryViewSet, basename="mobile-main-category", include_group_in_prefix=False)
router.register_group("mobile", "sub-category", SubCategoryViewSet, basename="mobile-sub-category", include_group_in_prefix=False)

router.register_group("mobile", "register", RegisterViewSet, basename="mobile-register", include_group_in_prefix=False)
router.register_group("mobile", "recognize", RecognizeViewSet, basename="mobile-recognize", include_group_in_prefix=False)
router.register_group("mobile", "employee", EmployeeViewSet, basename="mobile-employee", include_group_in_prefix=False)
router.register_group("mobile", "staff-profile", StaffProfileViewSet, basename="mobile-staff-profile", include_group_in_prefix=False)

router.register_group("mobile", "waste", WasteCollectionBluetoothViewSet, basename="mobile-waste-collection", include_group_in_prefix=False)
router.register_group("mobile", "attendance-list", AttendanceListViewSet, basename="mobile-attendance-list", include_group_in_prefix=False)

urlpatterns = [
    path("", include(router.urls)),
]
