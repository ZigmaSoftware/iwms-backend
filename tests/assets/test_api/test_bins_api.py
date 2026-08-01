"""API tests for Bins endpoint — CRUD operations + zone/ward/panchayat filters."""
import pytest
from app.models.assets.bins import Bins
from app.models.masters.panchayat import Panchayat
from app.models.schedule_masters.collection_point import Collection_point

BASE = "/api/v1/waste-types/bins/"


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


def _make_bin(company, project, collection_point, waste_type_obj, **overrides):
    defaults = {
        "company_id": company,
        "project_id": project,
        "collection_point_id": collection_point,
        "wastetype_id": waste_type_obj,
        "bin_capacity": 100,
        "bin_type": "small",
        "bin_name": "API Test Bin",
        "bin_image": "",
        "bin_qr": "",
    }
    defaults.update(overrides)
    return Bins.objects.create(**defaults)


def _ids(resp):
    data = resp.data.get("results", resp.data) if isinstance(resp.data, dict) else resp.data
    return [row["unique_id"] for row in data]


@pytest.mark.django_db
class TestBinsAPIList:
    def test_list_unauthenticated_returns_401(self, api_client):
        resp = api_client.get(BASE)
        assert resp.status_code in (401, 403)

    def test_list_authenticated_returns_200(self, auth_client):
        resp = auth_client.get(BASE)
        assert resp.status_code == 200


@pytest.mark.django_db
class TestBinsAPIRetrieve:
    def test_retrieve_nonexistent_returns_404(self, auth_client):
        resp = auth_client.get(f"{BASE}BIN-NOTEXIST/")
        assert resp.status_code in (404, 400)


@pytest.mark.django_db
class TestBinsAPIWardZonePanchayatFilters:
    def test_filter_by_ward_direct(self, auth_client, company, project, collection_point, waste_type_obj, zone, ward):
        collection_point.wards.add(ward)
        ward_bin = _make_bin(company, project, collection_point, waste_type_obj, ward_id=ward)
        no_ward_bin = _make_bin(
            company, project, collection_point, waste_type_obj,
            bin_name="No Ward Bin",
        )
        resp = auth_client.get(BASE, {"ward": ward.unique_id})
        assert resp.status_code == 200
        ids = _ids(resp)
        assert ward_bin.unique_id in ids
        assert no_ward_bin.unique_id not in ids

    def test_filter_by_ward_id_alias(self, auth_client, company, project, collection_point, waste_type_obj, zone, ward):
        collection_point.wards.add(ward)
        ward_bin = _make_bin(company, project, collection_point, waste_type_obj, ward_id=ward)
        resp = auth_client.get(BASE, {"ward_id": ward.unique_id})
        assert resp.status_code == 200
        assert ward_bin.unique_id in _ids(resp)

    def test_filter_by_zone_direct(self, auth_client, company, project, collection_point, waste_type_obj, zone, ward):
        collection_point.wards.add(ward)
        zone_bin = _make_bin(company, project, collection_point, waste_type_obj, zone_id=zone, ward_id=ward)
        other_zone_bin = _make_bin(
            company, project, collection_point, waste_type_obj,
            bin_name="Other Zone Bin",
        )
        resp = auth_client.get(BASE, {"zone": zone.unique_id})
        assert resp.status_code == 200
        ids = _ids(resp)
        assert zone_bin.unique_id in ids
        assert other_zone_bin.unique_id not in ids

    def test_filter_by_zone_id_alias(self, auth_client, company, project, collection_point, waste_type_obj, zone, ward):
        collection_point.wards.add(ward)
        zone_bin = _make_bin(company, project, collection_point, waste_type_obj, zone_id=zone, ward_id=ward)
        resp = auth_client.get(BASE, {"zone_id": zone.unique_id})
        assert resp.status_code == 200
        assert zone_bin.unique_id in _ids(resp)

    def test_filter_by_panchayat_direct(
        self, auth_client, company, project, collection_point, waste_type_obj, panchayat
    ):
        panchayat_bin = _make_bin(company, project, collection_point, waste_type_obj)
        assert panchayat_bin.panchayat_id == panchayat
        resp = auth_client.get(BASE, {"panchayat": panchayat.unique_id})
        assert resp.status_code == 200
        assert panchayat_bin.unique_id in _ids(resp)

    def test_filter_by_panchayat_id_alias(
        self, auth_client, company, project, collection_point, waste_type_obj, panchayat
    ):
        panchayat_bin = _make_bin(company, project, collection_point, waste_type_obj)
        resp = auth_client.get(BASE, {"panchayat_id": panchayat.unique_id})
        assert resp.status_code == 200
        assert panchayat_bin.unique_id in _ids(resp)

    def test_filter_by_panchayat_filters_direct_field_not_cp(
        self, auth_client, company, project, collection_point, waste_type_obj, panchayat
    ):
        other_cp = Collection_point.objects.create(
            cp_name="Other CP",
            company_id=company, project_id=project,
            state_id=collection_point.state_id,
            city_id=collection_point.city_id,
            district_id=collection_point.district_id,
            latitude="13.0827", longitude="80.2707",
        )
        legacy_bin = _make_bin(company, project, other_cp, waste_type_obj)
        Bins.objects.filter(pk=legacy_bin.pk).update(panchayat_id=None)
        resp = auth_client.get(BASE, {"panchayat": panchayat.unique_id})
        assert resp.status_code == 200
        assert legacy_bin.unique_id not in _ids(resp)

    def test_filter_by_collection_point(self, auth_client, company, project, collection_point, waste_type_obj):
        cp_bin = _make_bin(company, project, collection_point, waste_type_obj)
        resp = auth_client.get(BASE, {"collection_point_id": collection_point.unique_id})
        assert resp.status_code == 200
        assert cp_bin.unique_id in _ids(resp)
