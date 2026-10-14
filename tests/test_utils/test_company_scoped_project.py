from datetime import time
from types import SimpleNamespace

import pytest
from django.utils import timezone
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from app.models.core_modules.daily_operations.daily_trip_assignment import DailyTripAssignment
from app.serializers.core_modules.daily_operations.vehicle_breakdown_serializer import (
    VehicleBreakdownSerializer,
)
from app.viewsets.superadmin_masters.company_scoped_viewset import CompanyScopedViewSet


@pytest.mark.django_db
def test_project_falls_back_to_plain_staff_project_id(company, project):
    request = Request(
        APIRequestFactory().get("/vehicle-breakdowns/")
    )
    request.user = SimpleNamespace(
        company_id=company.unique_id,
        project_id=project.unique_id,
        is_authenticated=True,
    )

    view = CompanyScopedViewSet()
    view.request = request

    assert view._project() == project


@pytest.mark.django_db
def test_breakdown_uses_assignment_vehicle_and_tenant(company, project):
    assignment = DailyTripAssignment.objects.create(
        company_id=company.unique_id,
        project_id=project.unique_id,
        trip_date=timezone.localdate(),
        scheduled_time=time(9, 0),
        vehicle_id="VEH-ASSIGNED",
    )
    request = SimpleNamespace(
        user=SimpleNamespace(
            company_id=company.unique_id,
            project_id=project.unique_id,
            is_superuser=False,
        )
    )
    serializer = VehicleBreakdownSerializer(
        data={
            "trip_assignment_id": assignment.unique_id,
            "breakdown_reason": "OTHER",
            "breakdown_time": "09:30:00",
        },
        context={"request": request},
    )

    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data["breakdown_vehicle_id"] == "VEH-ASSIGNED"
