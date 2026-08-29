"""API tests for the mobile waste type lookup endpoint."""
import pytest

from app.models.customers.customercreation import CustomerCreation
from app.models.masters.panchayat import Panchayat
from app.models.user_creations.waste_collection_bluetooth import WasteType
from app.models.waste_types.property import Property
from app.models.waste_types.subproperty import SubProperty


BASE = "/api/v1/waste/get-waste-types/"


@pytest.fixture
def panchayat(db, company, project, state, district, city):
    return Panchayat.objects.create(
        panchayat_name="Customer Panchayat",
        company_id=company,
        project_id=project,
        state_id=state,
        district_id=district,
        city_id=city,
    )


@pytest.fixture
def prop(db):
    return Property.objects.create(property_name="Residential")


@pytest.fixture
def sub_prop(db, prop):
    return SubProperty.objects.create(sub_property_name="Apartment", property_id=prop)


@pytest.fixture
def customer(
    db,
    company,
    project,
    country,
    state,
    district,
    city,
    zone,
    ward,
    panchayat,
    prop,
    sub_prop,
):
    return CustomerCreation.objects.create(
        customer_name="Anitha Menon",
        contact_no="9876543210",
        pincode="600001",
        latitude="13.0827",
        longitude="80.2707",
        id_proof_type="Aadhar",
        id_no="1234-5678-9012",
        company_id=company,
        project_id=project,
        country=country,
        state=state,
        district=district,
        city=city,
        zone=zone,
        ward=ward,
        panchayat_id=panchayat,
        property_ref=prop,
        sub_property=sub_prop,
    )


@pytest.mark.django_db
class TestMobileWasteTypesAPI:
    def test_without_customer_returns_all_active_waste_types(self, auth_client):
        dry = WasteType.objects.create(waste_type_name="Dry Waste")
        electronic = WasteType.objects.create(waste_type_name="Electronic Waste")
        wet = WasteType.objects.create(waste_type_name="Wet Waste")

        resp = auth_client.get(BASE)

        assert resp.status_code == 200
        assert resp.data["status"] == "success"
        assert [row["id"] for row in resp.data["data"]] == [
            wet.unique_id,
            dry.unique_id,
            electronic.unique_id,
        ]
        assert [row["waste_type_name"] for row in resp.data["data"]] == [
            "Wet Waste",
            "Dry Waste",
            "Electronic Waste",
        ]

    def test_customer_id_returns_customer_saved_waste_types(self, auth_client, customer):
        wet = WasteType.objects.create(waste_type_name="Wet Waste")
        dry = WasteType.objects.create(waste_type_name="Dry Waste")
        medical = WasteType.objects.create(waste_type_name="Medical Waste")
        customer.waste_types.set([medical, wet])

        resp = auth_client.get(BASE, {"customer_id": customer.unique_id})

        assert resp.status_code == 200
        assert resp.data["status"] == "success"
        assert resp.data["count"] == 2
        assert [row["id"] for row in resp.data["data"]] == [
            wet.unique_id,
            medical.unique_id,
        ]
        assert dry.unique_id not in [row["id"] for row in resp.data["data"]]

    def test_unknown_customer_returns_empty_success_payload(self, auth_client):
        WasteType.objects.create(waste_type_name="Wet Waste")

        resp = auth_client.get(BASE, {"customer_id": "CUS-does-not-exist"})

        assert resp.status_code == 200
        assert resp.data == {"status": "success", "count": 0, "data": []}
