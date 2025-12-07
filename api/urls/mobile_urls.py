from rest_framework.routers import DefaultRouter
from api.views.mobileView.grievance.sub_category_viewset import SubCategoryViewSet
from api.views.mobileView.grievance.main_category_viewset import MainCategoryViewSet
from api.views.mobileView.citizen_login.login_viewset import CitizenLoginViewSet
from api.views.mobileView.citizen_login.new_login_views import LoginViewSet
from api.views.mobileView.waste_collection_bluetooth.waste_bluetooth_viewset import WasteCollectionBluetoothViewSet
from ..views.mobileView.citizen_login.login_viewset import CitizenLoginViewSet  # ViewSet version
from ..views.mobileView.grievance.main_category_viewset import MainCategoryViewSet
from ..views.mobileView.grievance.sub_category_viewset import SubCategoryViewSet
from ..views.mobileView.citizen_login.new_login_views import LoginViewSet
from ..views.mobileView.attendance_view.register import RegisterViewSet
from ..views.mobileView.attendance_view.recognize import RecognizeViewSet
from ..views.mobileView.attendance_view.employee_viewset import EmployeeViewSet
from ..views.mobileView.attendance_view.staff_profile_viewset import StaffProfileViewSet
# from ..views.mobileView.grievance.sub_category_viewset import 

router = DefaultRouter()

router.register("customer/login", CitizenLoginViewSet, basename="customer-login")
router.register("main-category", MainCategoryViewSet, basename="main-category")
router.register("sub-category", SubCategoryViewSet, basename="sub-category")
router.register("login", LoginViewSet, basename="mobile-login")
router.register("register", RegisterViewSet, basename="register")
router.register("recognize", RecognizeViewSet, basename="recognize")
router.register("employee", EmployeeViewSet, basename="employee")
router.register("staff-profile", StaffProfileViewSet, basename="staff-profile")
router.register("waste", WasteCollectionBluetoothViewSet, basename="waste-collection")
urlpatterns = router.urls

urlpatterns = router.urls
