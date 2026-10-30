from datetime import time
from types import SimpleNamespace

import pytest
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from app.models.core_modules.daily_operations.daily_trip_assignment import (
    DailyTripAssignment,
)
from app.models.core_modules.daily_operations.vehicle_breakdown import VehicleBreakdown
from app.models.masters.transport_masters.vehicleCreation import VehicleCreation
from app.models.superadmin.role_management.staffUserType import StaffUserType
from app.models.superadmin.staff_management.staffcreation import Staffcreation
from app.serializers.core_modules.daily_operations.vehicle_breakdown_serializer import (
    VehicleBreakdownVerifySerializer,
)
from app.viewsets.core_modules.daily_operations.vehicle_breakdown_viewset import (
    VehicleBreakdownViewSet,
)

pytestmark = pytest.mark.django_db


def _assignment(plan):
    return DailyTripAssignment.objects.create(
        company_id=plan.company_id,
        project_id=plan.project_id,
        trip_plan_id=plan.unique_id,
        staff_template_id=plan.staff_template_id,
        vehicle_id=plan.vehicle_id,
        panchayat_id=plan.panchayat_id,
        waste_type_ids=plan.waste_type_ids,
        trip_date=timezone.localdate(),
        scheduled_time=time(9, 0),
        status=DailyTripAssignment.STATUS_IN_PROGRESS,
        approval_status=DailyTripAssignment.APPROVAL_APPROVED,
    )


def test_available_driver_accepts_mobile_role_and_scopes_to_supervisor(
    company,
    project,
    user_type,
    supervisor,
    driver,
    operator,
    bin_plan,
):
    supervisor_role = StaffUserType.objects.create(
        name="Company Supervisor",
        usertype_id=user_type.unique_id,
        company_id=company.unique_id,
        project_id=project.unique_id,
    )
    driver_role = StaffUserType.objects.create(
        name="Company Driver",
        usertype_id=user_type.unique_id,
        company_id=company.unique_id,
        project_id=project.unique_id,
    )
    operator_role = StaffUserType.objects.create(
        name="Company Operator",
        usertype_id=user_type.unique_id,
        company_id=company.unique_id,
        project_id=project.unique_id,
    )
    supervisor.staffusertype_id = supervisor_role.unique_id
    supervisor.save(update_fields=["staffusertype_id"])
    driver.staffusertype_id = driver_role.unique_id
    driver.staff_head_id = supervisor.staff_unique_id
    driver.save(update_fields=["staffusertype_id", "staff_head_id"])
    operator.staffusertype_id = operator_role.unique_id
    operator.staff_head_id = supervisor.staff_unique_id
    operator.save(update_fields=["staffusertype_id", "staff_head_id"])

    outsider = Staffcreation.objects.create(
        employee_name="Other Supervisor Driver",
        company_id=company.unique_id,
        project_id=project.unique_id,
        staffusertype_id=driver_role.unique_id,
        active_status=True,
    )
    source = _assignment(bin_plan)
    breakdown = VehicleBreakdown.objects.create(
        company_id=company.unique_id,
        project_id=project.unique_id,
        trip_assignment_id=source.unique_id,
        breakdown_vehicle_id=source.vehicle_id,
    )

    request = APIRequestFactory().get(
        "/vehicle-breakdowns/available-staff/",
        {
            "date": timezone.localdate().isoformat(),
            "role": "govt_panchayat_driver",
            "breakdown_id": breakdown.unique_id,
        },
    )
    force_authenticate(request, user=supervisor)
    response = VehicleBreakdownViewSet.as_view({"get": "available_staff"})(request)

    assert response.status_code == 200
    assert [row["staff_unique_id"] for row in response.data] == [
        driver.staff_unique_id
    ]
    assert outsider.staff_unique_id not in {
        row["staff_unique_id"] for row in response.data
    }

    replacement_vehicle = VehicleCreation.objects.create(
        company_id=company.unique_id,
        project_id=project.unique_id,
        vehicle_no="TN01REPLACE",
    )
    serializer = VehicleBreakdownVerifySerializer(
        data={
            "replacement_vehicle_id": replacement_vehicle.unique_id,
            "replacement_driver_id": outsider.staff_unique_id,
            "replacement_operator_id": operator.staff_unique_id,
        },
        context={"instance": breakdown, "request": response.renderer_context["request"]},
    )
    assert not serializer.is_valid()
    assert "must report to the trip supervisor" in str(serializer.errors)


def test_breakdown_approval_carries_all_bins_and_closes_source_assignment(
    company,
    project,
    driver,
    operator,
    bin_plan,
    bin_stop,
):
    source = _assignment(bin_plan)
    breakdown = VehicleBreakdown.objects.create(
        company_id=company.unique_id,
        project_id=project.unique_id,
        trip_assignment_id=source.unique_id,
        breakdown_vehicle_id=source.vehicle_id,
    )
    replacement_vehicle = VehicleCreation.objects.create(
        company_id=company.unique_id,
        project_id=project.unique_id,
        vehicle_no="TN01BREAKDOWN",
    )
    serializer = VehicleBreakdownVerifySerializer(
        data={
            "replacement_vehicle_id": replacement_vehicle.unique_id,
            "replacement_driver_id": driver.staff_unique_id,
            "replacement_operator_id": operator.staff_unique_id,
        },
        context={
            "instance": breakdown,
            "request": SimpleNamespace(user=SimpleNamespace(staffusertype=None)),
            "account": None,
        },
    )

    assert serializer.is_valid(), serializer.errors
    approved = serializer.save()

    source.refresh_from_db()
    assert source.status == DailyTripAssignment.STATUS_COMPLETED
    assert approved.new_assignment is not None
    continuation = DailyTripAssignment.objects.get(unique_id=approved.new_assignment)
    assert continuation.status == DailyTripAssignment.STATUS_SCHEDULED
    assert continuation.trip_collection_points.count() == 1


def test_available_staff_templates_offers_the_broken_trips_own_crew(
    company, project, supervisor, bin_plan, staff_template,
):
    source = _assignment(bin_plan)
    later = _assignment(bin_plan)
    DailyTripAssignment.objects.filter(pk=later.pk).update(
        status=DailyTripAssignment.STATUS_SCHEDULED, scheduled_time=time(14, 0),
    )

    def template_ids(params):
        request = APIRequestFactory().get(
            "/vehicle-breakdowns/available-staff-templates/",
            {"date": timezone.localdate().isoformat(), **params},
        )
        force_authenticate(request, user=supervisor)
        response = VehicleBreakdownViewSet.as_view({"get": "available_staff_templates"})(request)
        assert response.status_code == 200, response.data
        return {row["unique_id"] for row in response.data}

    # Without the trip the crew looks busy (it is on that trip).
    assert staff_template.unique_id not in template_ids({})
    # For the trip that broke down, the same crew can carry on.
    assert staff_template.unique_id in template_ids({"trip_assignment_id": source.unique_id})


def test_verify_preview_with_a_replacement_vehicle_param(
    company, project, supervisor, bin_plan, staff_template,
):
    """`?replacement_vehicle_id=` must not be applied as a column filter on
    the breakdown (it has no replacement yet) — that 404'd the preview."""
    source = _assignment(bin_plan)
    breakdown = VehicleBreakdown.objects.create(
        company_id=company.unique_id,
        project_id=project.unique_id,
        trip_assignment_id=source.unique_id,
        breakdown_vehicle_id=source.vehicle_id,
    )
    spare = VehicleCreation.objects.create(
        company_id=company.unique_id, project_id=project.unique_id, vehicle_no="TN01SPARE",
    )
    request = APIRequestFactory().get(
        f"/vehicle-breakdowns/{breakdown.unique_id}/verify-preview/",
        {"replacement_vehicle_id": spare.unique_id},
    )
    force_authenticate(request, user=supervisor)
    response = VehicleBreakdownViewSet.as_view({"get": "verify_preview"})(
        request, unique_id=breakdown.unique_id,
    )

    assert response.status_code == 200, response.data
    assert response.data["replacement_vehicle_id"] == spare.unique_id
    assert response.data["original_crew"]["driver_id"] == staff_template.driver_id
