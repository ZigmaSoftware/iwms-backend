"""API tests for CustomerCreation endpoint — CRUD operations."""
import pytest
from rest_framework.test import APIRequestFactory, force_authenticate

from app.models.customers.customercreation import CustomerCreation
from app.models.masters.panchayat import Panchayat
from app.models.staff_creations.staffcreation import Staffcreation
from app.models.waste_types.property import Property
from app.models.waste_types.subproperty import SubProperty
from app.viewsets.masters.customer_masters.customercreation_viewset import (
    CustomerCreationViewSet,
)

BASE = "/api/v1/customer-masters/customercreations/"


@pytest.fixture
def panchayat(db, company, project, state, district, city):
    return Panchayat.objects.create(
        panchayat_name="Customer API Panchayat",
        company_id=company,
        project_id=project,
        state_id=state,
        district_id=district,
        city_id=city,
    )


@pytest.fixture
def property_ref(db):
    return Property.objects.create(property_name="Residential")


@pytest.fixture
def sub_property(db, property_ref):
    return SubProperty.objects.create(
        sub_property_name="Individual House",
        property_id=property_ref,
    )


def create_customer(
    *,
    name,
    company,
    project,
    country,
    state,
    district,
    city,
    zone,
    ward,
    panchayat,
    property_ref,
    sub_property,
    id_suffix,
):
    return CustomerCreation.objects.create(
        customer_name=name,
        contact_no=f"98765432{id_suffix:02d}",
        pincode="600001",
        latitude="13.0827",
        longitude="80.2707",
        id_proof_type="Aadhar",
        id_no=f"1234-5678-{id_suffix:04d}",
        company_id=company,
        project_id=project,
        country=country,
        state=state,
        district=district,
        city=city,
        zone=zone,
        ward=ward,
        panchayat_id=panchayat,
        property_ref=property_ref,
        sub_property=sub_property,
    )


@pytest.mark.django_db
class TestCustomerAPIList:
    def test_list_unauthenticated_returns_401(self, api_client):
        resp = api_client.get(BASE)
        assert resp.status_code in (401, 403)

    def test_list_authenticated_returns_200(self, auth_client):
        resp = auth_client.get(BASE)
        assert resp.status_code == 200


@pytest.mark.django_db
class TestCustomerAPIRetrieve:
    def test_retrieve_nonexistent_returns_404(self, auth_client):
        resp = auth_client.get(f"{BASE}CUS-NOTEXIST/")
        assert resp.status_code in (404, 400)


@pytest.mark.django_db
class TestCustomerFcmRegistration:
    def test_register_token_moves_ownership_to_authenticated_customer(
        self,
        company,
        project,
        country,
        state,
        district,
        city,
        zone,
        ward,
        panchayat,
        property_ref,
        sub_property,
    ):
        token = "FCM-CUSTOMER-DEVICE"
        customer = create_customer(
            name="Current Customer",
            company=company,
            project=project,
            country=country,
            state=state,
            district=district,
            city=city,
            zone=zone,
            ward=ward,
            panchayat=panchayat,
            property_ref=property_ref,
            sub_property=sub_property,
            id_suffix=1,
        )
        old_customer = create_customer(
            name="Old Customer",
            company=company,
            project=project,
            country=country,
            state=state,
            district=district,
            city=city,
            zone=zone,
            ward=ward,
            panchayat=panchayat,
            property_ref=property_ref,
            sub_property=sub_property,
            id_suffix=2,
        )
        old_customer.fcm_token = token
        old_customer.save(update_fields=["fcm_token"])
        staff = Staffcreation.objects.create(
            employee_name="Token Owner",
            company_id=company,
            project_id=project,
            fcm_token=token,
        )

        request = APIRequestFactory().post(
            f"{BASE}register-fcm-token/",
            {"fcm_token": token},
            format="json",
        )
        force_authenticate(request, user=customer)
        view = CustomerCreationViewSet.as_view({"post": "register_fcm_token"})

        response = view(request)

        assert response.status_code == 200
        customer.refresh_from_db()
        old_customer.refresh_from_db()
        staff.refresh_from_db()
        assert customer.fcm_token == token
        assert old_customer.fcm_token is None
        assert staff.fcm_token is None
