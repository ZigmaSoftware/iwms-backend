"""API tests for District, City, Zone, Ward masters endpoints."""
import pytest


@pytest.mark.django_db
class TestDistrictAPI:
    BASE = "/api/v1/masters/districts/"

    def test_list_unauthenticated(self, api_client):
        resp = api_client.get(self.BASE)
        assert resp.status_code in (401, 403)

    def test_list_authenticated(self, auth_client, district):
        resp = auth_client.get(self.BASE)
        assert resp.status_code == 200

    def test_retrieve(self, auth_client, district):
        resp = auth_client.get(f"{self.BASE}{district.unique_id}/")
        assert resp.status_code == 200

    def test_create(self, auth_client, continent, country, state):
        resp = auth_client.post(
            self.BASE,
            {
                "name": "Madurai",
                "continent_id": continent.unique_id,
                "country_id": country.unique_id,
                "state_id": state.unique_id,
            },
            format="json",
        )
        assert resp.status_code in (200, 201)

    def test_update(self, auth_client, district):
        resp = auth_client.patch(
            f"{self.BASE}{district.unique_id}/",
            {"name": "Updated District"},
            format="json",
        )
        assert resp.status_code in (200, 204)

    def test_delete(self, auth_client, district):
        resp = auth_client.delete(f"{self.BASE}{district.unique_id}/")
        assert resp.status_code in (200, 204)


@pytest.mark.django_db
class TestCityAPI:
    BASE = "/api/v1/masters/cities/"

    def test_list_authenticated(self, auth_client, city):
        resp = auth_client.get(self.BASE)
        assert resp.status_code == 200

    def test_retrieve(self, auth_client, city):
        resp = auth_client.get(f"{self.BASE}{city.unique_id}/")
        assert resp.status_code == 200

    def test_create(self, auth_client, company, project, continent, country, state, district):
        resp = auth_client.post(
            self.BASE,
            {
                "name": "Madurai City",
                "continent_id": continent.unique_id,
                "country_id": country.unique_id,
                "state_id": state.unique_id,
                "district_id": district.unique_id,
                "company_id": company.unique_id,
                "project_id": project.unique_id,
            },
            format="json",
        )
        assert resp.status_code in (200, 201)


@pytest.mark.django_db
class TestZoneAPI:
    BASE = "/api/v1/masters/zones/"

    def test_list_authenticated(self, auth_client, zone):
        resp = auth_client.get(self.BASE)
        assert resp.status_code == 200

    def test_retrieve(self, auth_client, zone):
        resp = auth_client.get(f"{self.BASE}{zone.unique_id}/")
        assert resp.status_code == 200

    def test_create(self, auth_client, state, district, city):
        resp = auth_client.post(
            self.BASE,
            {
                "zone_name": "New Zone",
                "state_id": state.unique_id,
                "district_id": district.unique_id,
                "city_id": city.unique_id,
            },
            format="json",
        )
        assert resp.status_code in (200, 201)


@pytest.mark.django_db
class TestWardAPI:
    BASE = "/api/v1/masters/wards/"

    def test_list_authenticated(self, auth_client, ward):
        resp = auth_client.get(self.BASE)
        assert resp.status_code == 200

    def test_retrieve(self, auth_client, ward):
        resp = auth_client.get(f"{self.BASE}{ward.unique_id}/")
        assert resp.status_code == 200
