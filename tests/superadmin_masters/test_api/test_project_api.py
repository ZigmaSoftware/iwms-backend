"""API tests for Project endpoint — CRUD operations."""
import pytest

BASE = "/api/v1/superadmin/project/"


@pytest.mark.django_db
class TestProjectAPIList:
    def test_list_authenticated_returns_200(self, auth_client, project):
        resp = auth_client.get(BASE)
        assert resp.status_code == 200


@pytest.mark.django_db
class TestProjectAPICreate:
    def test_create_returns_success(self, auth_client, company):
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


@pytest.mark.django_db
class TestProjectAPIRetrieve:
    def test_retrieve_returns_200(self, auth_client, project):
        resp = auth_client.get(f"{BASE}{project.unique_id}/")
        assert resp.status_code == 200


@pytest.mark.django_db
class TestProjectAPIUpdate:
    def test_patch_returns_success(self, auth_client, project):
        resp = auth_client.patch(
            f"{BASE}{project.unique_id}/", {"name": "Updated Project"}, format="json"
        )
        assert resp.status_code in (200, 204)


@pytest.mark.django_db
class TestProjectAPIDelete:
    def test_delete_returns_success(self, auth_client, project):
        resp = auth_client.delete(f"{BASE}{project.unique_id}/")
        assert resp.status_code in (200, 204)
