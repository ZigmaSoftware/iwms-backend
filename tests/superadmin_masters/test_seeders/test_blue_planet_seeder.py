import pytest

from app.management.commands.seeders.superadmin_masters.blue_planet import (
    BluePlanetSeeder,
)
from app.management.commands.seeders.superadmin.staff_management.staff_office import (
    backfill_missing_staff_ids,
)
from app.models.assets.bins import Bins
from app.models.customers.customercreation import CustomerCreation
from app.models.grivences.complaints import Complaint
from app.models.masters.ward import Ward
from app.models.masters.zone import Zone
from app.models.schedule_masters.collection_point import Collection_point
from app.models.schedule_masters.trip_plan import TripPlan
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project
from app.models.transport_masters.vehicleCreation import VehicleCreation
from app.models.staff_creations.staffcreation import Staffcreation


@pytest.mark.django_db
class TestBluePlanetSeeder:
    def test_creates_company_and_two_projects_with_noida_api_configuration(self):
        BluePlanetSeeder().run()

        company = Company.objects.get(name="Blue Planet")
        assert Company.objects.count() == 1

        projects = Project.objects.filter(company_id=company).order_by("name")

        assert list(projects.values_list("name", flat=True)) == [
            "Blue Planet Integrated Waste Management",
            "Palakkad BP",
        ]

        noida = projects.get(name="Blue Planet Integrated Waste Management")
        assert noida.attendance_api_url == BluePlanetSeeder.ATTENDANCE_API_URL
        assert noida.attendance_api_key == BluePlanetSeeder.ATTENDANCE_API_KEY
        assert noida.gps_api_url == BluePlanetSeeder.GPS_API_URL
        assert noida.gps_vehicle_tracking_api == BluePlanetSeeder.GPS_VEHICLE_TRACKING_API
        assert noida.weighment_api_url == BluePlanetSeeder.WEIGHMENT_API_URL

        # Blue Planet Integrated Waste Management uses the real Vamosys-tracked fleet instead of
        # the generic 2-vehicle demo pattern used elsewhere.
        assert VehicleCreation.objects.filter(
            company_id=company, project_id=noida, is_active=True
        ).count() == len(BluePlanetSeeder.GNO_REAL_VEHICLES)
        assert set(
            VehicleCreation.objects.filter(company_id=company, project_id=noida, is_active=True)
            .values_list("vehicle_no", flat=True)
        ) == {v["vehicle_no"] for v in BluePlanetSeeder.GNO_REAL_VEHICLES}

        for project in projects:
            assert Zone.objects.filter(company_id=company, project_id=project).count() == 3
            assert Ward.objects.filter(company_id=company, project_id=project).count() == 3
            assert Collection_point.objects.filter(company_id=company, project_id=project).count() == 3
            assert Bins.objects.filter(company_id=company, project_id=project).count() == 9
            if project.name != "Blue Planet Integrated Waste Management":
                assert VehicleCreation.objects.filter(company_id=company, project_id=project).count() == 2
            # Blue Planet Integrated Waste Management additionally carries 5 real-address customers
            # for the dedicated UP16KT1737 route (GNO_REAL_ROUTE_STOPS).
            expected_customers = 8 + (
                len(BluePlanetSeeder.GNO_REAL_ROUTE_STOPS) if project.name == "Blue Planet Integrated Waste Management" else 0
            )
            assert CustomerCreation.objects.filter(company_id=company, project_id=project).count() == expected_customers
            assert Complaint.objects.filter(company_id=company, project_id=project).count() == 3

            bin_trip_plan = TripPlan.objects.get(
                company_id=company, project_id=project, collection_type=TripPlan.COLLECTION_TYPE_BIN
            )
            assert bin_trip_plan.is_auto_assign is True

            household_trip_plans = TripPlan.objects.filter(
                company_id=company, project_id=project, collection_type=TripPlan.COLLECTION_TYPE_HOUSEHOLD
            )
            assert household_trip_plans.count() == (2 if project.name == "Blue Planet Integrated Waste Management" else 1)
            assert all(plan.is_auto_assign for plan in household_trip_plans)

            if project.name == "Blue Planet Integrated Waste Management":
                real_route_plan = household_trip_plans.get(
                    vehicle_id__vehicle_no=BluePlanetSeeder.GNO_REAL_ROUTE_VEHICLE_NO
                )
                assert real_route_plan.plan_collection_points.filter(is_active=True).count() == len(
                    BluePlanetSeeder.GNO_REAL_ROUTE_STOPS
                )

            for bin_obj in Bins.objects.filter(company_id=company, project_id=project):
                assert bin_obj.ward_id_id is not None
                assert bin_obj.zone_id_id is not None

    def test_is_idempotent(self):
        BluePlanetSeeder().run()
        BluePlanetSeeder().run()

        company = Company.objects.get(name="Blue Planet")
        assert Project.objects.filter(company_id=company).count() == 2
        for project in Project.objects.filter(company_id=company):
            assert Zone.objects.filter(company_id=company, project_id=project).count() == 3
            expected_customers = 8 + (
                len(BluePlanetSeeder.GNO_REAL_ROUTE_STOPS) if project.name == "Blue Planet Integrated Waste Management" else 0
            )
            assert CustomerCreation.objects.filter(company_id=company, project_id=project).count() == expected_customers
            assert Complaint.objects.filter(company_id=company, project_id=project).count() == 3

    def test_backfills_missing_staff_ids_across_all_projects(self):
        BluePlanetSeeder().run()
        staff = Staffcreation.objects.order_by("project_id_id", "staff_id").first()
        Staffcreation.objects.filter(pk=staff.pk).update(staff_id="")

        assert backfill_missing_staff_ids() == 1

        staff.refresh_from_db()
        assert staff.staff_id.startswith("STF")
        assert staff.staff_id != ""
