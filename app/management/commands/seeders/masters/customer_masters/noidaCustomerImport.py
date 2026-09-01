from app.management.commands.seeders.base import BaseSeeder

from app.models.common_masters.country import Country
from app.models.common_masters.state import State
from app.models.customers.customercreation import CustomerCreation
from app.models.masters.city import City
from app.models.masters.district import District
from app.models.masters.ward import Ward
from app.models.masters.zone import Zone
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project
from app.models.user_creations.waste_collection_bluetooth import WasteType
from app.models.waste_types.property import Property
from app.models.waste_types.subproperty import SubProperty

COMPANY_NAME = "Blue Planet"
PROJECT_NAME = "Blue Planet Integrated Waste Management"

CITY_NAME = "Noida"
DISTRICT_NAME = "Gautam Buddh Nagar"
STATE_NAME = "Uttar Pradesh"
COUNTRY_NAME = "India"
ZONE_NAME = "ZNE3-GAMMA-01"
WARD_NAME = "B"
PROPERTY_NAME = "Residential"
SUB_PROPERTY_NAME = "Individual House"
CUSTOMER_WASTE_TYPES = ["Wet Waste", "Dry Waste"]

# Sourced verbatim from customer_creation_template_final.xlsx (132 rows,
# all Noida / Gamma-01 / Ward B individual houses). (customer_name,
# building_no, sqft) — every other column in that file was blank.
NOIDA_CUSTOMER_DATA = [
    ("GAMMA-01B3RES", "3", "350.00"),
    ("GAMMA-01B4RES", "4", "350.00"),
    ("GAMMA-01B5RES", "5", "350.00"),
    ("GAMMA-01B10RES", "10", "350.00"),
    ("GAMMA-01B12RES", "12", "375.00"),
    ("GAMMA-01B13RES", "13", "375.00"),
    ("GAMMA-01B15RES", "15", "350.00"),
    ("GAMMA-01B19RES", "19", "350.00"),
    ("GAMMA-01B20RES", "20", "350.00"),
    ("GAMMA-01B22RES", "22", "350.00"),
    ("GAMMA-01B23RES", "23", "350.00"),
    ("GAMMA-01B26RES", "26", "350.00"),
    ("GAMMA-01B27RES", "27", "350.00"),
    ("GAMMA-01B28RES", "28", "350.00"),
    ("GAMMA-01B30RES", "30", "350.00"),
    ("GAMMA-01B31RES", "31", "375.00"),
    ("GAMMA-01B33RES", "33", "350.00"),
    ("GAMMA-01B34RES", "34", "350.00"),
    ("GAMMA-01B35RES", "35", "350.00"),
    ("GAMMA-01B38RES", "38", "350.00"),
    ("GAMMA-01B39RES", "39", "350.00"),
    ("GAMMA-01B40RES", "40", "350.00"),
    ("GAMMA-01B41RES", "41", "350.00"),
    ("GAMMA-01B42RES", "42", "350.00"),
    ("GAMMA-01B44RES", "44", "350.00"),
    ("GAMMA-01B45RES", "45", "350.00"),
    ("GAMMA-01B52RES", "52", "350.00"),
    ("GAMMA-01B53RES", "53", "350.00"),
    ("GAMMA-01B55RES", "55", "350.00"),
    ("GAMMA-01B56RES", "56", "350.00"),
    ("GAMMA-01B61RES", "61", "350.00"),
    ("GAMMA-01B63RES", "63", "350.00"),
    ("GAMMA-01B65RES", "65", "350.00"),
    ("GAMMA-01B66RES", "66", "350.00"),
    ("GAMMA-01B67RES", "67", "350.00"),
    ("GAMMA-01B69RES", "69", "275.00"),
    ("GAMMA-01B70RES", "70", "275.00"),
    ("GAMMA-01B71RES", "71", "275.00"),
    ("GAMMA-01B74RES", "74", "275.00"),
    ("GAMMA-01B75RES", "75", "275.00"),
    ("GAMMA-01B76RES", "76", "275.00"),
    ("GAMMA-01B80RES", "80", "300.00"),
    ("GAMMA-01B81RES", "81", "275.00"),
    ("GAMMA-01B83RES", "83", "275.00"),
    ("GAMMA-01B84RES", "84", "275.00"),
    ("GAMMA-01B88RES", "88", "275.00"),
    ("GAMMA-01B92RES", "92", "275.00"),
    ("GAMMA-01B93RES", "93", "275.00"),
    ("GAMMA-01B94RES", "94", "275.00"),
    ("GAMMA-01B95RES", "95", "275.00"),
    ("GAMMA-01B97RES", "97", "275.00"),
    ("GAMMA-01B99RES", "99", "275.00"),
    ("GAMMA-01B102RES", "102", "275.00"),
    ("GAMMA-01B105RES", "105", "275.00"),
    ("GAMMA-01B108RES", "108", "275.00"),
    ("GAMMA-01B109RES", "109", "275.00"),
    ("GAMMA-01B110RES", "110", "275.00"),
    ("GAMMA-01B111RES", "111", "275.00"),
    ("GAMMA-01B112RES", "112", "275.00"),
    ("GAMMA-01B116RES", "116", "275.00"),
    ("GAMMA-01B117RES", "117", "275.00"),
    ("GAMMA-01B119RES", "119", "275.00"),
    ("GAMMA-01B120RES", "120", "275.00"),
    ("GAMMA-01B121RES", "121", "200.00"),
    ("GAMMA-01B123RES", "123", "200.00"),
    ("GAMMA-01B126RES", "126", "200.00"),
    ("GAMMA-01B128RES", "128", "200.00"),
    ("GAMMA-01B129RES", "129", "200.00"),
    ("GAMMA-01B131RES", "131", "200.00"),
    ("GAMMA-01B132RES", "132", "200.00"),
    ("GAMMA-01B133RES", "133", "200.00"),
    ("GAMMA-01B135RES", "135", "200.00"),
    ("GAMMA-01B136RES", "136", "200.00"),
    ("GAMMA-01B138RES", "138", "200.00"),
    ("GAMMA-01B139RES", "139", "200.00"),
    ("GAMMA-01B140RES", "140", "200.00"),
    ("GAMMA-01B141RES", "141", "200.00"),
    ("GAMMA-01B143RES", "143", "200.00"),
    ("GAMMA-01B144RES", "144", "200.00"),
    ("GAMMA-01B145RES", "145", "200.00"),
    ("GAMMA-01B146RES", "146", "200.00"),
    ("GAMMA-01B147RES", "147", "200.00"),
    ("GAMMA-01B151RES", "151", "200.00"),
    ("GAMMA-01B152RES", "152", "200.00"),
    ("GAMMA-01B153RES", "153", "200.00"),
    ("GAMMA-01B154RES", "154", "200.00"),
    ("GAMMA-01B156RES", "156", "200.00"),
    ("GAMMA-01B157RES", "157", "200.00"),
    ("GAMMA-01B158RES", "158", "200.00"),
    ("GAMMA-01B160RES", "160", "200.00"),
    ("GAMMA-01B164RES", "164", "200.00"),
    ("GAMMA-01B165RES", "165", "200.00"),
    ("GAMMA-01B174RES", "174", "200.00"),
    ("GAMMA-01B176RES", "176", "200.00"),
    ("GAMMA-01B177RES", "177", "200.00"),
    ("GAMMA-01B179RES", "179", "200.00"),
    ("GAMMA-01B185RES", "185", "200.00"),
    ("GAMMA-01B188RES", "188", "200.00"),
    ("GAMMA-01B189RES", "189", "200.00"),
    ("GAMMA-01B190RES", "190", "200.00"),
    ("GAMMA-01B192RES", "192", "200.00"),
    ("GAMMA-01B194RES", "194", "200.00"),
    ("GAMMA-01B195RES", "195", "200.00"),
    ("GAMMA-01B196RES", "196", "200.00"),
    ("GAMMA-01B197RES", "197", "200.00"),
    ("GAMMA-01B199RES", "199", "200.00"),
    ("GAMMA-01B203RES", "203", "200.00"),
    ("GAMMA-01B204RES", "204", "200.00"),
    ("GAMMA-01B207RES", "207", "200.00"),
    ("GAMMA-01B209RES", "209", "200.00"),
    ("GAMMA-01B211RES", "211", "200.00"),
    ("GAMMA-01B213RES", "213", "200.00"),
    ("GAMMA-01B214RES", "214", "200.00"),
    ("GAMMA-01B218RES", "218", "200.00"),
    ("GAMMA-01B219RES", "219", "200.00"),
    ("GAMMA-01B220RES", "220", "200.00"),
    ("GAMMA-01B222RES", "222", "200.00"),
    ("GAMMA-01B224RES", "224", "200.00"),
    ("GAMMA-01B225RES", "225", "200.00"),
    ("GAMMA-01B227RES", "227", "200.00"),
    ("GAMMA-01B229RES", "229", "200.00"),
    ("GAMMA-01B240RES", "240", "200.00"),
    ("GAMMA-01B245RES", "245", "200.00"),
    ("GAMMA-01B247RES", "247", "200.00"),
    ("GAMMA-01B249RES", "249", "200.00"),
    ("GAMMA-01B250RES", "250", "200.00"),
    ("GAMMA-01B253RES", "253", "200.00"),
    ("GAMMA-01B255RES", "255", "200.00"),
    ("GAMMA-01B256RES", "256", "200.00"),
    ("GAMMA-01B259RES", "259", "200.00"),
    ("GAMMA-01B260RES", "260", "200.00"),
    ("GAMMA-01B261RES", "261", "220.00"),
]


class NoidaCustomerImportSeeder(BaseSeeder):
    """Replaces Noida (Greater Noida BP / Gamma-01 / Ward B) customers with
    the authoritative set from customer_creation_template_final.xlsx on
    every run: any existing Noida customer not in NOIDA_CUSTOMER_DATA is
    hard-deleted, and all 132 rows from the file are created/kept in sync."""

    name = "noida_customer_import"

    def run(self):
        company = Company.objects.filter(name=COMPANY_NAME, is_deleted=False).first()
        project = Project.objects.filter(
            name=PROJECT_NAME, company_id=company, is_deleted=False
        ).first() if company else None
        if not company or not project:
            self.log(f"Company '{COMPANY_NAME}' / project '{PROJECT_NAME}' not found — skipping.")
            return

        city = City.objects.filter(name=CITY_NAME, company_id=company, project_id=project, is_deleted=False).first()
        district = District.objects.filter(
            name=DISTRICT_NAME, company_id=company, project_id=project, is_deleted=False
        ).first()
        state = State.objects.filter(name=STATE_NAME).first()
        country = Country.objects.filter(name=COUNTRY_NAME).first()
        zone = Zone.objects.filter(zone_name=ZONE_NAME, company_id=company, project_id=project, is_deleted=False).first()
        ward = Ward.objects.filter(ward_name=WARD_NAME, zone_id=zone, is_deleted=False).first() if zone else None
        property_obj = Property.objects.filter(
            property_name=PROPERTY_NAME, company_id=company, project_id=project, is_deleted=False
        ).first()
        sub_property = SubProperty.objects.filter(
            sub_property_name=SUB_PROPERTY_NAME, property_id=property_obj, is_deleted=False
        ).first() if property_obj else None

        missing = [
            label
            for label, value in (
                ("city", city), ("district", district), ("state", state), ("country", country),
                ("zone", zone), ("ward", ward), ("property", property_obj), ("sub_property", sub_property),
            )
            if value is None
        ]
        if missing:
            self.log(f"Required master data missing ({', '.join(missing)}) — skipping.")
            return

        waste_types = list(
            WasteType.objects.filter(
                company_id=company, project_id=project,
                waste_type_name__in=CUSTOMER_WASTE_TYPES, is_deleted=False,
            )
        )
        if len(waste_types) != len(CUSTOMER_WASTE_TYPES):
            self.log("Required waste types missing — skipping.")
            return

        authoritative_names = {name for name, _building, _sqft in NOIDA_CUSTOMER_DATA}

        stale_qs = CustomerCreation.objects.filter(
            company_id=company, project_id=project, city=city,
        ).exclude(customer_name__in=authoritative_names)
        deleted_count = stale_qs.count()
        stale_qs.delete()

        created_count = 0
        updated_count = 0
        for customer_name, building_no, sqft in NOIDA_CUSTOMER_DATA:
            customer, created = CustomerCreation.objects.update_or_create(
                company_id=company,
                project_id=project,
                customer_name=customer_name,
                defaults={
                    "building_no": building_no,
                    "sqft": sqft,
                    "ward": ward,
                    "zone": zone,
                    "city": city,
                    "district": district,
                    "state": state,
                    "country": country,
                    "property_ref": property_obj,
                    "sub_property": sub_property,
                    "is_active": True,
                    "is_deleted": False,
                },
            )
            customer.waste_types.set(waste_types)
            created_count += int(created)
            updated_count += int(not created)

        self.log(
            f"---Noida customers synced from xlsx: {created_count} created, "
            f"{updated_count} updated, {deleted_count} stale removed "
            f"(total {len(NOIDA_CUSTOMER_DATA)})---"
        )
