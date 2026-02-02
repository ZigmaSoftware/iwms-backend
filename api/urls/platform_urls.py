from django.urls import path

from api.views.platform.platform_login import PlatformLoginView
from api.views.platform.company_management import PlatformCompanyCreateView
from api.views.platform.project_management import (
    PlatformFirstProjectCreateView,
)

urlpatterns = [
    path("auth/login/", PlatformLoginView.as_view(), name="platform-login"),
    path("companies/", PlatformCompanyCreateView.as_view(), name="platform-company-create"),
    path(
        "companies/<str:company_unique_id>/projects/first/",
        PlatformFirstProjectCreateView.as_view(),
        name="platform-first-project-create",
    ),
]
