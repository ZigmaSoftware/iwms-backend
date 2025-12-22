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

        customers = [
            {
                "customer_name": "Sameer",
                "contact_no": "7890",
                "building_no": "12A",
                "street": "Gamma Road",
                "area": "Gamma 1",
                "pincode": "600017",
                "latitude": "28.4869",
                "longitude": "77.5015",
                "id_no": "AADHAAR-7890-1",
            },
            {
                "customer_name": "Jaisurya",
                "contact_no": "7890",
                "building_no": "14B",
                "street": "Gamma Lane",
                "area": "Gamma 1",
                "pincode": "600017",
                "latitude": "28.4874",
                "longitude": "77.5021",
                "id_no": "AADHAAR-7890-2",
            },
            {
                "customer_name": "Sathya",
                "contact_no": "7890",
                "building_no": "16C",
                "street": "Gamma Street",
                "area": "Gamma 1",
                "pincode": "600017",
                "latitude": "28.4859",
                "longitude": "77.5008",
                "id_no": "AADHAAR-7890-3",
            },
        ]

        for entry in customers:
            CustomerCreation.objects.get_or_create(
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
                    "property": property_obj,
                    "sub_property": sub_property_obj,
                    "is_active": True,
                    "is_deleted": False,
                }
            )

        self.log("Customer creation seeded")
