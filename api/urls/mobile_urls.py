from rest_framework.routers import DefaultRouter
from api.views.mobileView.grievance.sub_category_viewset import SubCategoryViewSet
from api.views.mobileView.grievance.main_category_viewset import MainCategoryViewSet
from api.views.mobileView.citizen_login.login_viewset import CitizenLoginViewSet
from api.views.mobileView.citizen_login.new_login_views import LoginViewSet
from api.views.mobileView.waste_collection_bluetooth.waste_bluetooth_viewset import WasteCollectionBluetoothViewSet

router = DefaultRouter()

router.register("customer/login", CitizenLoginViewSet, basename="customer-login")
router.register("main-category", MainCategoryViewSet, basename="main-category")
router.register("sub-category", SubCategoryViewSet, basename="sub-category")
router.register("login", LoginViewSet, basename="mobile-login")

urlpatterns = router.urls
