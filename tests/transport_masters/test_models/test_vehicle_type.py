"""Unit tests for VehicleTypeCreation model — CRUD + constraints."""
import pytest
from app.models.masters.transport_masters.vehicleTypeCreation import VehicleTypeCreation


@pytest.mark.django_db
class TestVehicleTypeCreate:
    def test_basic_create(self):
        vt = VehicleTypeCreation.objects.create(vehicleType="Compactor")
        assert vt.vehicleType == "Compactor"

    def test_unique_id_prefix(self):
        vt = VehicleTypeCreation.objects.create(vehicleType="Tipper")
        assert vt.unique_id.startswith("VHTYPE-")

    def test_str_contains_type(self):
        vt = VehicleTypeCreation.objects.create(vehicleType="Dumper")
        assert "Dumper" in str(vt)


@pytest.mark.django_db
class TestVehicleTypeDefaults:
    def test_is_active_default_true(self):
        vt = VehicleTypeCreation.objects.create(vehicleType="Mini Truck")
        assert vt.is_active is True

    def test_is_deleted_default_false(self):
        vt = VehicleTypeCreation.objects.create(vehicleType="Autorickshaw")
        assert vt.is_deleted is False


@pytest.mark.django_db
class TestVehicleTypeSoftDelete:
    def test_soft_delete(self):
        vt = VehicleTypeCreation.objects.create(vehicleType="Temp Type")
        vt.delete()
        vt.refresh_from_db()
        assert vt.is_deleted is True


@pytest.mark.django_db
class TestVehicleTypeUpdate:
    def test_update_type(self):
        vt = VehicleTypeCreation.objects.create(vehicleType="Old Type")
        vt.vehicleType = "Updated Type"
        vt.save()
        vt.refresh_from_db()
        assert vt.vehicleType == "Updated Type"
