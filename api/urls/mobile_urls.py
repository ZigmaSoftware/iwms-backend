from django.urls import path
from ..views.mobileView.citizen_login.login_page import CitizenLoginPage
from ..views.mobileView.citizen_login.login_viewset import CitizenLogin

urlpatterns = [
    path("", CitizenLoginPage.as_view(), name="mobile-root"),
    path("customer/login/", CitizenLogin.as_view(), name="customer-login"),
]