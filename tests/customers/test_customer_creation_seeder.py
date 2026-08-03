import pytest

from app.management.commands.seeders.masters.customer_masters.customerCreation import (
    CUSTOMER_WASTE_TYPES,
    CustomerCreationSeeder,
)
from app.models.customers.customercreation import CustomerCreation
from app.models.role_assigns.userType import UserType
from app.models.user_creations.waste_collection_bluetooth import WasteType
from app.models.waste_types.property import Property
from app.models.waste_types.subproperty import SubProperty


@pytest.mark.django_db
def test_customer_seeder_generates_scoped_ids_and_is_idempotent(
    company,
    project,
    country,
    state,
    district,
    city,
    zone,
    ward,
):
    property_obj = Property.objects.create(
        property_name="Residential",
        company_id=company,
        project_id=project,
    )
    SubProperty.objects.create(
        sub_property_name="Apartment",
        property_id=property_obj,
        company_id=company,
        project_id=project,
    )
    UserType.objects.create(name="Customer")
    for waste_type_name in CUSTOMER_WASTE_TYPES:
        WasteType.objects.create(
            waste_type_name=waste_type_name,
            company_id=company,
            project_id=project,
        )

    seeder = CustomerCreationSeeder()
    seeder.run()
    seeder.run()

    customers = CustomerCreation.objects.filter(
        company_id=company,
        project_id=project,
    ).order_by("customer_id")
    assert customers.count() == 15
    assert list(customers.values_list("customer_id", flat=True)) == [
        f"CUST{sequence:04d}" for sequence in range(1, 16)
    ]
    assert all(
        unique_id.startswith("CUS-")
        for unique_id in customers.values_list("unique_id", flat=True)
    )

    first_customer = customers.first()
    CustomerCreation.objects.filter(pk=first_customer.pk).update(customer_id="")
    seeder.run()
    first_customer.refresh_from_db()

    assert first_customer.customer_id.startswith("CUST")
    assert first_customer.customer_id != ""
