import pytest

from app.management.commands.seeders.superadmin_masters.blue_planet import (
    BluePlanetSeeder,
)
from app.management.commands.seeders.superadmin_masters.project import ProjectSeeder
from app.management.commands.seeders.superadmin.staff_management.staff_office import (
    backfill_missing_staff_ids,
)
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project
from app.models.user_creations.staffcreation import Staffcreation


@pytest.mark.django_db
class TestBluePlanetSeeder:
    def test_creates_company_and_two_projects_with_noida_api_configuration(self):
        BluePlanetSeeder().run()

        company = Company.objects.get(name="Blue Planet")
        projects = Project.objects.filter(company_id=company).order_by("name")

        assert list(projects.values_list("name", flat=True)) == [
            "Noida BP",
            "Palakkad BP",
        ]

        noida = projects.get(name="Noida BP")
        assert noida.attendance_api_url == BluePlanetSeeder.ATTENDANCE_API_URL
        assert noida.attendance_api_key == BluePlanetSeeder.ATTENDANCE_API_KEY
        assert noida.gps_api_url == BluePlanetSeeder.GPS_API_URL
        assert noida.weighment_api_url == BluePlanetSeeder.WEIGHMENT_API_URL

        for project in projects:
            assert all(
                unique_id.startswith("STC-")
                for unique_id in Staffcreation.objects.filter(project_id=project)
                .values_list("staff_unique_id", flat=True)
            )
            assert list(
                Staffcreation.objects.filter(project_id=project)
                .order_by("staff_id")
                .values_list("staff_id", flat=True)
            ) == ["STF0001", "STF0002", "STF0003"]

    def test_is_idempotent_and_generic_project_seeder_does_not_add_third_project(self):
        BluePlanetSeeder().run()
        BluePlanetSeeder().run()
        ProjectSeeder().run()

        company = Company.objects.get(name="Blue Planet")
        assert Project.objects.filter(company_id=company).count() == 2
        for project in Project.objects.filter(company_id=company):
            assert Staffcreation.objects.filter(project_id=project).count() == 3
            assert list(
                Staffcreation.objects.filter(project_id=project)
                .order_by("staff_id")
                .values_list("staff_id", flat=True)
            ) == ["STF0001", "STF0002", "STF0003"]

    def test_backfills_missing_staff_ids_across_all_projects(self):
        BluePlanetSeeder().run()
        staff = Staffcreation.objects.order_by("project_id_id", "staff_id").first()
        Staffcreation.objects.filter(pk=staff.pk).update(staff_id="")

        assert backfill_missing_staff_ids() == 1

        staff.refresh_from_db()
        assert staff.staff_id.startswith("STF")
        assert staff.staff_id != ""
