from django.urls import path

from api.views.platform.project_management import CompanyAdditionalProjectCreateView

urlpatterns = [
    path("projects/", CompanyAdditionalProjectCreateView.as_view(), name="company-project-create"),
]
