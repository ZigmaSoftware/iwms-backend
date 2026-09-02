"""Serializer tests for Bins — ward/zone/panchayat writable fields + validation."""
import pytest

from app.models.assets.bins import Bins
from app.models.masters.panchayat import Panchayat
from app.models.masters.ward import Ward
from app.models.schedule_masters.collection_point import Collection_point
from app.serializers.masters.waste_masters.bins_serializer import BinsSerializer


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
    from app.models.staff_creations.waste_collection_bluetooth import WasteType
    return WasteType.objects.create(waste_type_name="General Waste")


@pytest.fixture
def bin_obj(db, company, project, collection_point, waste_type_obj):
    return Bins.objects.create(
        company_id=company, project_id=project,
        collection_point_id=collection_point,
        wastetype_id=waste_type_obj,
        bin_capacity=100,
        bin_type="small",
        bin_name="Serializer Test Bin",
        bin_image="",
        bin_qr="",
    )


def _payload(collection_point, waste_type_obj, **overrides):
    payload = {
        "collection_point_id": collection_point.unique_id,
        "wastetype_id": waste_type_obj.unique_id,
        "bin_capacity": 100,
        "bin_type": "small",
        "bin_name": "Serializer Test Bin",
    }
    payload.update(overrides)
    return payload


def _make_ward(state, district, city, zone=None, panchayat=None, name="Ward 1"):
    return Ward.objects.create(
        ward_name=name,
        state_id=state,
        district_id=district,
        city_id=city,
        zone_id=zone,
        panchayat_id=panchayat,
    )


@pytest.mark.django_db
class TestBinsSerializerFields:
    def test_ward_zone_panchayat_are_writable(self):
        serializer = BinsSerializer()
        for field_name in ("ward_id", "zone_id", "panchayat_id"):
            assert serializer.fields[field_name].read_only is False

    def test_output_includes_zone_ward_panchayat(self, bin_obj, zone, ward):
        collection_point = bin_obj.collection_point_id
        collection_point.wards.add(ward)
        bin_obj.ward_id = ward
        bin_obj.zone_id = zone
        bin_obj.save()
        data = BinsSerializer(bin_obj).data
        assert data["ward_id"] == ward.unique_id
        assert data["ward_name"] == ward.ward_name
        assert data["zone_id"] == zone.unique_id
        assert data["zone_name"] == zone.zone_name
        assert data["panchayat_id"] == collection_point.panchayat_id.unique_id
        assert data["panchayat_name"] == collection_point.panchayat_id.panchayat_name


@pytest.mark.django_db
class TestBinsSerializerWardValidation:
    def test_create_valid_when_ward_is_in_cp(self, collection_point, waste_type_obj, zone, ward):
        collection_point.wards.add(ward)
        serializer = BinsSerializer(
            data=_payload(
                collection_point, waste_type_obj,
                ward_id=ward.unique_id,
                zone_id=zone.unique_id,
            )
        )
        assert serializer.is_valid(), serializer.errors
        bin_obj = serializer.save(
            company_id=collection_point.company_id,
            project_id=collection_point.project_id,
        )
        assert bin_obj.ward_id == ward
        assert bin_obj.zone_id == zone

    def test_create_rejects_ward_not_in_cp(self, collection_point, waste_type_obj, zone):
        unlinked_ward = _make_ward(
            zone.state_id, zone.district_id, zone.city_id, zone=zone, name="Unlinked Ward"
        )
        serializer = BinsSerializer(
            data=_payload(
                collection_point, waste_type_obj,
                ward_id=unlinked_ward.unique_id,
            )
        )
        assert not serializer.is_valid()
        assert "ward_id" in serializer.errors

    def test_create_rejects_zone_and_panchayat_together(
        self, collection_point, waste_type_obj, zone, panchayat
    ):
        serializer = BinsSerializer(
            data=_payload(
                collection_point, waste_type_obj,
                zone_id=zone.unique_id,
                panchayat_id=panchayat.unique_id,
            )
        )
        assert not serializer.is_valid()
        assert "zone_id" in serializer.errors

    def test_create_without_ward_is_valid(self, collection_point, waste_type_obj):
        serializer = BinsSerializer(
            data=_payload(collection_point, waste_type_obj)
        )
        assert serializer.is_valid(), serializer.errors

    def test_accepts_ward_referenced_by_unique_id(
        self, collection_point, waste_type_obj, zone, ward
    ):
        collection_point.wards.add(ward)
        serializer = BinsSerializer(
            data=_payload(
                collection_point, waste_type_obj,
                ward_id=ward.unique_id,
            )
        )
        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data["ward_id"] == ward
