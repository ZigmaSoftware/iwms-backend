"""API tests for Staff endpoints — CRUD operations."""
import pytest

STAFF_BASE = "/api/v1/user-creations/staffcreation/"


@pytest.mark.django_db
class TestStaffAPIList:
    def test_list_unauthenticated_returns_401(self, api_client):
        resp = api_client.get(STAFF_BASE)
        assert resp.status_code in (401, 403)

    def test_list_authenticated_returns_200(self, auth_client):
        resp = auth_client.get(STAFF_BASE)
        assert resp.status_code == 200


@pytest.mark.django_db
class TestStaffAPICreate:
    def test_create_returns_success(self, auth_client, company, project):
        resp = auth_client.post(
            STAFF_BASE,
            {"employee_name": "New Staff", "company_id": company.unique_id, "project_id": project.unique_id},
            format="json",
        )
        assert resp.status_code in (200, 201)


@pytest.mark.django_db
class TestStaffAPIRetrieve:
    def test_retrieve_nonexistent_returns_404(self, auth_client):
        resp = auth_client.get(f"{STAFF_BASE}STC-NOTEXIST/")
        assert resp.status_code in (404, 400)
