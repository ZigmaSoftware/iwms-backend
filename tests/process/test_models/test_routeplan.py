"""Unit tests for RoutePlan model — CRUD + constraints."""
import pytest
from app.models.process.routeplan import RoutePlan
from app.models.transport_masters.vehicleCreation import VehicleCreation
from app.models.user_creations.staffcreation import StaffcreationOfficeDetails


@pytest.fixture
def vehicle(db, company, project):
    return VehicleCreation.objects.create(
        vehicle_no="TN01AB1234",
        vehicle_condition="NEW",
        company_id=company,
        project_id=project,
    )


@pytest.fixture
def supervisor(db, company, project):
    return StaffcreationOfficeDetails.objects.create(
        employee_name="Supervisor One",
        company_id=company,
        project_id=project,
    )


@pytest.fixture
def route_plan(db, company, project, district, city, zone, vehicle, supervisor):
    return RoutePlan.objects.create(
        district_id=district,
        city_id=city,
        zone_id=zone,
        vehicle_id=vehicle,
        supervisor_id=supervisor,
        company_id=company,
        project_id=project,
    )


@pytest.mark.django_db
class TestRoutePlanCreate:
    def test_unique_id_prefix(self, route_plan):
        assert route_plan.unique_id.startswith("RTP-")

    def test_display_code_auto_generated(self, route_plan):
        assert route_plan.display_code is not None
        assert len(route_plan.display_code) > 0

    def test_foreign_key_zone(self, route_plan, zone):
        assert route_plan.zone_id == zone

    def test_foreign_key_vehicle(self, route_plan, vehicle):
        assert route_plan.vehicle_id == vehicle

    def test_foreign_key_supervisor(self, route_plan, supervisor):
        assert route_plan.supervisor_id == supervisor


@pytest.mark.django_db
class TestRoutePlanDefaults:
    def test_is_active_default_true(self, route_plan):
        assert route_plan.is_active is True

    def test_is_deleted_default_false(self, route_plan):
        assert route_plan.is_deleted is False


@pytest.mark.django_db
class TestRoutePlanSoftDelete:
    def test_soft_delete(self, route_plan):
        route_plan.delete()
        route_plan.refresh_from_db()
        assert route_plan.is_deleted is True


@pytest.mark.django_db
class TestRoutePlanUniqueIds:
    def test_two_plans_have_different_ids(self, company, project, district, city, zone, vehicle, supervisor):
        rp1 = RoutePlan.objects.create(
            district_id=district, city_id=city, zone_id=zone,
            vehicle_id=vehicle, supervisor_id=supervisor,
            company_id=company, project_id=project,
        )
        rp2 = RoutePlan.objects.create(
            district_id=district, city_id=city, zone_id=zone,
            vehicle_id=vehicle, supervisor_id=supervisor,
            company_id=company, project_id=project,
        )
        assert rp1.unique_id != rp2.unique_id
