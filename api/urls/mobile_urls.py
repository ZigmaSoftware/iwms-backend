from django.urls import path, include
from rest_framework.routers import DefaultRouter

from ..views.mobileView.citizen_login.login_page import CitizenLoginPage
from ..views.mobileView.citizen_login.login_viewset import CitizenLoginViewSet  # ViewSet version

router = DefaultRouter()
router.register("customer/login", CitizenLoginViewSet, basename="customer-login")

urlpatterns = [
    path("login", CitizenLoginPage.as_view(), name="mobile-root"),
    path("", include(router.urls)),
]
