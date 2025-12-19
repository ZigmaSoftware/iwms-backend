# core/management/commands/seeders/customers/customer_creation.py
from api.management.commands.seeders.base import BaseSeeder
from api.apps.continent import Continent
from api.apps.country import Country
from api.apps.state import State
from api.apps.district import District
from api.apps.city import City
from api.apps.zone import Zone
from api.apps.ward import Ward
from api.apps.customercreation import CustomerCreation
from api.apps.property import Property
from api.apps.subproperty import SubProperty


class CustomerCreationSeeder(BaseSeeder):
    name = "customer_creation"

    def run(self):
        # ---- Location hierarchy ----
        country = Country.objects.get(name="India")
        state = State.objects.get(name="Tamil Nadu")
        district = District.objects.get(name="Chennai")
        city = City.objects.get(name="Chennai City")
        zone = Zone.objects.get(name="Zone 1")
        ward = Ward.objects.get(name="Ward 1")

        # ---- Property hierarchy ----
        property_obj = Property.objects.get(property_name="Residential", is_deleted=False)
        sub_property_obj = SubProperty.objects.get(sub_property_name="Apartment", is_deleted=False)

        # ---- Customer ----
        CustomerCreation.objects.get_or_create(
            contact_no="9876543210",
            defaults={
                "customer_name": "Test Customer",
                "building_no": "12A",
                "street": "Main Road",
                "area": "T Nagar",

                "ward": ward,
                "zone": zone,
                "city": city,
                "district": district,
                "state": state,
                "country": country,

                "pincode": "600017",
                "latitude": "13.0827",
                "longitude": "80.2707",

                "id_proof_type": CustomerCreation.IDProofType.AADHAAR,
                "id_no": "1234-5678-9012",

                "property": property_obj,
                "sub_property": sub_property_obj,

                "is_active": True,
                "is_deleted": False,
            }
        )

        self.log("Customer creation seeded")
