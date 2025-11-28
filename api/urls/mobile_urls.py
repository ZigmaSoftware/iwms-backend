from django.urls import path, include
from rest_framework.routers import DefaultRouter
from api.views.mobileView.waste_collection_bluetooth.waste_bluetooth_viewset import WasteCollectionViewSet
from ..views.mobileView.citizen_login.login_viewset import CitizenLoginViewSet  # ViewSet version
from ..views.mobileView.grievance.main_category_viewset import MainCategoryViewSet
from ..views.mobileView.grievance.sub_category_viewset import SubCategoryViewSet 

router = DefaultRouter()
router.register("customer/login", CitizenLoginViewSet, basename="customer-login")
router.register("main-category", MainCategoryViewSet, basename="main-category")
router.register("subcategory", SubCategoryViewSet, basename="subcategory")
router.register("waste", WasteCollectionViewSet, basename="waste")

# router.register("insert-waste-sub/", WasteCollectionViewSet.insert_waste_sub, basename="insert-waste-sub/")
# router.register("update-waste-sub/", WasteCollectionViewSet.update_waste_sub, basename="update-waste-sub/")
# router.register("get-waste-types/", WasteCollectionViewSet.get_saved_waste, basename="get-waste-types/")
# router.register("get-latest-waste/", WasteCollectionViewSet.get_latest_waste, basename="get-latest-waste/")
# router.register("finalize-waste/", WasteCollectionViewSet.finalize_waste_collection, basename="finalize-waste/")

urlpatterns = router.urls       
