from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.db.models import Q
from django.utils import timezone

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
from app.models.user_creations.waste_collection_bluetooth import WasteType
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project


# min 6 chars, 1 uppercase + 1 lowercase + 1 digit
DEFAULT_CUSTOMER_PASSWORD = "Customer1"
CUSTOMER_WASTE_TYPES = ["Wet Waste", "Dry Waste", "Mixed Waste", "Sanitary Waste"]

CUSTOMER_DATA = [
    {"customer_name": "Sameer",    "contact_no": "7890123456", "building_no": "12A", "street": "Gamma Road",    "area": "Gamma 1",  "pincode": "600017", "latitude": "13.0826", "longitude": "80.2707", "id_no": "AADHAAR-7890-01", "member_count": 4, "sqft": "1200.00", "water_consumption_lpd": "240.00", "waste_collection_kg_per_day": "3.50"},
    {"customer_name": "Priya",     "contact_no": "7890123457", "building_no": "24B", "street": "Alpha Street",  "area": "Alpha 2",  "pincode": "600018", "latitude": "13.0831", "longitude": "80.2712", "id_no": "AADHAAR-7890-02", "member_count": 3, "sqft": "950.00", "water_consumption_lpd": "180.00", "waste_collection_kg_per_day": "2.75"},
    {"customer_name": "Ravi",      "contact_no": "7890123458", "building_no": "5C",  "street": "Beta Lane",     "area": "Beta 3",   "pincode": "600019", "latitude": "13.0836", "longitude": "80.2717", "id_no": "AADHAAR-7890-03", "member_count": 5, "sqft": "1450.00", "water_consumption_lpd": "300.00", "waste_collection_kg_per_day": "4.50"},
    {"customer_name": "Kavitha",   "contact_no": "7890123459", "building_no": "33D", "street": "Delta Avenue",  "area": "Delta 1",  "pincode": "600020", "latitude": "13.0841", "longitude": "80.2722", "id_no": "AADHAAR-7890-04", "member_count": 2, "sqft": "800.00", "water_consumption_lpd": "150.00", "waste_collection_kg_per_day": "2.10"},
    {"customer_name": "Murugan",   "contact_no": "7890123460", "building_no": "7E",  "street": "Epsilon Road",  "area": "Epsilon 2","pincode": "600021", "latitude": "13.0846", "longitude": "80.2727", "id_no": "AADHAAR-7890-05", "member_count": 6, "sqft": "21000.00", "water_consumption_lpd": "45000.00", "waste_collection_kg_per_day": "110.00"},
    {"customer_name": "Sangeetha", "contact_no": "7890123461", "building_no": "18F", "street": "Zeta Street",   "area": "Zeta 3",   "pincode": "600022", "latitude": "13.0851", "longitude": "80.2732", "id_no": "AADHAAR-7890-06", "member_count": 4, "sqft": "1100.00", "water_consumption_lpd": "220.00", "waste_collection_kg_per_day": "3.00"},
    {"customer_name": "Vijay",     "contact_no": "7890123462", "building_no": "42G", "street": "Eta Lane",      "area": "Eta 1",    "pincode": "600023", "latitude": "13.0856", "longitude": "80.2737", "id_no": "AADHAAR-7890-07", "member_count": 3, "sqft": "1000.00", "water_consumption_lpd": "200.00", "waste_collection_kg_per_day": "2.80"},
    {"customer_name": "Deepa",     "contact_no": "7890123463", "building_no": "9H",  "street": "Theta Avenue",  "area": "Theta 2",  "pincode": "600024", "latitude": "13.0861", "longitude": "80.2742", "id_no": "AADHAAR-7890-08", "member_count": 5, "sqft": "1250.00", "water_consumption_lpd": "260.00", "waste_collection_kg_per_day": "3.60"},
    {"customer_name": "Arun",      "contact_no": "7890123464", "building_no": "51I", "street": "Iota Road",     "area": "Iota 3",   "pincode": "600025", "latitude": "13.0866", "longitude": "80.2747", "id_no": "AADHAAR-7890-09", "member_count": 4, "sqft": "1150.00", "water_consumption_lpd": "210.00", "waste_collection_kg_per_day": "3.10"},
    {"customer_name": "Meena",     "contact_no": "7890123465", "building_no": "3J",  "street": "Kappa Street",  "area": "Kappa 1",  "pincode": "600026", "latitude": "13.0871", "longitude": "80.2752", "id_no": "AADHAAR-7890-10", "member_count": 2, "sqft": "900.00", "water_consumption_lpd": "170.00", "waste_collection_kg_per_day": "2.40"},
    {"customer_name": "Suresh",    "contact_no": "7890123466", "building_no": "27K", "street": "Lambda Lane",   "area": "Lambda 2", "pincode": "600027", "latitude": "13.0876", "longitude": "80.2757", "id_no": "AADHAAR-7890-11", "member_count": 5, "sqft": "1300.00", "water_consumption_lpd": "280.00", "waste_collection_kg_per_day": "4.00"},
    {"customer_name": "Divya",     "contact_no": "7890123467", "building_no": "14L", "street": "Mu Avenue",     "area": "Mu 3",     "pincode": "600028", "latitude": "13.0881", "longitude": "80.2762", "id_no": "AADHAAR-7890-12", "member_count": 3, "sqft": "980.00", "water_consumption_lpd": "190.00", "waste_collection_kg_per_day": "2.90"},
    {"customer_name": "Karthik",   "contact_no": "7890123468", "building_no": "6M",  "street": "Nu Road",       "area": "Nu 1",     "pincode": "600029", "latitude": "13.0886", "longitude": "80.2767", "id_no": "AADHAAR-7890-13", "member_count": 4, "sqft": "1180.00", "water_consumption_lpd": "230.00", "waste_collection_kg_per_day": "3.40"},
    {"customer_name": "Radha",     "contact_no": "7890123469", "building_no": "39N", "street": "Xi Street",     "area": "Xi 2",     "pincode": "600030", "latitude": "13.0891", "longitude": "80.2772", "id_no": "AADHAAR-7890-14", "member_count": 6, "sqft": "1500.00", "water_consumption_lpd": "320.00", "waste_collection_kg_per_day": "4.80"},
    {"customer_name": "Balaji",    "contact_no": "7890123470", "building_no": "22O", "street": "Omicron Lane",  "area": "Omicron 3","pincode": "600031", "latitude": "13.0896", "longitude": "80.2777", "id_no": "AADHAAR-7890-15", "member_count": 3, "sqft": "1020.00", "water_consumption_lpd": "205.00", "waste_collection_kg_per_day": "3.00"},
]


def backfill_missing_customer_ids():
    missing_customers = CustomerCreation.objects.filter(
        Q(customer_id__isnull=True) | Q(customer_id="")
    ).order_by("company_id_id", "project_id_id", "unique_id")
    repaired_count = 0
    for customer in missing_customers.iterator():
        customer.save(update_fields=["customer_id"])
        repaired_count += 1
    return repaired_count


class CustomerCreationSeeder(BaseSeeder):
    name = "customer_creation"

    def run(self):
        repaired_count = backfill_missing_customer_ids()
        if repaired_count:
            self.log(f"Backfilled customer IDs for {repaired_count} customers.")

        country = Country.objects.filter(name="India").first()
        state = State.objects.filter(name="Tamil Nadu").first()
        district = District.objects.filter(name="Chennai").first()
        city = City.objects.filter(name="Chennai City").first()
        zone = Zone.objects.filter(zone_name="Zone 1").first()
        ward = Ward.objects.filter(ward_name="Ward 1").first()

        if not all([country, state, district, city, zone, ward]):
            self.log("Required location hierarchy missing.")
            return

        property_obj = Property.objects.filter(property_name="Residential", is_deleted=False).first()
        sub_property_obj = SubProperty.objects.filter(sub_property_name="Apartment", is_deleted=False).first()

        if not property_obj or not sub_property_obj:
            self.log("Required property/sub-property missing.")
            return

        company = Company.objects.filter(is_deleted=False).first()
        project = Project.objects.filter(company_id=company, is_deleted=False).first() if company else None
        if not company or not project:
            self.log("Company/project missing. Seed superadmin masters before customers.")
            return

        waste_types = list(
            WasteType.objects.filter(
                company_id=company,
                project_id=project,
                waste_type_name__in=CUSTOMER_WASTE_TYPES,
                is_deleted=False,
            ).order_by("waste_type_name")
        )
        if not waste_types:
            waste_types = list(
                WasteType.objects.filter(
                    waste_type_name__in=CUSTOMER_WASTE_TYPES,
                    is_deleted=False,
                ).order_by("waste_type_name")
            )
        if not waste_types:
            self.log("Waste types missing. Seed waste types before customers.")
            return

        customer_type = UserType.objects.filter(name__iexact="customer").first()
        if not customer_type:
            self.log("UserType 'customer' missing. Seed role-assign before customers.")
            return

        UserModel = get_user_model()

        now = timezone.now()
        created_count = 0
        updated_count = 0
        for entry in CUSTOMER_DATA:
            hashed_password = make_password(DEFAULT_CUSTOMER_PASSWORD)
            family_members = [
                {
                    "member_name": f"{entry['customer_name']} Family {idx}",
                    "id_proof_type": CustomerCreation.IDProofType.AADHAAR,
                    "id_no": f"{entry['id_no']}-FM{idx}",
                }
                for idx in range(1, int(entry["member_count"]) + 1)
            ]
            customer, created = CustomerCreation.objects.update_or_create(
                company_id=company,
                project_id=project,
                id_no=entry["id_no"],
                defaults={
                    "customer_name": entry["customer_name"],
                    "contact_no": entry["contact_no"],
                    "username": entry["contact_no"],
                    "password": hashed_password,
                    "password_crt_date": now,
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
                    "sqft": entry["sqft"],
                    "water_consumption_lpd": entry["water_consumption_lpd"],
                    "waste_collection_kg_per_day": entry["waste_collection_kg_per_day"],
                    "id_proof_type": CustomerCreation.IDProofType.AADHAAR,
                    "id_no": entry["id_no"],
                    "member_count": entry["member_count"],
                    "family_members": family_members,
                    "property_ref": property_obj,
                    "sub_property": sub_property_obj,
                    "user_type_id": customer_type,
                    "is_active": True,
                    "is_deleted": False,
                },
            )
            # Seed the waste streams only for a brand-new customer. Re-running
            # this seeder must not clobber waste types edited (in particular
            # REMOVED) via Customer Creation on the web — `.set()` replaces the
            # whole M2M, so calling it on the update branch silently restored
            # every type an operator had deleted.
            if created:
                customer.waste_types.set(waste_types)
                created_count += 1
            else:
                updated_count += 1
            action = "Created" if created else "Exists"
            self.log(
                f"Customer {action}: {customer.customer_name} "
                f"[unique_id={customer.unique_id}, customer_id={customer.customer_id}]"
            )
            UserModel.objects.filter(customer_id_id=customer.unique_id).delete()

        self.log(f"---Customers seeded ({created_count} created, {updated_count} updated)---")

        repaired_count = backfill_missing_customer_ids()
        if repaired_count:
            self.log(f"Backfilled customer IDs for {repaired_count} customers.")
