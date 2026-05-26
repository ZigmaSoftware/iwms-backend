"""API integration tests for Continent and Country endpoints."""
import pytest
from django.urls import reverse


@pytest.mark.django_db
class TestContinentAPI:
    BASE = "/api/v1/common-masters/continents/"

    def test_list_unauthenticated_returns_401(self, api_client):
        resp = api_client.get(self.BASE)
        assert resp.status_code in (401, 403)

    def test_list_authenticated(self, auth_client, continent):
        resp = auth_client.get(self.BASE)
        assert resp.status_code == 200

    def test_list_returns_created_continent(self, auth_client, continent):
        resp = auth_client.get(self.BASE)
        data = resp.json()
        items = data if isinstance(data, list) else data.get("results", data.get("data", []))
        names = [i.get("name") for i in items]
        assert continent.name in names

    def test_create(self, auth_client):
        resp = auth_client.post(self.BASE, {"name": "NewCont"}, format="json")
        assert resp.status_code in (200, 201)

    def test_retrieve(self, auth_client, continent):
        resp = auth_client.get(f"{self.BASE}{continent.unique_id}/")
        assert resp.status_code == 200
        assert resp.json().get("name") == continent.name

    def test_update(self, auth_client, continent):
        resp = auth_client.patch(
            f"{self.BASE}{continent.unique_id}/",
            {"name": "Updated Continent"},
            format="json",
        )
        assert resp.status_code in (200, 204)

    def test_delete(self, auth_client, continent):
        resp = auth_client.delete(f"{self.BASE}{continent.unique_id}/")
        assert resp.status_code in (200, 204)


@pytest.mark.django_db
class TestCountryAPI:
    BASE = "/api/v1/common-masters/countries/"

    def test_list_unauthenticated_returns_401(self, api_client):
        resp = api_client.get(self.BASE)
        assert resp.status_code in (401, 403)

    def test_list_authenticated(self, auth_client, country):
        resp = auth_client.get(self.BASE)
        assert resp.status_code == 200

    def test_create(self, auth_client, continent):
        resp = auth_client.post(
            self.BASE,
            {"name": "Brazil", "continent_id": continent.unique_id},
            format="json",
        )
        assert resp.status_code in (200, 201)

    def test_retrieve(self, auth_client, country):
        resp = auth_client.get(f"{self.BASE}{country.unique_id}/")
        assert resp.status_code == 200
        assert resp.json().get("name") == country.name

    def test_update(self, auth_client, country):
        resp = auth_client.patch(
            f"{self.BASE}{country.unique_id}/",
            {"name": "Updated Country"},
            format="json",
        )
        assert resp.status_code in (200, 204)

    def test_delete(self, auth_client, country):
        resp = auth_client.delete(f"{self.BASE}{country.unique_id}/")
        assert resp.status_code in (200, 204)
