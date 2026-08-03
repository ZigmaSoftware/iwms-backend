"""Unit tests for CustomerCreation model — CRUD + constraints."""
import pytest
from app.models.customers.customercreation import CustomerCreation
from app.models.masters.panchayat import Panchayat
from app.models.waste_types.property import Property
from app.models.waste_types.subproperty import SubProperty


def create_customer_in_scope(source, *, name, project):
    return CustomerCreation.objects.create(
        customer_name=name,
        contact_no="9123456789",
        pincode=source.pincode,
        latitude=source.latitude,
        longitude=source.longitude,
        id_proof_type=source.id_proof_type,
        id_no=f"{source.id_no}-{name}",
        company_id=source.company_id,
        project_id=project,
        country=source.country,
        state=source.state,
        district=source.district,
        city=source.city,
        zone=source.zone,
        ward=source.ward,
        panchayat_id=source.panchayat_id,
        property_ref=source.property_ref,
        sub_property=source.sub_property,
    )


@pytest.fixture
def panchayat(db, company, project, state, district, city):
    return Panchayat.objects.create(
        panchayat_name="Customer Panchayat",
        company_id=company, project_id=project,
        state_id=state, district_id=district, city_id=city,
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
        company_id=company, project_id=project,
        country=country, state=state, district=district,
        city=city, zone=zone, ward=ward,
        panchayat_id=panchayat,
        property_ref=prop, sub_property=sub_prop,
    )


@pytest.mark.django_db
class TestCustomerCreationCreate:
    def test_basic_create(self, customer):
        assert customer.customer_name == "Alice"

    def test_unique_id_prefix(self, customer):
        assert customer.unique_id.startswith("CUS-")

    def test_customer_id_starts_at_one(self, customer):
        assert customer.customer_id == "CUST0001"

    def test_customer_id_is_exposed_by_serializer(self, customer):
        from app.serializers.masters.customer_masters.customercreation_serializer import (
            CustomerCreationSerializer,
        )

        assert CustomerCreationSerializer(customer).data["customer_id"] == "CUST0001"

    def test_foreign_key_company(self, customer, company):
        assert customer.company_id == company

    def test_optional_fields_null(self, customer):
        assert customer.building_no is None
        assert customer.email is None


@pytest.mark.django_db
class TestCustomerCreationDefaults:
    def test_is_active_default_true(self, customer):
        assert customer.is_active is True

    def test_is_deleted_default_false(self, customer):
        assert customer.is_deleted is False


@pytest.mark.django_db
class TestCustomerCreationSoftDelete:
    def test_soft_delete(self, customer):
        customer.delete()
        customer.refresh_from_db()
        assert customer.is_deleted is True
        assert customer.is_active is False


@pytest.mark.django_db
class TestCustomerCreationUpdate:
    def test_update_name(self, customer):
        customer.customer_name = "Bob"
        customer.save()
        customer.refresh_from_db()
        assert customer.customer_name == "Bob"

    def test_update_contact(self, customer):
        customer.contact_no = "9999999999"
        customer.save()
        customer.refresh_from_db()
        assert customer.contact_no == "9999999999"

    def test_update_repairs_missing_customer_id(self, customer):
        CustomerCreation.objects.filter(pk=customer.pk).update(customer_id="")
        customer.refresh_from_db()
        customer.customer_name = "Repaired Customer"
        customer.save(update_fields=["customer_name"])
        customer.refresh_from_db()

        assert customer.customer_id == "CUST0001"


@pytest.mark.django_db
class TestCustomerCreationDisplayId:
    def test_customer_id_increments_within_company_and_project(self, customer):
        second_customer = create_customer_in_scope(
            customer,
            name="Second Customer",
            project=customer.project_id,
        )

        assert second_customer.customer_id == "CUST0002"

    def test_customer_id_restarts_for_another_project(self, customer, company):
        from app.models.superadmin_masters.project import Project

        other_project = Project.objects.create(name="Other Project", company_id=company)
        other_customer = create_customer_in_scope(
            customer,
            name="Other Project Customer",
            project=other_project,
        )

        assert other_customer.customer_id == "CUST0001"
