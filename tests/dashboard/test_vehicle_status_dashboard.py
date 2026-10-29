"""Vehicle Status Dashboard (dashboards/fleet-status)."""
from datetime import date, datetime, time
from decimal import Decimal
from types import SimpleNamespace

import pytest
from django.utils import timezone
from rest_framework.test import APIRequestFactory

from app.middleware import module_permission_middleware as mpm
from app.models.core_modules.daily_operations.bin_collection_event import BinCollectionEvent
from app.models.core_modules.daily_operations.daily_trip_assignment import DailyTripAssignment
from app.models.core_modules.daily_operations.daily_trip_collection_point import (
    DailyTripCollectionPoint,
)
from app.models.core_modules.daily_operations.daily_trip_household_collection import (
    DailyTripHouseholdCollection,
)
from app.models.core_modules.daily_operations.trip_delay_report import TripDelayReport
from app.models.core_modules.daily_operations.trip_retrip_request import TripRetripRequest
from app.models.core_modules.daily_operations.vehicle_breakdown import VehicleBreakdown
from app.models.core_modules.daily_operations.wastecollection import WasteCollection
from app.models.core_modules.schedule_setup.alternative_staff_template import (
    AlternativeStaffTemplate,
)
from app.models.core_modules.schedule_setup.staff_template import StaffTemplate
from app.models.masters.transport_masters.vehicleCreation import VehicleCreation
from app.models.superadmin.staff_management.staffcreation import StaffcreationOfficeDetails
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project
from app.models.waste_collection_bluetooth.waste_collection_bluetooth import WasteType
from app.utils.permission_catalog import ROUTE_OWNERS
from app.viewsets.dashboard.vehicle_status_dashboard_viewset import VehicleStatusDashboardViewSet

URL = "/api/v1/dashboards/fleet-status/"
DAY = date(2026, 10, 15)
EARLIER = date(2026, 10, 3)


def _aware(day, hh, mm=0):
    return timezone.make_aware(datetime.combine(day, time(hh, mm)))


@pytest.fixture
def fleet(db, company, project):
    scope = {"company_id": company.unique_id, "project_id": project.unique_id}
    driver = StaffcreationOfficeDetails.objects.create(employee_name="Ravi Driver", **scope)
    operator = StaffcreationOfficeDetails.objects.create(employee_name="Kumar Operator", **scope)
    substitute = StaffcreationOfficeDetails.objects.create(employee_name="Sub Driver", **scope)
    team = StaffTemplate.objects.create(
        driver_id=driver.staff_unique_id, operator_id=operator.staff_unique_id, **scope,
    )
    alt = AlternativeStaffTemplate.objects.create(
        staff_template_id=team.unique_id,
        driver_id=substitute.staff_unique_id,
        operator_id=operator.staff_unique_id,
        from_date=DAY, to_date=DAY,
        change_reason="Leave",
        approval_status="APPROVED",
        **scope,
    )
    wet = WasteType.objects.create(waste_type_name="Wet Waste", **scope)

    busy = VehicleCreation.objects.create(vehicle_no="TN01AB1234", **scope)
    broken = VehicleCreation.objects.create(vehicle_no="TN01AB9999", **scope)
    VehicleCreation.objects.create(vehicle_no="TN01ZZ0001", **scope)  # idle all day

    def trip(vehicle, day, status, **extra):
        return DailyTripAssignment.objects.create(
            vehicle_id=vehicle.unique_id,
            trip_date=day,
            scheduled_time=time(6, 0),
            status=status,
            staff_template_id=team.unique_id,
            **scope,
            **extra,
        )

    # Started 40 minutes late, on the alternative crew.
    on_trip = trip(
        busy, DAY, DailyTripAssignment.STATUS_IN_PROGRESS,
        alt_staff_template_id=alt.unique_id, actual_start_at=_aware(DAY, 6, 40),
    )
    earlier = trip(busy, EARLIER, DailyTripAssignment.STATUS_COMPLETED)
    stalled = trip(broken, DAY, DailyTripAssignment.STATUS_IN_PROGRESS)

    for status, carried in (
        (DailyTripCollectionPoint.STATUS_COLLECTED, None),
        (DailyTripCollectionPoint.STATUS_PENDING, None),
        (DailyTripCollectionPoint.STATUS_MISSED, None),
    ):
        DailyTripCollectionPoint.objects.create(
            trip_assignment_id=on_trip.unique_id, status=status, carried_to_assignment=carried, **scope,
        )
    DailyTripHouseholdCollection.objects.create(
        trip_assignment_id=on_trip.unique_id,
        collection_type=DailyTripHouseholdCollection.COLLECTION_TYPE_BULK,
        status=DailyTripHouseholdCollection.STATUS_PENDING,
        carried_to_assignment="TRIP-NEXT",
        **scope,
    )

    BinCollectionEvent.objects.create(
        trip_assignment_id=on_trip.unique_id, vehicle_id=busy.unique_id,
        waste_type_id=wet.unique_id, collected_weight_kg=Decimal("120"),
        status=BinCollectionEvent.STATUS_COLLECTED, collection_date=DAY,
        driver_latitude=Decimal("13.08"), driver_longitude=Decimal("80.27"),
        **scope,
    )
    # Not collected: no weight.
    BinCollectionEvent.objects.create(
        trip_assignment_id=on_trip.unique_id, vehicle_id=busy.unique_id,
        collected_weight_kg=Decimal("999"),
        status=BinCollectionEvent.STATUS_NOT_COLLECTED, collection_date=DAY, **scope,
    )
    WasteCollection.objects.create(
        trip_assignment_id=earlier.unique_id, dry_waste=30, wet_waste=50,
        collection_date=EARLIER, **scope,
    )

    VehicleBreakdown.objects.create(
        trip_assignment_id=stalled.unique_id, breakdown_vehicle_id=broken.unique_id,
        replacement_vehicle_id=busy.unique_id, new_assignment=on_trip.unique_id,
        breakdown_reason="FLAT_TYRE",
        status=VehicleBreakdown.STATUS_REPORTED, **scope,
    )
    TripDelayReport.objects.create(
        trip_assignment_id=on_trip.unique_id, delay_reason="TRAFFIC",
        delay_remarks="Jam", estimated_delay_minutes=25, **scope,
    )
    TripRetripRequest.objects.create(
        assignment_id=on_trip.unique_id, reason="Vehicle full", pending_bin_count=1, **scope,
    )
    return SimpleNamespace(
        busy=busy, broken=broken, on_trip=on_trip, team=team, alt=alt,
        driver=driver, substitute=substitute,
    )


def test_vehicle_status_dashboard_is_a_grantable_screen():
    assert ROUTE_OWNERS["dashboards/fleet-status"] == ("dashboard", "vehicle-status-dashboard")


@pytest.mark.django_db
def test_fleet_rows(auth_client, fleet, company):
    data = auth_client.get(URL, {"date": DAY.isoformat(), "company_id": company.unique_id}).json()
    rows = {r["vehicle_no"]: r for r in data["vehicles"]}
    assert list(rows) == ["TN01AB1234", "TN01AB9999", "TN01ZZ0001"]

    busy = rows["TN01AB1234"]
    assert busy["state"] == "on_trip"
    assert busy["current_trip"]["id"] == fleet.on_trip.unique_id
    assert busy["current_trip"]["start_delay_min"] == 40
    assert busy["current_trip"]["late"] is True
    # The trip runs on the alternative crew.
    assert busy["on_alternative_staff"] is True
    assert busy["driver"]["name"] == "Sub Driver"
    stops = busy["stops"]
    assert (stops["planned"], stops["collected"], stops["remaining"], stops["missed"], stops["carried"]) == (
        4, 1, 1, 1, 1,
    )
    assert busy["weight_today_kg"] == 120.0
    assert busy["weight_month_kg"] == 200.0  # + 80 kg household earlier this month
    assert (busy["delays"], busy["delay_minutes"], busy["retrips"], busy["pending_retrips"]) == (1, 25, 1, 1)

    assert rows["TN01AB9999"]["state"] == "breakdown"
    assert rows["TN01AB9999"]["open_breakdowns"] == 1
    assert rows["TN01ZZ0001"]["state"] == "idle"

    summary = data["summary"]
    assert summary["vehicles"] == 3
    assert summary["states"] == {"on_trip": 1, "breakdown": 1, "scheduled": 0, "completed": 0, "idle": 1}
    assert summary["weight_month_kg"] == 200.0


@pytest.mark.django_db
def test_vehicle_detail(auth_client, fleet):
    data = auth_client.get(f"{URL}{fleet.busy.unique_id}/", {"date": DAY.isoformat()}).json()
    assert data["vehicle"]["vehicle_no"] == "TN01AB1234"
    assert data["state"] == "on_trip"
    assert data["last_seen"]["source"] == "bin_scan"

    [trip] = data["trips"]
    assert trip["scheduled_time"] == "06:00"
    assert trip["start_delay_min"] == 40
    assert trip["staff"]["driver"]["name"] == "Ravi Driver"
    assert trip["alternative_staff"]["driver"]["name"] == "Sub Driver"
    assert trip["alternative_staff"]["reason"] == "Leave"

    assert [c["template_id"] for c in data["staff"]["assigned"]] == [fleet.team.unique_id]
    assert [a["template_id"] for a in data["staff"]["alternatives"]] == [fleet.alt.unique_id]

    by_type = data["stops"]["by_collection_type"]
    assert (by_type["bin_collection"]["collected"], by_type["bin_collection"]["remaining"]) == (1, 1)
    assert by_type["bulk_waste_collection"]["carried"] == 1
    assert {w["name"] for w in data["stops"]["by_waste_type"]} == {"Unclassified"}

    today, month = data["weight"]["today"], data["weight"]["month"]
    assert today["total_kg"] == 120.0
    assert today["by_collection_type"]["bin_collection"] == 120.0
    assert month["total_kg"] == 200.0
    assert month["by_collection_type"]["household_collection"] == 80.0
    assert {w["name"]: w["kg"] for w in month["by_waste_type"]} == {
        "Wet Waste": 170.0, "Dry Waste": 30.0,
    }
    assert sum(d["kg"] for d in data["weight"]["daily"]) == 200.0
    assert len(data["weight"]["daily"]) == 15

    # The breakdown of the other vehicle shows here as a replacement.
    [breakdown] = data["breakdowns"]
    assert breakdown["role"] == "replacement"
    assert breakdown["broken_vehicle_no"] == "TN01AB9999"
    assert [d["reason"] for d in data["delays"]] == ["TRAFFIC"]
    assert [r["status"] for r in data["retrips"]] == ["Pending"]


@pytest.mark.django_db
def test_vehicle_outside_scope_is_not_found(auth_client, fleet):
    other = Company.objects.create(name="Other Company")
    Project.objects.create(name="Other Project", company_id=other.unique_id)
    response = auth_client.get(
        f"{URL}{fleet.busy.unique_id}/", {"date": DAY.isoformat(), "company_id": other.unique_id},
    )
    assert response.status_code == 404
    assert auth_client.get(URL, {"company_id": other.unique_id}).json()["vehicles"] == []


def test_vehicle_status_needs_its_view_grant(monkeypatch):
    request = APIRequestFactory().get(URL)

    def check(permissions):
        def _auth(req):
            req.user = SimpleNamespace(is_authenticated=True, is_superuser=False, company_id="CMP-1")

        monkeypatch.setattr(mpm, "_authenticate_request", _auth)
        monkeypatch.setattr(mpm, "_resolve_permissions_for_request", lambda req: permissions)
        view = SimpleNamespace(cls=VehicleStatusDashboardViewSet, actions={"get": "list"})
        return mpm.ModulePermissionMiddleware(lambda r: None).process_view(request, view, (), {})

    assert check({"dashboard": {"vehicle-status-dashboard": ["view"]}}) is None
    assert check({"dashboard": {"admin-dashboard": ["view"]}}).status_code == 403
    assert check({}).status_code == 403


# ------------------------------------------------------------ supervisors

def _supervisor(company, project, name):
    from app.models.superadmin.role_management.staffUserType import StaffUserType

    role = StaffUserType.objects.create(
        name="Company Supervisor", company_id=company.unique_id, project_id=project.unique_id,
    )
    return StaffcreationOfficeDetails.objects.create(
        employee_name=name, staffusertype_id=role.unique_id,
        company_id=company.unique_id, project_id=project.unique_id,
    )


def _as(user, path, params):
    from rest_framework.test import force_authenticate

    request = APIRequestFactory().get(path, params)
    force_authenticate(request, user=user)
    if path == URL:
        return VehicleStatusDashboardViewSet.as_view({"get": "list"})(request)
    pk = path.rstrip("/").rsplit("/", 1)[-1]
    return VehicleStatusDashboardViewSet.as_view({"get": "retrieve"})(request, pk=pk)


@pytest.fixture
def supervisors(fleet, company, project):
    from app.models.core_modules.schedule_setup.trip_plan import TripPlan

    # Vehicle master names the first; a trip plan the second.
    by_vehicle = _supervisor(company, project, "Vehicle Supervisor")
    fleet.busy.supervisor_id = by_vehicle.staff_unique_id
    fleet.busy.save(update_fields=["supervisor_id"])
    by_plan = _supervisor(company, project, "Plan Supervisor")
    TripPlan.objects.create(
        company_id=company.unique_id, project_id=project.unique_id,
        vehicle_id=fleet.broken.unique_id, supervisor_id=by_plan.staff_unique_id,
        trip_trigger_weight_kg=500, max_vehicle_capacity_kg=1000, scheduled_time=time(6, 0),
    )
    return SimpleNamespace(by_vehicle=by_vehicle, by_plan=by_plan)


@pytest.mark.django_db
def test_supervisor_sees_only_their_vehicles(fleet, supervisors):
    params = {"date": DAY.isoformat()}
    data = _as(supervisors.by_vehicle, URL, params).data
    assert data["viewer"] == {"supervisor_only": True}
    assert [r["vehicle_no"] for r in data["vehicles"]] == ["TN01AB1234"]
    assert data["vehicles"][0]["supervisor"]["name"] == "Vehicle Supervisor"
    assert data["summary"]["vehicles"] == 1

    data = _as(supervisors.by_plan, URL, params).data
    assert [r["vehicle_no"] for r in data["vehicles"]] == ["TN01AB9999"]


@pytest.mark.django_db
def test_supervisor_cannot_open_another_vehicle(fleet, supervisors):
    params = {"date": DAY.isoformat()}
    own = _as(supervisors.by_vehicle, f"{URL}{fleet.busy.unique_id}/", params)
    assert own.status_code == 200
    assert own.data["vehicle"]["supervisor"]["name"] == "Vehicle Supervisor"
    assert _as(supervisors.by_vehicle, f"{URL}{fleet.broken.unique_id}/", params).status_code == 404


@pytest.mark.django_db
def test_admin_sees_every_vehicle_with_its_supervisor(auth_client, fleet, supervisors, company):
    data = auth_client.get(URL, {"date": DAY.isoformat(), "company_id": company.unique_id}).json()
    assert data["viewer"] == {"supervisor_only": False}
    rows = {r["vehicle_no"]: r for r in data["vehicles"]}
    assert len(rows) == 3
    assert rows["TN01AB1234"]["supervisor"]["name"] == "Vehicle Supervisor"
    assert rows["TN01ZZ0001"]["supervisor"] is None
