from django.urls import path, include
from rest_framework.routers import DefaultRouter
from api.views.mobileView.waste_collection_bluetooth.waste_bluetooth_viewset import WasteCollectionBluetoothViewSet
from ..views.mobileView.citizen_login.login_viewset import CitizenLoginViewSet  # ViewSet version
from ..views.mobileView.grievance.main_category_viewset import MainCategoryViewSet
from ..views.mobileView.grievance.sub_category_viewset import SubCategoryViewSet
from ..views.mobileView.citizen_login.new_login_views import LoginViewSet
# from ..views.mobileView.grievance.sub_category_viewset import 

router = DefaultRouter()
router.register("customer/login", CitizenLoginViewSet, basename="customer-login")
router.register("main-category", MainCategoryViewSet, basename="main-category")
router.register("subcategory", SubCategoryViewSet, basename="subcategory")
router.register("login", LoginViewSet, basename="mobile-login")
router.register("waste", WasteCollectionBluetoothViewSet, basename="waste")

urlpatterns = router.urls

