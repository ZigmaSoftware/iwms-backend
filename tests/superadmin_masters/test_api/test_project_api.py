"""API tests for Project endpoint — CRUD operations."""
import pytest
from app.models.staff_creations.staffcreation import Staffcreation
from app.models.superadmin_masters.project import Project

BASE = "/api/v1/superadmin/project/"


@pytest.mark.django_db
class TestProjectAPIList:
    def test_list_authenticated_returns_company_name(self, auth_client, project, company):
        resp = auth_client.get(BASE)
        assert resp.status_code == 200
        results = resp.json().get("results", resp.json())
        row = next(item for item in results if item["unique_id"] == project.unique_id)
        assert row["company_unique_id"] == company.unique_id
        assert row["company_name"] == company.name


@pytest.mark.django_db
class TestProjectAPICreate:
    def test_create_returns_success(self, auth_client, company, superuser):
        resp = auth_client.post(
            BASE,
            {
                "name": "New Project",
                "company_unique_id": company.unique_id,
                "admin_username": "proj_admin",
                "admin_password": "securepass123",
                "admin_employee_name": "Project Admin",
            },
            format="json",
        )
        assert resp.status_code in (200, 201)
        project_data = resp.json().get("project", resp.json())
        assert project_data["created_by"] == superuser.unique_id
        assert project_data["updated_by"] == superuser.unique_id
        project = Project.objects.get(name="New Project")
        staff = Staffcreation.objects.get(username="proj_admin")
        assert project.company_id == company.unique_id
        assert project.created_by_id == superuser.unique_id
        assert project.updated_by_id == superuser.unique_id
        assert staff.company_id == company.unique_id
        assert staff.project_id == project.unique_id

    def test_create_stores_but_does_not_return_attendance_api_key(self, auth_client, company):
        resp = auth_client.post(
            BASE,
            {
                "name": "Attendance Project",
                "company_unique_id": company.unique_id,
                "attendance_api_url": "http://zigfly.in/attendance-api/api/sync/recognized",
                "attendance_api_key": "ZIGFLY_SYNC_2025",
                "admin_username": "attendance_admin",
                "admin_password": "securepass123",
                "admin_employee_name": "Attendance Admin",
            },
            format="json",
        )
        assert resp.status_code in (200, 201)
        assert "attendance_api_key" not in resp.json().get("project", resp.json())
        assert Project.objects.get(name="Attendance Project").attendance_api_key == "ZIGFLY_SYNC_2025"

    def test_create_redacts_attendance_api_key_from_audit(self, auth_client, company):
        from app.utils.common_audit import CommonAudit

        auth_client.post(
            BASE,
            {
                "name": "Audited Attendance Project",
                "company_unique_id": company.unique_id,
                "attendance_api_url": "http://zigfly.in/attendance-api/api/sync/recognized",
                "attendance_api_key": "ZIGFLY_SYNC_2025",
                "admin_username": "audited_admin",
                "admin_password": "securepass123",
                "admin_employee_name": "Audited Admin",
            },
            format="json",
        )

        audit = CommonAudit.objects.filter(endpoint_name="projects").latest("createdAt")
        assert audit.new_data["attendance_api_key"] == "[REDACTED]"


@pytest.mark.django_db
class TestProjectAPIRetrieve:
    def test_retrieve_returns_200(self, auth_client, project):
        resp = auth_client.get(f"{BASE}{project.unique_id}/")
        assert resp.status_code == 200


@pytest.mark.django_db
class TestProjectAPIUpdate:
    def test_patch_returns_success(self, auth_client, project, superuser):
        resp = auth_client.patch(
            f"{BASE}{project.unique_id}/", {"name": "Updated Project"}, format="json"
        )
        assert resp.status_code in (200, 204)
        project.refresh_from_db()
        assert project.updated_by_id == superuser.unique_id


@pytest.mark.django_db
class TestProjectAPIDelete:
    def test_delete_returns_success(self, auth_client, project):
        resp = auth_client.delete(f"{BASE}{project.unique_id}/")
        assert resp.status_code in (200, 204)
