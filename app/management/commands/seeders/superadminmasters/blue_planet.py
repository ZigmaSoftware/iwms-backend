import math

from app.management.commands.seeders.base import BaseSeeder
from django.contrib.auth.hashers import make_password
from django.db.models import F, Max
from django.utils import timezone
from app.models.common_masters.continent import Continent
from app.models.common_masters.country import Country
from app.models.common_masters.state import State
from app.models.masters.city import City
from app.models.masters.district import District
from app.models.masters.panchayat import Panchayat
from app.models.masters.ward import Ward
from app.models.masters.zone import Zone
from app.models.role_assigns.staffUserType import StaffUserType
from app.models.role_assigns.userType import UserType
from app.models.schedule_masters.collection_point import Collection_point
from app.models.schedule_masters.staff_template import StaffTemplate
from app.models.schedule_masters.trip_plan import TripPlan
from app.models.schedule_masters.trip_plan_collection_point import TripPlanCollectionPoint
from app.models.assets.bins import Bins, BinType
from app.models.customers.customercreation import CustomerCreation
from app.models.grivences.complaints import Complaint
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project
from app.models.transport_masters.fuel import Fuel
from app.models.transport_masters.vehicleCreation import VehicleCreation
from app.models.transport_masters.vehicleTypeCreation import VehicleTypeCreation
from app.models.user_creations.staffcreation import Staffcreation
from app.models.user_creations.waste_collection_bluetooth import WasteType
from app.models.waste_types.property import Property
from app.models.waste_types.subproperty import SubProperty


# min 6 chars, 1 uppercase + 1 lowercase + 1 digit (matches CustomerCreationSeeder's rule)
DEFAULT_CUSTOMER_PASSWORD = "Customer1"


def _scatter(base_lat, base_lon, index, spread=0.01):
    """Deterministic pseudo-random offset around an anchor point, so seeded
    pins land scattered across real streets on a map instead of walking in
    a single straight line (which a fixed per-index increment produces).
    Uses different irrational-ish multipliers for lat vs lon and a sign
    flip driven by index parity so points spread in every direction."""
    angle = (index * 137.508) % 360  # golden-angle spacing — avoids clustering
    radius = spread * (0.35 + 0.65 * ((index * 0.618) % 1))
    d_lat = radius * math.cos(math.radians(angle))
    d_lon = radius * math.sin(math.radians(angle))
    return base_lat + d_lat, base_lon + d_lon


class BluePlanetSeeder(BaseSeeder):
    name = "blue_planet"

    COMPANY_NAME = "Blue Planet"

    ATTENDANCE_API_URL = "http://zigfly.in/attendance-api/api/sync/recognized"
    ATTENDANCE_API_KEY = "ZIGFLY_SYNC_2025"
    GPS_API_URL = "https://api.vamosys.com/getVehicleHistory"
    GPS_VEHICLE_TRACKING_API = "https://api.vamosys.com/mobile/getGrpDataForTrustedClients"
    WEIGHMENT_API_URL = (
        "https://zigma.in/d2d/folders/waste_collected_summary_report/"
        "waste_collected_data_api.php"
    )

    # Real Vamosys-tracked fleet for Greater Noida BP (orgId=BLUEPLANET,
    # fcode=VAM) — vehicle_no values match the live GPS feed's regNo/vehicleId
    # exactly so the vehicle tracking page can match each pin to its vehicle.
    GNO_REAL_VEHICLES = [
        {"vehicle_no": "UP16RT5634", "vehicle_type": "Bus", "latitude": 28.476127, "longitude": 77.480789},
        {"vehicle_no": "UP16RT5635", "vehicle_type": "Truck", "latitude": 28.476191, "longitude": 77.480818},
        {"vehicle_no": "UP16KT1739", "vehicle_type": "Truck", "latitude": 28.475805, "longitude": 77.480743},
        {"vehicle_no": "UP16KT1907", "vehicle_type": "Van", "latitude": 28.447853, "longitude": 77.478098},
        {"vehicle_no": "UP19KT1909", "vehicle_type": "Truck", "latitude": 28.475827, "longitude": 77.480693},
        {"vehicle_no": "UP16KT1911", "vehicle_type": "Truck", "latitude": 28.475796, "longitude": 77.480649},
        {"vehicle_no": "UP16KT1740", "vehicle_type": "Truck", "latitude": 28.476076, "longitude": 77.480649},
        {"vehicle_no": "UP16KT1738", "vehicle_type": "Truck", "latitude": 28.475704, "longitude": 77.480498},
        {"vehicle_no": "UP16KT1741", "vehicle_type": "Truck", "latitude": 28.475891, "longitude": 77.480729},
        {"vehicle_no": "UP16KT1742", "vehicle_type": "Truck", "latitude": 28.476100, "longitude": 77.480729},
        {"vehicle_no": "UP16KT1737", "vehicle_type": "Truck", "latitude": 28.475771, "longitude": 77.480551},
        {"vehicle_no": "UP16KT1908", "vehicle_type": "Truck", "latitude": 28.475782, "longitude": 77.480782},
        {"vehicle_no": "UP16KT1912", "vehicle_type": "Truck", "latitude": 28.475884, "longitude": 77.480373},
    ]

    # Real, genuine Greater Noida localities (not synthetic/scattered
    # points) used as a dedicated 5-stop household-collection route for one
    # real Vamosys-tracked vehicle. Greater Noida BP is household-collection
    # only, so each stop is a real customer at a real address, not a
    # standalone Collection_point (which belongs to bin collection).
    GNO_REAL_ROUTE_VEHICLE_NO = "UP16KT1737"
    GNO_REAL_ROUTE_STOPS = [
        {
            "name": "Rakesh Gupta", "suffix": "R1", "building": "12", "street": "Pari Chowk Road",
            "area": "Pari Chowk", "pincode": "201310", "latitude": 28.474700, "longitude": 77.504600,
        },
        {
            "name": "Sanjay Malhotra", "suffix": "R2", "building": "45", "street": "Alpha 1 Market Road",
            "area": "Alpha 1", "pincode": "201308", "latitude": 28.472100, "longitude": 77.514700,
        },
        {
            "name": "Meera Agarwal", "suffix": "R3", "building": "9", "street": "Beta 2 Sector Road",
            "area": "Beta 2", "pincode": "201309", "latitude": 28.466700, "longitude": 77.500900,
        },
        {
            "name": "Vikram Chaudhary", "suffix": "R4", "building": "22", "street": "Knowledge Park III Road",
            "area": "Knowledge Park 3", "pincode": "201313", "latitude": 28.474500, "longitude": 77.489900,
        },
        {
            "name": "Poonam Bhatt", "suffix": "R5", "building": "3", "street": "Surajpur Site Road",
            "area": "Surajpur", "pincode": "201306", "latitude": 28.487200, "longitude": 77.501100,
        },
    ]

    PROJECT_LOCATION = {
        "Blue Planet Integrated Waste Management": {
            "state": "Uttar Pradesh",
            "district": "Gautam Buddh Nagar",
            "city": "Noida",
            "prefix": "GNO",
            "base_lat": 28.474400,
            "base_lon": 77.504000,
        },
        "Palakkad BP": {
            "state": "Kerala",
            "district": "Palakkad",
            "city": "Palakkad",
            "prefix": "PAL",
            "base_lat": 10.786700,
            "base_lon": 76.654800,
        },
    }

    # (customer_name, contact_no suffix, building_no, street, area, pincode, id suffix, member_count, sqft, water_lpd, waste_kg_per_day)
    CUSTOMER_DATA = {
        "Palakkad BP": [
            ("Anitha Menon",   "01", "12A", "Temple Road",   "Kalpathy",   "678001", 4, "1200.00", "240.00", "3.50"),
            ("Suresh Kumar",   "02", "24B", "River Street",  "Olavakkode", "678002", 3, "950.00",  "180.00", "2.75"),
            ("Radhika Nair",   "03", "5C",  "Fort Lane",     "Kalpathy",   "678003", 5, "1450.00", "300.00", "4.50"),
            ("Vinod Pillai",   "04", "33D", "Market Avenue", "Olavakkode", "678004", 2, "800.00",  "150.00", "2.10"),
            ("Lakshmi Warrier","05", "7E",  "Canal Road",    "Kalpathy",   "678005", 6, "1350.00", "270.00", "3.90"),
            ("Rajeev Menon",   "06", "18F", "Mill Street",   "Olavakkode", "678006", 4, "1100.00", "220.00", "3.00"),
            ("Deepa Krishnan", "07", "42G", "Station Road",  "Kalpathy",   "678007", 3, "1000.00", "200.00", "2.80"),
            ("Anoop Varma",    "08", "9H",  "Palace Road",   "Olavakkode", "678008", 5, "1250.00", "260.00", "3.60"),
        ],
        "Blue Planet Integrated Waste Management": [
            ("Amit Sharma",    "01", "12A", "Alpha Road",    "Alpha 1",    "201308", 4, "1200.00", "240.00", "3.50"),
            ("Priyanka Gupta", "02", "24B", "Beta Street",   "Beta 2",     "201309", 3, "950.00",  "180.00", "2.75"),
            ("Rohit Verma",    "03", "5C",  "Gamma Lane",    "Gamma 3",    "201310", 5, "1450.00", "300.00", "4.50"),
            ("Neha Singh",     "04", "33D", "Delta Avenue",  "Delta 1",    "201311", 2, "800.00",  "150.00", "2.10"),
            ("Ankit Tyagi",    "05", "7E",  "Sector Road",   "Sector 12",  "201312", 6, "1350.00", "270.00", "3.90"),
            ("Kavita Chauhan", "06", "18F", "Knowledge Park", "Knowledge Park 3", "201313", 4, "1100.00", "220.00", "3.00"),
            ("Manoj Yadav",    "07", "42G", "Pari Chowk",    "Pari Chowk", "201314", 3, "1000.00", "200.00", "2.80"),
            ("Sunita Rawat",   "08", "9H",  "Surajpur Road", "Surajpur",   "201315", 5, "1250.00", "260.00", "3.60"),
        ],
    }

    # Real-world-approximate boundary polygons for named localities within
    # Greater Noida and Palakkad — hand-picked to correspond to genuine
    # areas on the map (not a synthetic box around wherever seeded assets
    # happened to land). Connected in order to draw the geofence polygon.
    WARD_REAL_BOUNDARIES = {
        "GNO Ward 1": [  # Alpha 1 / Alpha 2 sector block, Greater Noida
            {"latitude": 28.4720, "longitude": 77.5145},
            {"latitude": 28.4718, "longitude": 77.5245},
            {"latitude": 28.4635, "longitude": 77.5248},
            {"latitude": 28.4610, "longitude": 77.5180},
            {"latitude": 28.4640, "longitude": 77.5130},
        ],
        "GNO Ward 2": [  # Knowledge Park III block, Greater Noida
            {"latitude": 28.4790, "longitude": 77.4890},
            {"latitude": 28.4795, "longitude": 77.5010},
            {"latitude": 28.4715, "longitude": 77.5015},
            {"latitude": 28.4705, "longitude": 77.4905},
        ],
        "GNO Ward 3": [  # Pari Chowk / Surajpur block, Greater Noida
            {"latitude": 28.4930, "longitude": 77.5090},
            {"latitude": 28.4935, "longitude": 77.5205},
            {"latitude": 28.4805, "longitude": 77.5210},
            {"latitude": 28.4800, "longitude": 77.5095},
        ],
        "PAL Ward 1": [  # Kalpathy block, Palakkad
            {"latitude": 10.7920, "longitude": 76.6540},
            {"latitude": 10.7925, "longitude": 76.6650},
            {"latitude": 10.7810, "longitude": 76.6655},
            {"latitude": 10.7770, "longitude": 76.6580},
            {"latitude": 10.7820, "longitude": 76.6520},
        ],
        "PAL Ward 2": [  # Olavakkode block, Palakkad
            {"latitude": 10.7700, "longitude": 76.6350},
            {"latitude": 10.7705, "longitude": 76.6460},
            {"latitude": 10.7595, "longitude": 76.6465},
            {"latitude": 10.7590, "longitude": 76.6355},
        ],
        "PAL Ward 3": [  # Town center / Palakkad Fort area
            {"latitude": 10.7810, "longitude": 76.6600},
            {"latitude": 10.7815, "longitude": 76.6710},
            {"latitude": 10.7700, "longitude": 76.6715},
            {"latitude": 10.7695, "longitude": 76.6605},
        ],
    }

    # (main_category, sub_category, category, priority, status, details)
    COMPLAINT_DATA = [
        ("Missed Collection", "Bin not collected", Complaint.CategoryChoices.COLLECTION, Complaint.PriorityChoices.HIGH, Complaint.StatusChoices.PROGRESSING, "Bin was not collected on the scheduled day."),
        ("Vehicle Delay", "Late arrival", Complaint.CategoryChoices.TRANSPORT, Complaint.PriorityChoices.MEDIUM, Complaint.StatusChoices.CLOSED, "Collection vehicle arrived 2 hours late."),
        ("Segregation", "Mixed waste", Complaint.CategoryChoices.SEGREGATION, Complaint.PriorityChoices.LOW, Complaint.StatusChoices.CLOSED, "Wet and dry waste were mixed during pickup."),
    ]

    def _base_geo(self, state_name):
        asia, _ = Continent.objects.get_or_create(name="Asia")
        india, _ = Country.objects.get_or_create(
            name="India",
            continent_id=asia,
            defaults={"currency": "INR", "mob_code": "+91", "is_active": True, "is_deleted": False},
        )
        state, _ = State.objects.get_or_create(
            name=state_name,
            country_id=india,
            continent_id=asia,
            defaults={"label": state_name[:2].upper(), "is_active": True, "is_deleted": False},
        )
        return asia, india, state

    def _staff_role(self, name):
        staff_type, _ = UserType.objects.get_or_create(
            name="Staff",
            defaults={"is_active": True, "is_deleted": False},
        )
        role, _ = StaffUserType.objects.get_or_create(
            name=name,
            usertype_id=staff_type,
            defaults={"is_active": True, "is_deleted": False},
        )
        return staff_type, role

    # Named real staff for Greater Noida BP (prefix GNO) — this project uses
    # actual employee names instead of the generic Driver1/Operator1/... labels.
    GNO_NAMED_STAFF = [
        ("driver1", "Company Driver", "ASHISH KASANA"),
        ("operator1", "Company Operator", "CHREN SINGH"),
        ("supervisor", "Company Supervisor", "Mithun.M"),
    ]

    def _create_staff(self, company, project, district, city, zones, wards, prefix):
        staff_type, driver_role = self._staff_role("Company Driver")
        _, operator_role = self._staff_role("Company Operator")
        _, supervisor_role = self._staff_role("Company Supervisor")
        role_by_name = {
            "Company Driver": driver_role,
            "Company Operator": operator_role,
            "Company Supervisor": supervisor_role,
        }

        if prefix == "GNO":
            staff_defs = [
                (label, role_by_name[role_name], employee_name)
                for label, role_name, employee_name in self.GNO_NAMED_STAFF
            ]
        else:
            staff_defs = [
                ("driver1", driver_role, f"BP {prefix} Driver1"),
                ("driver2", driver_role, f"BP {prefix} Driver2"),
                ("operator1", operator_role, f"BP {prefix} Operator1"),
                ("operator2", operator_role, f"BP {prefix} Operator2"),
                ("supervisor", supervisor_role, f"BP {prefix} Supervisor"),
            ]

        staff = {}
        for label, role, employee_name in staff_defs:
            username = f"bp_{prefix.lower()}_{label}"
            defaults = {
                "employee_name": employee_name,
                "office_email": f"{username}@blueplanet.local",
                "user_type_id": staff_type,
                "staffusertype_id": role,
                "password": "Blue123",
                "company_id": company,
                "project_id": project,
                "district_id": district,
                "city_id": city,
                "zone_id": zones[0],
                "ward_id": wards[0],
                "is_active": True,
                "is_deleted": False,
                "approval_status": Staffcreation.APPROVAL_APPROVED,
                "login_enabled": True,
            }
            obj, _ = Staffcreation.objects.update_or_create(
                username=username,
                defaults=defaults,
            )
            staff[label] = obj
        return staff

    def _create_vehicles(self, company, project, prefix):
        fuel, _ = Fuel.objects.get_or_create(
            fuel_type="Diesel",
            defaults={"description": "Diesel fuel", "is_active": True, "is_deleted": False},
        )

        if prefix == "GNO":
            return self._create_gno_real_vehicles(company, project, fuel)

        vehicle_type, _ = VehicleTypeCreation.objects.get_or_create(
            vehicleType=f"Blue Planet {prefix} Compactor",
            defaults={
                "description": f"Blue Planet {prefix} compactor",
                "is_active": True,
                "is_deleted": False,
            },
        )
        vehicles = []
        for idx in range(1, 3):
            vehicle, _ = VehicleCreation.objects.update_or_create(
                vehicle_no=f"BP-{prefix}-VEH-0{idx}",
                defaults={
                    "vehicle_type": vehicle_type,
                    "fuel_type": fuel,
                    "company_id": company,
                    "project_id": project,
                    "capacity": "3000.00",
                    "mileage_per_liter": "6.00",
                    "service_record": "Blue Planet seeded vehicle",
                    "vehicle_insurance": "Blue Planet Insurance",
                    "vehicle_condition": VehicleCreation.ConditionChoices.NEW,
                    "fuel_tank_capacity": "120.00",
                    "is_active": True,
                    "is_deleted": False,
                },
            )
            vehicles.append(vehicle)
        return vehicles

    def _create_gno_real_vehicles(self, company, project, fuel):
        """Vehicles for Greater Noida BP backed by the real Vamosys-tracked
        fleet (see GNO_REAL_VEHICLES) instead of synthetic BP-GNO-VEH-0N
        rows, so vehicle_no matches the live GPS feed's regNo exactly and
        the vehicle tracking page can pair each pin to its DB vehicle."""
        # Deactivate (not delete) the old synthetic demo vehicles — they're
        # referenced by protected FKs from historical trips/logs/events, so
        # they must stay in place, just hidden from active use. Palakkad BP
        # is untouched.
        VehicleCreation.objects.filter(
            project_id=project, vehicle_no__startswith="BP-GNO-VEH-"
        ).update(is_active=False, is_deleted=True)

        vehicles = []
        for entry in self.GNO_REAL_VEHICLES:
            vehicle_type, _ = VehicleTypeCreation.objects.get_or_create(
                vehicleType=entry["vehicle_type"],
                defaults={
                    "description": f"Vamosys-tracked {entry['vehicle_type']}",
                    "is_active": True,
                    "is_deleted": False,
                },
            )
            vehicle, _ = VehicleCreation.objects.update_or_create(
                vehicle_no=entry["vehicle_no"],
                defaults={
                    "vehicle_type": vehicle_type,
                    "fuel_type": fuel,
                    "company_id": company,
                    "project_id": project,
                    "capacity": "3000.00",
                    "mileage_per_liter": "6.00",
                    "service_record": "Vamosys GPS-tracked vehicle",
                    "vehicle_insurance": "Blue Planet Insurance",
                    "vehicle_condition": VehicleCreation.ConditionChoices.NEW,
                    "fuel_tank_capacity": "120.00",
                    "is_active": True,
                    "is_deleted": False,
                },
            )
            vehicles.append(vehicle)
        return vehicles

    def _create_property_data(self, company, project):
        prop, _ = Property.objects.update_or_create(
            company_id=company,
            project_id=project,
            property_name="Agricultural",
            defaults={"is_active": True, "is_deleted": False},
        )
        sub_property, _ = SubProperty.objects.update_or_create(
            property_id=prop,
            sub_property_name="Farm",
            defaults={
                "company_id": company,
                "project_id": project,
                "is_active": True,
                "is_deleted": False,
            },
        )
        residential_prop, _ = Property.objects.update_or_create(
            company_id=company,
            project_id=project,
            property_name="Residential",
            defaults={"is_active": True, "is_deleted": False},
        )
        residential_sub, _ = SubProperty.objects.update_or_create(
            property_id=residential_prop,
            sub_property_name="Individual House",
            defaults={
                "company_id": company,
                "project_id": project,
                "is_active": True,
                "is_deleted": False,
            },
        )
        return prop, sub_property, residential_prop, residential_sub

    def _create_waste_types(self, company, project):
        result = []
        for name in ("Mixed Waste", "Wet Waste", "Dry Waste"):
            waste_type, _ = WasteType.objects.update_or_create(
                company_id=company,
                project_id=project,
                waste_type_name=name,
                defaults={"is_active": True, "is_deleted": False},
            )
            result.append(waste_type)
        return result

    def _create_customers(self, company, project, project_name, district, city, state, country, zone, ward, panchayat, property_obj, sub_property, waste_types):
        prefix = self.PROJECT_LOCATION[project_name]["prefix"]
        contact_base = "94" if prefix[0].upper() == "P" else "95"
        customers = []
        for idx, (name, suffix, building, street, area, pincode, member_count, sqft, water_lpd, waste_kg) in enumerate(
            self.CUSTOMER_DATA[project_name]
        ):
            if ward.latitude:
                lat, lon = _scatter(float(ward.latitude), float(ward.longitude), idx + 40, spread=0.004)
            else:
                lat, lon = 0.0, 0.0
            id_no = f"AADHAAR-BP-{prefix}-{suffix}"
            family_members = [
                {
                    "member_name": f"{name} Family {member_idx}",
                    "id_proof_type": CustomerCreation.IDProofType.AADHAAR,
                    "id_no": f"{id_no}-FM{member_idx}",
                }
                for member_idx in range(1, member_count + 1)
            ]
            customer, _ = CustomerCreation.objects.update_or_create(
                company_id=company,
                project_id=project,
                id_no=id_no,
                defaults={
                    "customer_name": name,
                    "contact_no": f"9{contact_base}00{idx:05d}",
                    "username": f"bp_{prefix.lower()}_customer_{suffix}",
                    "password": make_password(DEFAULT_CUSTOMER_PASSWORD),
                    "password_crt_date": timezone.now(),
                    "building_no": building,
                    "street": street,
                    "area": area,
                    "ward": ward,
                    "zone": zone,
                    "city": city,
                    "district": district,
                    "state": state,
                    "country": country,
                    "panchayat_id": panchayat,
                    "pincode": pincode,
                    "latitude": f"{lat:.6f}",
                    "longitude": f"{lon:.6f}",
                    "sqft": sqft,
                    "water_consumption_lpd": water_lpd,
                    "waste_collection_kg_per_day": waste_kg,
                    "id_proof_type": CustomerCreation.IDProofType.AADHAAR,
                    "id_no": id_no,
                    "member_count": member_count,
                    "family_members": family_members,
                    "property_ref": property_obj,
                    "sub_property": sub_property,
                    "is_active": True,
                    "is_deleted": False,
                },
            )
            customer.waste_types.set(waste_types)
            customers.append(customer)
        return customers

    def _create_complaints(self, company, project, customers):
        complaints = []
        for idx, (main_category, sub_category, category, priority, status, details) in enumerate(self.COMPLAINT_DATA):
            customer = customers[idx % len(customers)]
            complaint, _ = Complaint.objects.update_or_create(
                company_id=company,
                project_id=project,
                customer=customer,
                main_category=main_category,
                sub_category=sub_category,
                defaults={
                    "category": category,
                    "priority": priority,
                    "status": status,
                    "details": details,
                },
            )
            complaints.append(complaint)
        return complaints

    def _create_project_operational_data(self, company, project, config):
        prefix = config["prefix"]
        asia, india, state = self._base_geo(config["state"])
        district, _ = District.objects.update_or_create(
            name=config["district"],
            state_id=state,
            defaults={
                "continent_id": asia,
                "country_id": india,
                "company_id": company,
                "project_id": project,
                "is_active": True,
                "is_deleted": False,
            },
        )
        city, _ = City.objects.update_or_create(
            name=config["city"],
            state_id=state,
            district_id=district,
            defaults={
                "continent_id": asia,
                "country_id": india,
                "company_id": company,
                "project_id": project,
                "description": f"{project.name} city",
                "is_active": True,
                "is_deleted": False,
            },
        )
        base_lat = config["base_lat"]
        base_lon = config["base_lon"]

        zones = []
        wards = []
        panchayats = []
        collection_points = []
        for idx in range(1, 4):
            zone_lat, zone_lon = _scatter(base_lat, base_lon, idx, spread=0.02)
            zone, _ = Zone.objects.update_or_create(
                zone_name=f"{prefix} Zone {idx}",
                city_id=city,
                company_id=company,
                project_id=project,
                defaults={
                    "state_id": state,
                    "district_id": district,
                    "latitude": zone_lat,
                    "longitude": zone_lon,
                    "is_active": True,
                    "is_deleted": False,
                },
            )
            zones.append(zone)

            ward_lat, ward_lon = _scatter(zone_lat, zone_lon, idx + 10, spread=0.006)
            ward, _ = Ward.objects.update_or_create(
                ward_name=f"{prefix} Ward {idx}",
                zone_id=zone,
                company_id=company,
                project_id=project,
                defaults={
                    "state_id": state,
                    "district_id": district,
                    "city_id": city,
                    "latitude": ward_lat,
                    "longitude": ward_lon,
                    "is_active": True,
                    "is_deleted": False,
                },
            )
            wards.append(ward)

            panchayat_lat, panchayat_lon = _scatter(zone_lat, zone_lon, idx + 20, spread=0.006)
            panchayat, _ = Panchayat.objects.update_or_create(
                panchayat_name=f"{prefix} PLB {idx}",
                company_id=company,
                project_id=project,
                defaults={
                    "state_id": state,
                    "district_id": district,
                    "city_id": city,
                    "agreed_weight_kg": 800,
                    "weight_unit": "kg",
                    "latitude": panchayat_lat,
                    "longitude": panchayat_lon,
                    "is_active": True,
                    "is_deleted": False,
                },
            )
            panchayats.append(panchayat)

            cp_lat, cp_lon = _scatter(zone_lat, zone_lon, idx + 30, spread=0.006)
            collection_point, _ = Collection_point.objects.update_or_create(
                cp_name=f"CP-{prefix}-{idx:02d}",
                panchayat_id=panchayat,
                company_id=company,
                project_id=project,
                defaults={
                    "state_id": state,
                    "district_id": district,
                    "city_id": city,
                    "latitude": cp_lat,
                    "longitude": cp_lon,
                    "is_active": True,
                    "is_deleted": False,
                },
            )
            collection_point.wards.clear()
            collection_points.append(collection_point)

        if prefix == "GNO":
            self._create_noida_customer_scope(company, project, asia, india, state)

        agri_property, agri_sub_property, residential_property, residential_sub_property = (
            self._create_property_data(company, project)
        )
        waste_types = self._create_waste_types(company, project)
        staff = self._create_staff(company, project, district, city, zones, wards, prefix)
        vehicles = self._create_vehicles(company, project, prefix)

        staff_template, _ = StaffTemplate.objects.update_or_create(
            driver_id=staff["driver1"],
            operator_id=staff["operator1"],
            defaults={
                "company_id": company,
                "project_id": project,
                "extra_operator_id": [],
                "status": StaffTemplate.Status.ACTIVE,
                "is_active": True,
                "is_deleted": False,
            },
        )

        bins = []
        for cp_idx, cp in enumerate(collection_points):
            for waste_type in waste_types:
                qr = f"QR-BP-{prefix}-{cp.cp_name.split('-')[-1]}-{waste_type.waste_type_name.upper().replace(' ', '-')}"
                bin_obj, _ = Bins.objects.update_or_create(
                    bin_qr=qr,
                    defaults={
                        "company_id": company,
                        "project_id": project,
                        "collection_point_id": cp,
                        "wastetype_id": waste_type,
                        "ward_id": wards[cp_idx],
                        "zone_id": zones[cp_idx],
                        "bin_name": f"{cp.cp_name} {waste_type.waste_type_name}",
                        "bin_capacity": 240,
                        "bin_type": BinType.MEDIUM,
                        "bin_image": "default.png",
                        "is_active": True,
                        "is_deleted": False,
                    },
                )
                bins.append(bin_obj)

        # ------------------------------------------------------------
        # Bin-collection TripPlan — 1 per project, visiting every CP/bin
        # ------------------------------------------------------------
        trip_plan, _ = TripPlan.objects.update_or_create(
            company_id=company,
            project_id=project,
            staff_template_id=staff_template,
            vehicle_id=vehicles[0],
            panchayat_id=panchayats[0],
            defaults={
                "district_id": district,
                "city_id": city,
                "zone_id": None,
                "supervisor_id": staff["supervisor"],
                "property_id": agri_property,
                "sub_property_id": agri_sub_property,
                "waste_type_id": waste_types[0],
                "waste_type_ids": [waste_type.unique_id for waste_type in waste_types],
                "trip_trigger_weight_kg": 800,
                "max_vehicle_capacity_kg": 3000,
                "scheduled_time": "13:00",
                "collection_type": TripPlan.COLLECTION_TYPE_BIN,
                "is_auto_assign": True,
                "approval_status": TripPlan.ApprovalStatus.APPROVED,
                "status": TripPlan.Status.ACTIVE,
                "is_active": True,
                "is_deleted": False,
            },
        )

        existing = TripPlanCollectionPoint.objects.filter(trip_plan_id=trip_plan)
        if existing.exists():
            max_sequence = existing.aggregate(max_sequence=Max("sequence"))["max_sequence"] or 0
            existing.update(
                sequence=F("sequence") + max_sequence + len(bins) + 1000,
                is_deleted=True,
                is_active=False,
            )
        for idx, bin_obj in enumerate(bins, start=1):
            TripPlanCollectionPoint.objects.update_or_create(
                trip_plan_id=trip_plan,
                collection_point_id=bin_obj.collection_point_id,
                bin_id=bin_obj,
                defaults={
                    "company_id": company,
                    "project_id": project,
                    "collection_type": TripPlanCollectionPoint.COLLECTION_TYPE_BIN,
                    "sequence": idx,
                    "is_active": True,
                    "is_deleted": False,
                },
            )

        # ------------------------------------------------------------
        # Household customers + complaints
        # ------------------------------------------------------------
        customers = self._create_customers(
            company, project, project.name, district, city, state, india,
            zones[0], wards[0], panchayats[0], residential_property, residential_sub_property, waste_types,
        )
        complaints = self._create_complaints(company, project, customers)

        if prefix == "GNO":
            self._create_gno_dedicated_vehicle_route(
                company, project, district, city, state, india, zones[0], wards[0], panchayats[0],
                staff_template, staff["supervisor"], residential_property, residential_sub_property, waste_types,
            )

        # ------------------------------------------------------------
        # Household-collection TripPlan — 1 per project, one stop
        # ------------------------------------------------------------
        household_plan, _ = TripPlan.objects.update_or_create(
            company_id=company,
            project_id=project,
            staff_template_id=staff_template,
            vehicle_id=vehicles[-1],
            panchayat_id=None,
            collection_type=TripPlan.COLLECTION_TYPE_HOUSEHOLD,
            defaults={
                "district_id": district,
                "city_id": city,
                "zone_id": zones[0],
                "supervisor_id": staff["supervisor"],
                "property_id": residential_property,
                "sub_property_id": residential_sub_property,
                "waste_type_id": waste_types[0],
                "waste_type_ids": [waste_types[0].unique_id],
                "trip_trigger_weight_kg": 400,
                "max_vehicle_capacity_kg": 3000,
                "scheduled_time": "09:00",
                "is_auto_assign": True,
                "approval_status": TripPlan.ApprovalStatus.APPROVED,
                "status": TripPlan.Status.ACTIVE,
                "is_active": True,
                "is_deleted": False,
            },
        )
        household_plan.wards.set([wards[0]])
        TripPlanCollectionPoint.objects.get_or_create(
            trip_plan_id=household_plan,
            sequence=1,
            defaults={
                "collection_type": TripPlanCollectionPoint.COLLECTION_TYPE_HOUSEHOLD,
                "is_active": True,
            },
        )

        self._finalize_ward_boundaries(wards, bins, customers)

        return {
            "district": district,
            "city": city,
            "zones": zones,
            "wards": wards,
            "panchayats": panchayats,
            "collection_points": collection_points,
            "bins": bins,
            "trip_plan": trip_plan,
            "household_plan": household_plan,
            "customers": customers,
            "complaints": complaints,
        }

    def _create_noida_customer_scope(self, company, project, asia, india, state):
        district, _ = District.objects.update_or_create(
            name="Gautam Buddh Nagar",
            state_id=state,
            defaults={
                "continent_id": asia,
                "country_id": india,
                "company_id": company,
                "project_id": project,
                "is_active": True,
                "is_deleted": False,
            },
        )
        city, _ = City.objects.update_or_create(
            name="Noida",
            state_id=state,
            district_id=district,
            company_id=company,
            project_id=project,
            defaults={
                "continent_id": asia,
                "country_id": india,
                "description": "Noida city for Gamma-01 customer import",
                "is_active": True,
                "is_deleted": False,
            },
        )
        zone, _ = Zone.objects.update_or_create(
            zone_name="ZNE3-GAMMA-01",
            city_id=city,
            company_id=company,
            project_id=project,
            defaults={
                "state_id": state,
                "district_id": district,
                "latitude": 28.474400,
                "longitude": 77.504000,
                "is_active": True,
                "is_deleted": False,
            },
        )
        Ward.objects.update_or_create(
            ward_name="B",
            zone_id=zone,
            company_id=company,
            project_id=project,
            defaults={
                "state_id": state,
                "district_id": district,
                "city_id": city,
                "latitude": 28.474400,
                "longitude": 77.504000,
                "is_active": True,
                "is_deleted": False,
            },
        )

    def _create_gno_dedicated_vehicle_route(
        self, company, project, district, city, state, country, zone, ward, panchayat,
        staff_template, supervisor, property_obj, sub_property, waste_types,
    ):
        """A dedicated static household-collection route for one real
        Vamosys-tracked vehicle (GNO_REAL_ROUTE_VEHICLE_NO), visiting 5 real
        customers at real Greater Noida localities (GNO_REAL_ROUTE_STOPS) —
        not synthetic scattered points. Greater Noida BP is household
        collection only, so stops are customers (each with their own real
        lat/lon), not standalone Collection_point rows."""
        vehicle = VehicleCreation.objects.get(
            project_id=project, vehicle_no=self.GNO_REAL_ROUTE_VEHICLE_NO
        )

        customers = []
        for route_idx, stop in enumerate(self.GNO_REAL_ROUTE_STOPS, start=1):
            id_no = f"AADHAAR-BP-GNO-ROUTE-{stop['suffix']}"
            customer, _ = CustomerCreation.objects.update_or_create(
                company_id=company,
                project_id=project,
                id_no=id_no,
                defaults={
                    "customer_name": stop["name"],
                    "contact_no": f"9600{route_idx:06d}",
                    "username": f"bp_gno_route_customer_{stop['suffix'].lower()}",
                    "password": make_password(DEFAULT_CUSTOMER_PASSWORD),
                    "password_crt_date": timezone.now(),
                    "building_no": stop["building"],
                    "street": stop["street"],
                    "area": stop["area"],
                    "ward": ward,
                    "zone": zone,
                    "city": city,
                    "district": district,
                    "state": state,
                    "country": country,
                    "panchayat_id": panchayat,
                    "pincode": stop["pincode"],
                    "latitude": f"{stop['latitude']:.6f}",
                    "longitude": f"{stop['longitude']:.6f}",
                    "sqft": "1200.00",
                    "water_consumption_lpd": "240.00",
                    "waste_collection_kg_per_day": "3.50",
                    "id_proof_type": CustomerCreation.IDProofType.AADHAAR,
                    "id_no": id_no,
                    "member_count": 4,
                    "family_members": [
                        {
                            "member_name": f"{stop['name']} Family {member_idx}",
                            "id_proof_type": CustomerCreation.IDProofType.AADHAAR,
                            "id_no": f"{id_no}-FM{member_idx}",
                        }
                        for member_idx in range(1, 5)
                    ],
                    "property_ref": property_obj,
                    "sub_property": sub_property,
                    "is_active": True,
                    "is_deleted": False,
                },
            )
            customer.waste_types.set(waste_types)
            customers.append(customer)

        trip_plan, _ = TripPlan.objects.update_or_create(
            company_id=company,
            project_id=project,
            staff_template_id=staff_template,
            vehicle_id=vehicle,
            panchayat_id=None,
            collection_type=TripPlan.COLLECTION_TYPE_HOUSEHOLD,
            defaults={
                "district_id": district,
                "city_id": city,
                "zone_id": zone,
                "supervisor_id": supervisor,
                "property_id": property_obj,
                "sub_property_id": sub_property,
                "waste_type_id": waste_types[0],
                "waste_type_ids": [waste_types[0].unique_id],
                "trip_trigger_weight_kg": 400,
                "max_vehicle_capacity_kg": 3000,
                "scheduled_time": "10:00",
                "is_auto_assign": True,
                "approval_status": TripPlan.ApprovalStatus.APPROVED,
                "status": TripPlan.Status.ACTIVE,
                "is_active": True,
                "is_deleted": False,
            },
        )
        trip_plan.wards.set([ward])

        existing = TripPlanCollectionPoint.objects.filter(trip_plan_id=trip_plan)
        if existing.exists():
            max_sequence = existing.aggregate(max_sequence=Max("sequence"))["max_sequence"] or 0
            existing.update(
                sequence=F("sequence") + max_sequence + len(customers) + 1000,
                is_deleted=True,
                is_active=False,
            )
        for idx, customer in enumerate(customers, start=1):
            TripPlanCollectionPoint.objects.update_or_create(
                trip_plan_id=trip_plan,
                customer_id=customer,
                defaults={
                    "company_id": company,
                    "project_id": project,
                    "collection_type": TripPlanCollectionPoint.COLLECTION_TYPE_HOUSEHOLD,
                    "sequence": idx,
                    "is_active": True,
                    "is_deleted": False,
                },
            )

        return trip_plan, customers

    @staticmethod
    def _point_in_polygon(lat, lon, coords):
        n = len(coords)
        inside = False
        j = n - 1
        for i in range(n):
            lat_i, lon_i = coords[i]["latitude"], coords[i]["longitude"]
            lat_j, lon_j = coords[j]["latitude"], coords[j]["longitude"]
            if (lon_i > lon) != (lon_j > lon):
                x = (lat_j - lat_i) * (lon - lon_i) / (lon_j - lon_i) + lat_i
                if lat < x:
                    inside = not inside
            j = i
        return inside

    @staticmethod
    def _polygon_centroid(coords):
        lats = [p["latitude"] for p in coords]
        lons = [p["longitude"] for p in coords]
        return sum(lats) / len(lats), sum(lons) / len(lons)

    def _finalize_ward_boundaries(self, wards, bins, customers, padding=0.0015):
        """Give every ward a boundary_coordinates polygon so the dashboard's
        ward-geofence overlay has something to draw.

        Prefers a real-world locality boundary from WARD_REAL_BOUNDARIES
        (hand-picked to correspond to genuine named areas within Greater
        Noida/Palakkad) when one is defined for this ward's name. Falls
        back to a bounding box around the ward's own bins/customers when
        no real boundary is on file.

        Either way, any bin/collection-point/customer belonging to the
        ward that ends up outside the chosen polygon is nudged to a point
        inside it (scattered around the polygon's centroid) — otherwise a
        real-world-shaped ward could easily exclude assets that were
        seeded independently around the ward's plain center point.
        """
        for ward in wards:
            real_boundary = self.WARD_REAL_BOUNDARIES.get(ward.ward_name)
            if real_boundary:
                ward.boundary_coordinates = real_boundary
                center_lat, center_lon = self._polygon_centroid(real_boundary)
                ward.latitude = round(center_lat, 6)
                ward.longitude = round(center_lon, 6)
                ward.save(update_fields=["boundary_coordinates", "latitude", "longitude"])
            else:
                points = [
                    (float(bin_obj.latitude), float(bin_obj.longitude))
                    for bin_obj in bins
                    if bin_obj.ward_id_id == ward.unique_id
                    and bin_obj.latitude is not None
                    and bin_obj.longitude is not None
                ]
                points += [
                    (float(customer.latitude), float(customer.longitude))
                    for customer in customers
                    if customer.ward_id == ward.unique_id
                    and customer.latitude
                    and customer.longitude
                ]
                if ward.latitude is not None and ward.longitude is not None:
                    points.append((float(ward.latitude), float(ward.longitude)))
                if not points:
                    continue

                lats = [p[0] for p in points]
                lons = [p[1] for p in points]
                min_lat, max_lat = min(lats) - padding, max(lats) + padding
                min_lon, max_lon = min(lons) - padding, max(lons) + padding

                ward.boundary_coordinates = [
                    {"latitude": max_lat, "longitude": min_lon},
                    {"latitude": max_lat, "longitude": max_lon},
                    {"latitude": min_lat, "longitude": max_lon},
                    {"latitude": min_lat, "longitude": min_lon},
                ]
                ward.save(update_fields=["boundary_coordinates"])
                continue

            # Nudge any out-of-boundary asset into the real polygon so
            # markers never render outside their own ward's geofence.
            coords = ward.boundary_coordinates
            nudge_idx = 0
            for bin_obj in bins:
                if bin_obj.ward_id_id != ward.unique_id or bin_obj.latitude is None:
                    continue
                lat, lon = float(bin_obj.latitude), float(bin_obj.longitude)
                if self._point_in_polygon(lat, lon, coords):
                    continue
                new_lat, new_lon = _scatter(center_lat, center_lon, nudge_idx, spread=0.003)
                nudge_idx += 1
                bin_obj.latitude = round(new_lat, 6)
                bin_obj.longitude = round(new_lon, 6)
                bin_obj.save(update_fields=["latitude", "longitude"])
                cp = bin_obj.collection_point_id
                if cp and not self._point_in_polygon(float(cp.latitude), float(cp.longitude), coords):
                    cp.latitude = bin_obj.latitude
                    cp.longitude = bin_obj.longitude
                    cp.save(update_fields=["latitude", "longitude"])

            for customer in customers:
                if customer.ward_id != ward.unique_id or not customer.latitude:
                    continue
                lat, lon = float(customer.latitude), float(customer.longitude)
                if self._point_in_polygon(lat, lon, coords):
                    continue
                new_lat, new_lon = _scatter(center_lat, center_lon, nudge_idx + 50, spread=0.003)
                nudge_idx += 1
                customer.latitude = f"{new_lat:.6f}"
                customer.longitude = f"{new_lon:.6f}"
                customer.save(update_fields=["latitude", "longitude"])

    def run(self):
        company, company_created = Company.objects.update_or_create(
            name=self.COMPANY_NAME,
            defaults={
                "description": "Blue Planet waste management operations",
                "is_active": True,
                "is_deleted": False,
            },
        )

        project_defaults = {
            "Blue Planet Integrated Waste Management": {
                "description": "Blue Planet Greater Noida operations",
                "gps_api_url": self.GPS_API_URL,
                "gps_vehicle_tracking_api": self.GPS_VEHICLE_TRACKING_API,
                "gps_user_id": "BLUEPLANET",
                "gps_group_name": "BLUEPLANET:VAM",
                "gps_provider_name": "BLUEPLANET",
                "gps_fcode": "VAM",
                "gps_trip_user_id": "NMCP2DISPOSAL",
                "weighment_api_url": self.WEIGHMENT_API_URL,
                "attendance_api_url": self.ATTENDANCE_API_URL,
                "attendance_api_key": self.ATTENDANCE_API_KEY,
                "is_active": True,
                "is_deleted": False,
            },
            "Palakkad BP": {
                "description": "Blue Planet Palakkad operations",
                "is_active": True,
                "is_deleted": False,
            },
        }

        created = 0
        updated = 0
        for name, defaults in project_defaults.items():
            project, was_created = Project.objects.update_or_create(
                company_id=company,
                name=name,
                defaults=defaults,
            )
            created += int(was_created)
            updated += int(not was_created)
            self._create_project_operational_data(
                company,
                project,
                self.PROJECT_LOCATION[name],
            )

        company_action = "Created" if company_created else "Updated"
        self.log(
            f"{company_action} Blue Planet | Projects created: {created}, updated: {updated} | operational data synced"
        )
