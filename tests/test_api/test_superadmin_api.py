"""API tests for Company and Project (superadmin) endpoints."""
import pytest
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project


@pytest.mark.django_db
class TestCompanyAPI:
    BASE = "/api/v1/superadmin/company/"

    def test_list_unauthenticated(self, api_client):
        resp = api_client.get(self.BASE)
        assert resp.status_code in (401, 403)

    def test_list_authenticated(self, auth_client, company):
        resp = auth_client.get(self.BASE)
        assert resp.status_code == 200

    def test_create(self, auth_client):
        resp = auth_client.post(
            self.BASE, {"name": "New Company"}, format="json"
        )
        assert resp.status_code in (200, 201)

    def test_retrieve(self, auth_client, company):
        resp = auth_client.get(f"{self.BASE}{company.unique_id}/")
        assert resp.status_code == 200
        assert resp.json().get("name") == company.name

    def test_update(self, auth_client, company):
        resp = auth_client.patch(
            f"{self.BASE}{company.unique_id}/",
            {"name": "Renamed Company"},
            format="json",
        )
        assert resp.status_code in (200, 204)

    def test_delete(self, auth_client, company):
        resp = auth_client.delete(f"{self.BASE}{company.unique_id}/")
        assert resp.status_code in (200, 204)


@pytest.mark.django_db
class TestProjectAPI:
    BASE = "/api/v1/superadmin/project/"

    def test_list_authenticated(self, auth_client, project):
        resp = auth_client.get(self.BASE)
        assert resp.status_code == 200

    def test_create(self, auth_client, company, project):
        # company already has one project, so no admin credentials required
        resp = auth_client.post(
            self.BASE,
            {"name": "New Project", "company_unique_id": company.unique_id},
            format="json",
        )
        assert resp.status_code in (200, 201)

    def test_retrieve(self, auth_client, project):
        resp = auth_client.get(f"{self.BASE}{project.unique_id}/")
        assert resp.status_code == 200

    def test_update(self, auth_client, project):
        resp = auth_client.patch(
            f"{self.BASE}{project.unique_id}/",
            {"name": "Updated Project"},
            format="json",
        )
        assert resp.status_code in (200, 204)

    def test_delete(self, auth_client, project):
        resp = auth_client.delete(f"{self.BASE}{project.unique_id}/")
        assert resp.status_code in (200, 204)
