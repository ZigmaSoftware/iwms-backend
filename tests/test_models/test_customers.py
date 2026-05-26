"""Model tests for CustomerCreation and FeedBack."""
import pytest
from app.models.customers.customercreation import CustomerCreation
from app.models.customers.feedback import FeedBack
from app.models.masters.panchayat import Panchayat
from app.models.waste_types.property import Property
from app.models.waste_types.subproperty import SubProperty


@pytest.fixture
def panchayat(db, company, project, state, district, city):
    return Panchayat.objects.create(
        panchayat_name="Test Panchayat",
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
def customer(db, company, project, continent, country, state, district, city, zone, ward, panchayat, prop, sub_prop):
    return CustomerCreation.objects.create(
        customer_name="Alice",
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
class TestCustomerCreationModel:

    def test_create(self, customer):
        assert customer.customer_name == "Alice"
        assert customer.unique_id.startswith("CUS-")

    def test_default_flags(self, customer):
        assert customer.is_active is True
        assert customer.is_deleted is False

    def test_soft_delete(self, customer):
        customer.delete()
        customer.refresh_from_db()
        assert customer.is_deleted is True
        assert customer.is_active is False

    def test_optional_fields_are_null(self, customer):
        assert customer.building_no is None
        assert customer.email is None
        assert customer.apartment_name is None

    def test_foreign_key_company(self, customer, company):
        assert customer.company_id == company

    def test_ordering_alphabetical(self, db, company, project, country, state, district, city, zone, ward, panchayat, prop, sub_prop):
        base = dict(
            pincode="600001", latitude="13.0", longitude="80.0",
            id_proof_type="Aadhar",
            company_id=company, project_id=project,
            country=country, state=state, district=district,
            city=city, zone=zone, ward=ward,
            panchayat_id=panchayat, property_ref=prop, sub_property=sub_prop,
        )
        CustomerCreation.objects.create(customer_name="Zebra", id_no="0001", contact_no="0000000001", **base)
        CustomerCreation.objects.create(customer_name="Apple", id_no="0002", contact_no="0000000002", **base)
        names = list(CustomerCreation.objects.values_list("customer_name", flat=True))
        assert names == sorted(names)

    def test_unique_ids_differ(self, customer, db, company, project, country, state, district, city, zone, ward, panchayat, prop, sub_prop):
        c2 = CustomerCreation.objects.create(
            customer_name="Bob",
            contact_no="1111111111",
            pincode="600002",
            latitude="13.1",
            longitude="80.1",
            id_proof_type="Aadhar",
            id_no="9999-9999-9999",
            company_id=company, project_id=project,
            country=country, state=state, district=district,
            city=city, zone=zone, ward=ward,
            panchayat_id=panchayat, property_ref=prop, sub_property=sub_prop,
        )
        assert customer.unique_id != c2.unique_id


@pytest.mark.django_db
class TestFeedBackModel:

    def test_create(self, customer, company, project):
        fb = FeedBack.objects.create(
            category="Satisfied",
            feedback_details="Service was good.",
            customer=customer,
            company_id=company,
            project_id=project,
        )
        assert fb.category == "Satisfied"
        assert fb.unique_id.startswith("FEED-")

    def test_default_flags(self, customer, company, project):
        fb = FeedBack.objects.create(
            category="Poor",
            customer=customer,
            company_id=company,
            project_id=project,
        )
        assert fb.is_active is True
        assert fb.is_deleted is False

    def test_soft_delete(self, customer, company, project):
        fb = FeedBack.objects.create(
            category="Not Satisfied",
            customer=customer,
            company_id=company,
            project_id=project,
        )
        fb.delete()
        fb.refresh_from_db()
        assert fb.is_deleted is True
        assert fb.is_active is False

    def test_optional_details_nullable(self, customer, company, project):
        fb = FeedBack.objects.create(
            category="Satisfied",
            customer=customer,
            company_id=company,
            project_id=project,
        )
        assert fb.feedback_details is None

    def test_foreign_key_customer(self, customer, company, project):
        fb = FeedBack.objects.create(
            category="Excellent",
            customer=customer,
            company_id=company,
            project_id=project,
        )
        assert fb.customer == customer
