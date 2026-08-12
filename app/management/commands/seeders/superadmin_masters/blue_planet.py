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
from app.models.masters.hierarchy import AdministrativeHierarchy
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
    WEIGHMENT_API_URL = (
        "https://zigma.in/d2d/folders/waste_collected_summary_report/"
        "waste_collected_data_api.php"
    )

    PROJECT_LOCATION = {
        "Greater Noida BP": {
            "state": "Uttar Pradesh",
            "district": "Greater Noida BP District",
            "city": "Greater Noida BP City",
            "prefix": "GNO",
            "base_lat": 28.474400,
            "base_lon": 77.504000,
        },
        "Palakkad BP": {
            "state": "Kerala",
            "district": "Palakkad BP District",
            "city": "Palakkad BP City",
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
        "Greater Noida BP": [
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

    def _administrative_hierarchy(self):
        zone_hierarchy, _ = AdministrativeHierarchy.objects.get_or_create(
            level_name="Zone"
        )
        ward_hierarchy, _ = AdministrativeHierarchy.objects.get_or_create(
            level_name="Ward"
        )
        panchayat_hierarchy, _ = AdministrativeHierarchy.objects.get_or_create(
            level_name="Panchayat"
        )
        return zone_hierarchy, ward_hierarchy, panchayat_hierarchy

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

    def _create_staff(self, company, project, district, city, zones, wards, prefix):
        staff_type, driver_role = self._staff_role("Company Driver")
        _, operator_role = self._staff_role("Company Operator")
        _, supervisor_role = self._staff_role("Company Supervisor")

        staff_defs = [
            ("Driver1", driver_role),
            ("Driver2", driver_role),
            ("Operator1", operator_role),
            ("Operator2", operator_role),
            ("Supervisor", supervisor_role),
        ]
        staff = {}
        for label, role in staff_defs:
            username = f"bp_{prefix.lower()}_{label.lower()}"
            employee_name = f"BP {prefix} {label}"
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
            staff[label.lower()] = obj
        return staff

    def _create_vehicles(self, company, project, prefix):
        fuel, _ = Fuel.objects.get_or_create(
            fuel_type="Diesel",
            defaults={"description": "Diesel fuel", "is_active": True, "is_deleted": False},
        )
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
        for name in ("Organic Waste", "Wet Waste", "Dry Waste"):
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
        zone_hierarchy, ward_hierarchy, panchayat_hierarchy = (
            self._administrative_hierarchy()
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
                    "hierarchy_id": zone_hierarchy,
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
                    "hierarchy_id": ward_hierarchy,
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
                    "hierarchy_id": panchayat_hierarchy,
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
            "Greater Noida BP": {
                "description": "Blue Planet Greater Noida operations",
                "gps_api_url": self.GPS_API_URL,
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
