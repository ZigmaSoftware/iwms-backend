from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password

from app.management.commands.seeders.base import BaseSeeder

from app.models.common_masters.country import Country
from app.models.common_masters.state import State
from app.models.masters.district import District
from app.models.masters.city import City
from app.models.masters.zone import Zone
from app.models.masters.ward import Ward

from app.models.customers.customercreation import CustomerCreation
from app.models.role_assigns.userType import UserType

from app.models.waste_types.property import Property
from app.models.waste_types.subproperty import SubProperty
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project


DEFAULT_CUSTOMER_PASSWORD = "Customer@123"


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
        zone = Zone.objects.get(zone_name="Zone 1")
        ward = Ward.objects.get(ward_name="Ward 1")

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
                "password": DEFAULT_CUSTOMER_PASSWORD,
            },
        ]

        for entry in customers:
            # ensure username defaults to contact number when not provided
            entry.setdefault("username", entry["contact_no"])
            raw_password = entry.get("password") or DEFAULT_CUSTOMER_PASSWORD
            entry["password"] = make_password(raw_password)

        customer_type = UserType.objects.filter(name__iexact="customer").first()
        if not customer_type:
            self.log("UserType 'customer' missing. Seed role-assign before customers.")
            return
        UserModel = get_user_model()

        # --------------------------------------------------
        # CREATE CUSTOMERS
        # --------------------------------------------------
        for entry in customers:
            customer, created = CustomerCreation.objects.get_or_create(
                customer_name=entry["customer_name"],
                contact_no=entry["contact_no"],
                defaults={
                    "username": entry["username"],
                    "password": entry["password"],
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
                    "user_type_id": customer_type,
                    "is_active": True,
                    "is_deleted": False,
                }
            )

            if created:
                self.log(f"Customer created: {customer.customer_name}")
            else:
                update_fields = []
                if not customer.username and entry.get("username"):
                    customer.username = entry["username"]
                    update_fields.append("username")
                if not customer.password and entry.get("password"):
                    customer.password = entry["password"]
                    update_fields.append("password")
                if update_fields:
                    customer.save(update_fields=update_fields)

            # Customer auth uses CustomerCreation directly.
            # Remove legacy mirrored auth user rows for this customer.
            UserModel.objects.filter(customer_id_id=customer.unique_id).delete()

        self.log("---Customers seeded successfully---")
