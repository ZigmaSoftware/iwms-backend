from api.management.commands.seeders.base import BaseSeeder

from api.models.commonmasters.country import Country
from api.models.commonmasters.state import State
from api.models.masters.district import District
from api.models.masters.city import City
from api.models.masters.zone import Zone
from api.models.masters.ward import Ward

from api.models.customers.customercreation import CustomerCreation

from api.models.assets.property import Property
from api.models.assets.subproperty import SubProperty
from api.models.superadminmasters.company import Company
from api.models.superadminmasters.project import Project


class CustomerCreationSeeder(BaseSeeder):
    name = "customer_creation"

    def run(self):
        # --------------------------------------------------
        # LOCATION HIERARCHY
        # --------------------------------------------------
        country = Country.objects.get(name="India")
        state = State.objects.get(name="Tamil Nadu")
        district = District.objects.get(name="Chennai")
        city = City.objects.get(name="Chennai City")
        zone = Zone.objects.get(name="Zone 1")
        ward = Ward.objects.get(name="Ward 1")

        # --------------------------------------------------
        # PROPERTY HIERARCHY
        # --------------------------------------------------
        property_obj = Property.objects.get(
            property_name="Residential",
            is_deleted=False
        )
        sub_property_obj = SubProperty.objects.get(
            sub_property_name="Apartment",
            is_deleted=False
        )

        company = Company.objects.filter(is_deleted=False).first()
        project = None
        if company:
            project = Project.objects.filter(company_id=company, is_deleted=False).first()

        # --------------------------------------------------
        # CUSTOMER SEED DATA
        # --------------------------------------------------
        customers = [
            {
                "customer_name": "Sameer",
                "contact_no": "7890123456",
                "building_no": "12A",
                "street": "Gamma Road",
                "area": "Gamma 1",
                "pincode": "600017",
                "latitude": "28.4869",
                "longitude": "77.5015",
                "id_no": "AADHAAR-7890-1",
            },
        ]

        # --------------------------------------------------
        # CREATE CUSTOMERS
        # --------------------------------------------------
        for entry in customers:
            customer, created = CustomerCreation.objects.get_or_create(
                customer_name=entry["customer_name"],
                contact_no=entry["contact_no"],
                defaults={
                    "building_no": entry["building_no"],
                    "street": entry["street"],
                    "area": entry["area"],
                    "ward": ward,
                    "zone": zone,
                    "city": city,
                    "district": district,
                    "state": state,
                    "country": country,
                    "pincode": entry["pincode"],
                    "latitude": entry["latitude"],
                    "longitude": entry["longitude"],
                    "id_proof_type": CustomerCreation.IDProofType.AADHAAR,
                    "id_no": entry["id_no"],
                    "property_ref": property_obj,
                    "sub_property": sub_property_obj,
                    "company_id": company,
                    "project_id": project,
                    "is_active": True,
                    "is_deleted": False,
                }
            )

            if created:
                self.log(f"Customer created: {customer.customer_name}")

        self.log("✅ Customers seeded successfully")
