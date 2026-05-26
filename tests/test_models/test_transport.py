"""Unit tests for Fuel, VehicleTypeCreation, VehicleCreation models."""
import pytest
from app.models.transport_masters.fuel import Fuel
from app.models.transport_masters.vehicleTypeCreation import VehicleTypeCreation
from app.models.transport_masters.vehicleCreation import VehicleCreation


@pytest.mark.django_db
class TestFuelModel:
    def test_create(self):
        f = Fuel.objects.create(fuel_type="Diesel")
        assert f.fuel_type == "Diesel"
        assert f.unique_id.startswith("FUEL-")

    def test_str(self):
        f = Fuel.objects.create(fuel_type="Petrol")
        assert str(f) == "Petrol"

    def test_default_flags(self):
        f = Fuel.objects.create(fuel_type="CNG")
        assert f.is_active is True
        assert f.is_deleted is False

    def test_soft_delete(self):
        f = Fuel.objects.create(fuel_type="Electric")
        f.delete()
        f.refresh_from_db()
        assert f.is_deleted is True
        assert f.is_active is False

    def test_description_optional(self):
        f = Fuel.objects.create(fuel_type="Hydrogen")
        assert f.description is None

    def test_ordering_by_fuel_type(self):
        Fuel.objects.create(fuel_type="Zebra Gas")
        Fuel.objects.create(fuel_type="Alpha Gas")
        names = list(Fuel.objects.values_list("fuel_type", flat=True))
        assert names == sorted(names)


@pytest.mark.django_db
class TestVehicleTypeCreationModel:
    def test_create(self, company, project):
        vt = VehicleTypeCreation.objects.create(
            vehicleType="Compactor",
            company_id=company,
            project_id=project,
        )
        assert vt.vehicleType == "Compactor"
        assert vt.unique_id.startswith("VHTYPE-")

    def test_str(self, company, project):
        vt = VehicleTypeCreation.objects.create(
            vehicleType="Tipper",
            company_id=company,
            project_id=project,
        )
        assert "Tipper" in str(vt)

    def test_default_flags(self, company, project):
        vt = VehicleTypeCreation.objects.create(
            vehicleType="Dumper",
            company_id=company,
            project_id=project,
        )
        assert vt.is_active is True
        assert vt.is_deleted is False

    def test_soft_delete(self, company, project):
        vt = VehicleTypeCreation.objects.create(
            vehicleType="Loader",
            company_id=company,
            project_id=project,
        )
        vt.delete()
        vt.refresh_from_db()
        assert vt.is_deleted is True


@pytest.mark.django_db
class TestVehicleCreationModel:
    def test_create(self, company, project):
        fuel = Fuel.objects.create(fuel_type="Diesel")
        vt = VehicleTypeCreation.objects.create(
            vehicleType="Compactor",
            company_id=company,
            project_id=project,
        )
        v = VehicleCreation.objects.create(
            vehicle_no="TN01AB1234",
            fuel_type=fuel,
            vehicle_type=vt,
            capacity=10,
            company_id=company,
            project_id=project,
        )
        assert v.vehicle_no == "TN01AB1234"
        assert v.unique_id.startswith("VEHCRE-")

    def test_default_flags(self, company, project):
        fuel = Fuel.objects.create(fuel_type="CNG")
        vt = VehicleTypeCreation.objects.create(
            vehicleType="Tipper",
            company_id=company,
            project_id=project,
        )
        v = VehicleCreation.objects.create(
            vehicle_no="TN02CD5678",
            fuel_type=fuel,
            vehicle_type=vt,
            capacity=8,
            company_id=company,
            project_id=project,
        )
        assert v.is_active is True
        assert v.is_deleted is False

    def test_foreign_keys(self, company, project):
        fuel = Fuel.objects.create(fuel_type="Petrol")
        vt = VehicleTypeCreation.objects.create(
            vehicleType="Loader",
            company_id=company,
            project_id=project,
        )
        v = VehicleCreation.objects.create(
            vehicle_no="TN03EF9012",
            fuel_type=fuel,
            vehicle_type=vt,
            capacity=6,
            company_id=company,
            project_id=project,
        )
        assert v.fuel_type == fuel
        assert v.vehicle_type == vt
