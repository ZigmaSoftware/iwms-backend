"""Unit tests for Bins model — CRUD + constraints."""
import pytest
from app.models.assets.bins import Bins
from app.models.schedule_masters.collection_point import Collection_point
from app.models.masters.panchayat import Panchayat
from app.models.masters.ward import Ward


@pytest.fixture
def panchayat(db, company, project, state, district, city):
    return Panchayat.objects.create(
        panchayat_name="Test Panchayat",
        company_id=company, project_id=project,
        state_id=state, district_id=district, city_id=city,
    )


@pytest.fixture
def collection_point(db, company, project, state, district, city, panchayat):
    return Collection_point.objects.create(
        cp_name="CP-01",
        company_id=company, project_id=project,
        state_id=state, city_id=city, district_id=district,
        panchayat_id=panchayat,
        latitude="13.0827", longitude="80.2707",
    )


@pytest.fixture
def waste_type_obj(db):
    from app.models.user_creations.waste_collection_bluetooth import WasteType
    return WasteType.objects.create(waste_type_name="General Waste")


@pytest.fixture
def bin_obj(db, company, project, district, city, collection_point, waste_type_obj):
    return Bins.objects.create(
        company_id=company, project_id=project,
        district_id=district, city_id=city,
        collection_point_id=collection_point,
        wastetype_id=waste_type_obj,
        bin_capacity=100,
        bin_type="small",
        bin_name="Test Bin",
        bin_image="",
        bin_qr="",
    )


@pytest.mark.django_db
class TestBinsCreate:
    def test_basic_create(self, bin_obj):
        assert bin_obj.bin_capacity == 100
        assert bin_obj.bin_type == "small"

    def test_unique_id_prefix(self, bin_obj):
        assert bin_obj.unique_id.startswith("BIN-")

    def test_foreign_key_company(self, bin_obj, company):
        assert bin_obj.company_id == company

    def test_foreign_key_collection_point(self, bin_obj, collection_point):
        assert bin_obj.collection_point_id == collection_point


@pytest.mark.django_db
class TestBinsDefaults:
    def test_is_active_default_true(self, bin_obj):
        assert bin_obj.is_active is True

    def test_is_deleted_default_false(self, bin_obj):
        assert bin_obj.is_deleted is False


@pytest.mark.django_db
class TestBinsSoftDelete:
    def test_soft_delete(self, bin_obj):
        bin_obj.delete()
        bin_obj.refresh_from_db()
        assert bin_obj.is_deleted is True


@pytest.mark.django_db
class TestBinsUpdate:
    def test_update_bin_capacity(self, bin_obj):
        bin_obj.bin_capacity = 200
        bin_obj.save()
        bin_obj.refresh_from_db()
        assert bin_obj.bin_capacity == 200

    def test_update_bin_type(self, bin_obj):
        bin_obj.bin_type = "large"
        bin_obj.save()
        bin_obj.refresh_from_db()
        assert bin_obj.bin_type == "large"


@pytest.mark.django_db
class TestBinsZoneWardPanchayat:
    def test_ward_zone_panchayat_fields_are_nullable(self, bin_obj):
        assert bin_obj.ward_id is None
        assert bin_obj.zone_id is None

    def test_save_derives_panchayat_from_collection_point(self, bin_obj, panchayat):
        bin_obj.refresh_from_db()
        assert bin_obj.panchayat_id == panchayat

    def test_save_derives_zone_from_ward(self, bin_obj, collection_point, zone):
        ward = Ward.objects.create(
            ward_name="Zone Ward",
            state_id=zone.state_id,
            district_id=zone.district_id,
            city_id=zone.city_id,
            zone_id=zone,
        )
        collection_point.wards.add(ward)
        bin_obj.ward_id = ward
        bin_obj.zone_id = None
        bin_obj.save()
        bin_obj.refresh_from_db()
        assert bin_obj.ward_id == ward
        assert bin_obj.zone_id == zone

    def test_save_derives_panchayat_from_ward(self, bin_obj, collection_point, panchayat):
        ward = Ward.objects.create(
            ward_name="Panchayat Ward",
            state_id=panchayat.state_id,
            district_id=panchayat.district_id,
            city_id=panchayat.city_id,
            panchayat_id=panchayat,
        )
        collection_point.wards.add(ward)
        bin_obj.ward_id = ward
        bin_obj.panchayat_id = None
        bin_obj.save()
        bin_obj.refresh_from_db()
        assert bin_obj.ward_id == ward
        assert bin_obj.panchayat_id == panchayat

    def test_explicit_zone_and_ward_are_persisted(self, bin_obj, zone, ward):
        bin_obj.zone_id = zone
        bin_obj.ward_id = ward
        bin_obj.save()
        bin_obj.refresh_from_db()
        assert bin_obj.zone_id == zone
        assert bin_obj.ward_id == ward
