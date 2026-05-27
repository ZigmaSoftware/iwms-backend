"""API tests for Panchayat endpoint — CRUD operations."""
import pytest

BASE = "/api/v1/masters/panchayat/"


@pytest.mark.django_db
class TestPanchayatAPIList:
    def test_list_unauthenticated_returns_401(self, api_client):
        resp = api_client.get(BASE)
        assert resp.status_code in (401, 403)

    def test_list_authenticated_returns_200(self, auth_client):
        resp = auth_client.get(BASE)
        assert resp.status_code == 200


@pytest.mark.django_db
class TestPanchayatAPICreate:
    def test_create_returns_success(self, auth_client, company, project, state, city, district):
        resp = auth_client.post(
            BASE,
            {
                "company_id": company.unique_id,
                "project_id": project.unique_id,
                "state_id": state.unique_id,
                "city_id": city.unique_id,
                "district_id": district.unique_id,
                "panchayat_name": "Test Panchayat",
                "geofencing_type": "polygon",
            },
            format="json",
        )
        assert resp.status_code in (200, 201)


@pytest.mark.django_db
class TestPanchayatAPIRetrieve:
    def test_retrieve_returns_200(self, auth_client, company, project, state, city, district):
        from app.models.masters.panchayat import Panchayat
        p = Panchayat.objects.create(
            company_id=company, project_id=project,
            state_id=state, city_id=city, district_id=district,
            panchayat_name="Sample Panchayat",
            geofencing_type="circle",
        )
        resp = auth_client.get(f"{BASE}{p.unique_id}/")
        assert resp.status_code == 200


@pytest.mark.django_db
class TestPanchayatAPIUpdate:
    def test_patch_returns_success(self, auth_client, company, project, state, city, district):
        from app.models.masters.panchayat import Panchayat
        p = Panchayat.objects.create(
            company_id=company, project_id=project,
            state_id=state, city_id=city, district_id=district,
            panchayat_name="Old Name",
            geofencing_type="square",
        )
        resp = auth_client.patch(
            f"{BASE}{p.unique_id}/", {"panchayat_name": "New Name"}, format="json"
        )
        assert resp.status_code in (200, 204)


@pytest.mark.django_db
class TestPanchayatAPIDelete:
    def test_delete_returns_success(self, auth_client, company, project, state, city, district):
        from app.models.masters.panchayat import Panchayat
        p = Panchayat.objects.create(
            company_id=company, project_id=project,
            state_id=state, city_id=city, district_id=district,
            panchayat_name="Delete Me",
            geofencing_type="rectangle",
        )
        resp = auth_client.delete(f"{BASE}{p.unique_id}/")
        assert resp.status_code in (200, 204)
