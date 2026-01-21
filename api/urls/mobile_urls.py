from rest_framework.routers import DefaultRouter
from api.views.mobileView.grievance.sub_category_viewset import SubCategoryViewSet
from api.views.mobileView.grievance.main_category_viewset import MainCategoryViewSet
from api.views.mobileView.citizen_login.new_login_views import LoginViewSet
from api.views.mobileView.waste_collection_bluetooth.waste_bluetooth_viewset import (WasteCollectionBluetoothViewSet,)
from api.views.mobileView.attendance_view.register import RegisterViewSet
from api.views.mobileView.attendance_view.recognize import RecognizeViewSet
from api.views.mobileView.attendance_view.employee_viewset import EmployeeViewSet
from api.views.mobileView.attendance_view.staff_profile_viewset import StaffProfileViewSet
from api.views.mobileView.attendance_view.attendance_list import AttendanceListViewSet

router = DefaultRouter()

router.register("login", LoginViewSet, basename="mobile-login")
router.register("main-category", MainCategoryViewSet, basename="main-category")
router.register("sub-category", SubCategoryViewSet, basename="sub-category")
router.register("register", RegisterViewSet, basename="register")
router.register("recognize", RecognizeViewSet, basename="recognize")
router.register("employee", EmployeeViewSet, basename="employee")
router.register("staff-profile", StaffProfileViewSet, basename="staff-profile")
router.register("waste", WasteCollectionBluetoothViewSet, basename="waste-collection")
router.register("attendance-list", AttendanceListViewSet, basename="attendance_list")
urlpatterns = router.urls
