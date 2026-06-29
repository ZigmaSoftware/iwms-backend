from app.management.commands.seeders.base import BaseSeeder
from django.db.models import F, Max
from app.models.common_masters.continent import Continent
from app.models.common_masters.country import Country
from app.models.common_masters.state import State
from app.models.masters.areatype import AreaType
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
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project
from app.models.transport_masters.fuel import Fuel
from app.models.transport_masters.vehicleCreation import VehicleCreation
from app.models.transport_masters.vehicleTypeCreation import VehicleTypeCreation
from app.models.user_creations.staffcreation import Staffcreation
from app.models.user_creations.waste_collection_bluetooth import WasteType
from app.models.waste_types.property import Property
from app.models.waste_types.subproperty import SubProperty


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
        "Noida BP": {
            "state": "Uttar Pradesh",
            "district": "Noida BP District",
            "city": "Noida BP City",
            "prefix": "NOI",
            "base_lat": 28.535500,
            "base_lon": 77.391000,
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

    def _area_hierarchy(self, state, district, city):
        urban, _ = AreaType.objects.get_or_create(
            name="Urban",
            defaults={
                "state_id": state,
                "district_id": district,
                "city_id": city,
                "description": "Urban area",
                "is_active": True,
                "is_deleted": False,
            },
        )
        rural, _ = AreaType.objects.get_or_create(
            name="Rural",
            defaults={
                "state_id": state,
                "district_id": district,
                "city_id": city,
                "description": "Rural area",
                "is_active": True,
                "is_deleted": False,
            },
        )
        zone_hierarchy, _ = AdministrativeHierarchy.objects.get_or_create(area_type=urban, level_name="Zone")
        ward_hierarchy, _ = AdministrativeHierarchy.objects.get_or_create(area_type=urban, level_name="Ward")
        panchayat_hierarchy, _ = AdministrativeHierarchy.objects.get_or_create(area_type=rural, level_name="Panchayat")
        return urban, rural, zone_hierarchy, ward_hierarchy, panchayat_hierarchy

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

    def _create_staff(self, company, project, district, city, zone, ward, prefix):
        staff_type, driver_role = self._staff_role("Company Driver")
        _, operator_role = self._staff_role("Company Operator")
        _, supervisor_role = self._staff_role("Company Supervisor")

        staff_defs = [
            ("Driver", driver_role),
            ("Operator", operator_role),
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
                "zone_id": zone,
                "ward_id": ward,
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

    def _create_vehicle(self, company, project, prefix):
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
        vehicle, _ = VehicleCreation.objects.update_or_create(
            vehicle_no=f"BP-{prefix}-VEH-01",
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
        return vehicle

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
        return prop, sub_property

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
        urban, rural, zone_hierarchy, ward_hierarchy, panchayat_hierarchy = self._area_hierarchy(state, district, city)

        zone, _ = Zone.objects.update_or_create(
            zone_name=f"{prefix} Zone 1",
            city_id=city,
            company_id=company,
            project_id=project,
            defaults={
                "state_id": state,
                "district_id": district,
                "area_type_id": urban,
                "hierarchy_id": zone_hierarchy,
                "latitude": config["base_lat"],
                "longitude": config["base_lon"],
                "is_active": True,
                "is_deleted": False,
            },
        )
        ward, _ = Ward.objects.update_or_create(
            ward_name=f"{prefix} Ward 1",
            zone_id=zone,
            company_id=company,
            project_id=project,
            defaults={
                "state_id": state,
                "district_id": district,
                "city_id": city,
                "area_type_id": urban,
                "hierarchy_id": ward_hierarchy,
                "latitude": config["base_lat"] + 0.001,
                "longitude": config["base_lon"] + 0.001,
                "is_active": True,
                "is_deleted": False,
            },
        )
        panchayat, _ = Panchayat.objects.update_or_create(
            panchayat_name=f"{prefix} PLB 1",
            company_id=company,
            project_id=project,
            defaults={
                "state_id": state,
                "district_id": district,
                "city_id": city,
                "area_type_id": rural,
                "hierarchy_id": panchayat_hierarchy,
                "agreed_weight_kg": 800,
                "weight_unit": "kg",
                "latitude": config["base_lat"] + 0.002,
                "longitude": config["base_lon"] + 0.002,
                "is_active": True,
                "is_deleted": False,
            },
        )

        prop, sub_property = self._create_property_data(company, project)
        waste_types = self._create_waste_types(company, project)
        staff = self._create_staff(company, project, district, city, zone, ward, prefix)
        vehicle = self._create_vehicle(company, project, prefix)

        staff_template, _ = StaffTemplate.objects.update_or_create(
            driver_id=staff["driver"],
            operator_id=staff["operator"],
            defaults={
                "company_id": company,
                "project_id": project,
                "extra_operator_id": [],
                "approved_by": staff["supervisor"],
                "status": StaffTemplate.Status.ACTIVE,
                "approval_status": StaffTemplate.ApprovalStatus.APPROVED,
                "is_active": True,
                "is_deleted": False,
            },
        )

        collection_point, _ = Collection_point.objects.update_or_create(
            cp_name=f"CP-{prefix}-01",
            panchayat_id=panchayat,
            company_id=company,
            project_id=project,
            defaults={
                "state_id": state,
                "district_id": district,
                "city_id": city,
                "collection_type": Collection_point.COLLECTION_TYPE_BIN,
                "latitude": config["base_lat"] + 0.003,
                "longitude": config["base_lon"] + 0.003,
                "is_active": True,
                "is_deleted": False,
            },
        )
        collection_point.wards.clear()

        bins = []
        for waste_type in waste_types:
            qr = f"QR-BP-{prefix}-{waste_type.waste_type_name.upper().replace(' ', '-')}"
            bin_obj, _ = Bins.objects.update_or_create(
                bin_qr=qr,
                defaults={
                    "company_id": company,
                    "project_id": project,
                    "collection_point_id": collection_point,
                    "wastetype_id": waste_type,
                    "bin_name": f"{collection_point.cp_name} {waste_type.waste_type_name}",
                    "bin_capacity": 240,
                    "bin_type": BinType.MEDIUM,
                    "bin_image": "default.png",
                    "is_active": True,
                    "is_deleted": False,
                },
            )
            bins.append(bin_obj)

        trip_plan, _ = TripPlan.objects.update_or_create(
            company_id=company,
            project_id=project,
            staff_template_id=staff_template,
            vehicle_id=vehicle,
            panchayat_id=panchayat,
            defaults={
                "district_id": district,
                "city_id": city,
                "zone_id": None,
                "supervisor_id": staff["supervisor"],
                "property_id": prop,
                "sub_property_id": sub_property,
                "waste_type_id": waste_types[0],
                "waste_type_ids": [waste_type.unique_id for waste_type in waste_types],
                "trip_trigger_weight_kg": 800,
                "max_vehicle_capacity_kg": 3000,
                "scheduled_time": "13:00",
                "approval_status": TripPlan.ApprovalStatus.APPROVED,
                "status": TripPlan.Status.ACTIVE,
                "is_active": True,
                "is_deleted": False,
            },
        )
        trip_plan.wards.clear()

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
                collection_point_id=collection_point,
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

        return {
            "district": district,
            "city": city,
            "panchayat": panchayat,
            "collection_point": collection_point,
            "bins": bins,
            "trip_plan": trip_plan,
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
            "Noida BP": {
                "description": "Blue Planet Noida operations",
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
