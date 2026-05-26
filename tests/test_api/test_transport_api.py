"""API tests for Fuel and VehicleType endpoints."""
import pytest
from app.models.transport_masters.fuel import Fuel
from app.models.transport_masters.vehicleTypeCreation import VehicleTypeCreation


@pytest.mark.django_db
class TestFuelAPI:
    BASE = "/api/v1/transport-masters/fuels/"

    def test_list_unauthenticated(self, api_client):
        resp = api_client.get(self.BASE)
        assert resp.status_code in (401, 403)

    def test_list_authenticated(self, auth_client):
        Fuel.objects.create(fuel_type="Diesel")
        resp = auth_client.get(self.BASE)
        assert resp.status_code == 200

    def test_create(self, auth_client):
        resp = auth_client.post(self.BASE, {"fuel_type": "LPG"}, format="json")
        assert resp.status_code in (200, 201)

    def test_retrieve(self, auth_client):
        fuel = Fuel.objects.create(fuel_type="CNG")
        resp = auth_client.get(f"{self.BASE}{fuel.unique_id}/")
        assert resp.status_code == 200
        assert resp.json().get("fuel_type") == "CNG"

    def test_update(self, auth_client):
        fuel = Fuel.objects.create(fuel_type="Electric")
        resp = auth_client.patch(
            f"{self.BASE}{fuel.unique_id}/",
            {"fuel_type": "EV"},
            format="json",
        )
        assert resp.status_code in (200, 204)

    def test_delete(self, auth_client):
        fuel = Fuel.objects.create(fuel_type="Hydrogen")
        resp = auth_client.delete(f"{self.BASE}{fuel.unique_id}/")
        assert resp.status_code in (200, 204)


@pytest.mark.django_db
class TestVehicleTypeAPI:
    BASE = "/api/v1/transport-masters/vehicle-type/"

    def test_list_authenticated(self, auth_client, company, project):
        VehicleTypeCreation.objects.create(vehicleType="Compactor", company_id=company, project_id=project)
        resp = auth_client.get(self.BASE)
        assert resp.status_code == 200

    def test_create(self, auth_client, company, project):
        resp = auth_client.post(
            self.BASE,
            {"vehicleType": "Tipper", "company_id_input": company.unique_id, "project_id_input": project.unique_id},
            format="json",
        )
        assert resp.status_code in (200, 201)

    def test_retrieve(self, auth_client, company, project):
        vt = VehicleTypeCreation.objects.create(vehicleType="Loader", company_id=company, project_id=project)
        resp = auth_client.get(f"{self.BASE}{vt.unique_id}/")
        assert resp.status_code == 200
