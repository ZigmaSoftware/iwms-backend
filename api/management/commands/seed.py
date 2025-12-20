# from django.core.management.base import BaseCommand
# from django.db import connection, transaction
# from faker import Faker
# import random

# # -----------------------------------------
# #   IMPORT MODELS (MATCHING YOUR REAL FILES)
# # -----------------------------------------
# from api.apps.continent import Continent
# from api.apps.country import Country
# from api.apps.state import State
# from api.apps.district import District
# from api.apps.city import City
# from api.apps.zone import Zone
# from api.apps.ward import Ward

# from api.apps.userType import UserType
# from api.apps.userCreation import User      # adjust to actual filename


# from api.apps.userscreen import UserScreen


# from api.apps.property import Property
# from api.apps.subproperty import SubProperty

# from api.apps.fuel import Fuel
# from api.apps.vehicleTypeCreation import VehicleTypeCreation
# from api.apps.vehicleCreation import VehicleCreation

# from api.apps.customercreation import CustomerCreation
# from api.apps.complaints import Complaint
# from api.apps.feedback import FeedBack


# fake = Faker()


# # -----------------------------------------
# #  MySQL TRUNCATE SAFE FUNCTION
# # -----------------------------------------
# def truncate(model):
#     table = model._meta.db_table
#     with connection.cursor() as cursor:
#         cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")
#         cursor.execute(f"TRUNCATE TABLE `{table}`;")
#         cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")


# # -----------------------------------------
# #  MAIN SEEDER CLASS
# # -----------------------------------------
# class Command(BaseCommand):
#     help = "Seed full IWMS database (MySQL version, safe for PROTECT FKs)."

#     @transaction.atomic
#     def handle(self, *args, **kwargs):
#         self.stdout.write(self.style.WARNING("⚙ Resetting IWMS database…"))

#         self._truncate_all()
#         self._seed_geography()
#         # self._seed_usertypes_users()
#         # self._seed_screens()
#         self._seed_properties()
#         self._seed_vehicle_masters()
#         self._seed_vehicles()
#         # self._seed_customers()
#         self._seed_complaints()
#         self._seed_feedback()

#         self.stdout.write(self.style.SUCCESS("✔ Seeding completed successfully."))

#     # ----------------------------------------------------------------------
#     # TRUNCATE ALL TABLES IN SAFE FK ORDER
#     # ----------------------------------------------------------------------
#     def _truncate_all(self):
#         truncate(FeedBack)
#         truncate(Complaint)
#         # truncate(CustomerCreation)

#         truncate(VehicleCreation)
#         truncate(VehicleTypeCreation)
#         truncate(Fuel)

#         # truncate(UserPermission)
#         # truncate(UserScreen)
#         # truncate(MainUserScreen)
#         # truncate(User)
#         # truncate(UserType)

#         truncate(Ward)
#         truncate(Zone)
#         truncate(City)
#         truncate(District)
#         truncate(State)
#         truncate(Country)
#         truncate(Continent)

#         truncate(SubProperty)
#         truncate(Property)

#     # ----------------------------------------------------------------------
#     # GEOGRAPHY MASTER
#     # ----------------------------------------------------------------------
#     def _seed_geography(self):
#         asia = Continent.objects.create(name="Asia")

#         india = Country.objects.create(
#             continent=asia,
#             name="India",
#             currency="INR",
#             mob_code="+91"
#         )

#         tn = State.objects.create(country=india, name="Tamil Nadu")
#         ka = State.objects.create(country=india, name="Karnataka")

#         dist1 = District.objects.create(country=india, state=tn, name="Coimbatore")
#         dist2 = District.objects.create(country=india, state=ka, name="Bengaluru Urban")

#         city1 = City.objects.create(country=india, state=tn, district=dist1, name="Coimbatore")
#         city2 = City.objects.create(country=india, state=ka, district=dist2, name="Bengaluru")

#         zone_east = Zone.objects.create(
#             country=india, state=tn, district=dist1, city=city1, name="East Zone"
#         )
#         zone_west = Zone.objects.create(
#             country=india, state=tn, district=dist1, city=city1, name="West Zone"
#         )

#         Ward.objects.create(
#             country=india, state=tn, district=dist1, city=city1, zone=zone_east, name="Ward 23"
#         )
#         Ward.objects.create(
#             country=india, state=tn, district=dist1, city=city1, zone=zone_west, name="Ward 45"
#         )

#     # ----------------------------------------------------------------------
#     # USER TYPES + USERS
#     # ----------------------------------------------------------------------
#     # def _seed_usertypes_users(self):
#     #     admin = UserType.objects.create(name="Admin")
#     #     operator = UserType.objects.create(name="Operator")
#     #     citizen = UserType.objects.create(name="Citizen")

#     #     User.objects.create(
#     #         username="admin",
#     #         password="admin123",
#     #         first_name="System",
#     #         last_name="Admin",
#     #         user_type=admin,
#     #     )

#     #     for i in range(5):
#     #         User.objects.create(
#     #             username=f"operator{i}",
#     #             password="op123",
#     #             first_name=fake.first_name(),
#     #             last_name=fake.last_name(),
#     #             user_type=operator,
#     #         )

#     # # ----------------------------------------------------------------------
#     # # SCREENS + PERMISSIONS
#     # # ----------------------------------------------------------------------
#     # def _seed_screens(self):
#     #     dashboard = MainUserScreen.objects.create(mainscreen="Dashboard")
#     #     operations = MainUserScreen.objects.create(mainscreen="Operations")
#     #     reports = MainUserScreen.objects.create(mainscreen="Reports")

#     #     UserScreen.objects.create(mainscreen=dashboard, screen_name="Live Map")
#     #     UserScreen.objects.create(mainscreen=operations, screen_name="Grievance Management")
#     #     UserScreen.objects.create(mainscreen=operations, screen_name="Vehicle Tracking")
#     #     UserScreen.objects.create(mainscreen=reports, screen_name="Daily Metrics")

#     # ----------------------------------------------------------------------
#     # PROPERTY → SUBPROPERTY
#     # ----------------------------------------------------------------------
#     def _seed_properties(self):
#         house = Property.objects.create(property_name="Residential")
#         commercial = Property.objects.create(property_name="Commercial")

#         SubProperty.objects.create(property=house, sub_property_name="Individual House")
#         SubProperty.objects.create(property=house, sub_property_name="Apartment")
#         SubProperty.objects.create(property=commercial, sub_property_name="Retail Shop")

#     # ----------------------------------------------------------------------
#     # VEHICLE MASTER
#     # ----------------------------------------------------------------------
#     def _seed_vehicle_masters(self):
#         Fuel.objects.create(fuel_type="Diesel")
#         Fuel.objects.create(fuel_type="Petrol")

#         VehicleTypeCreation.objects.create(vehicleType="Compactor")
#         VehicleTypeCreation.objects.create(vehicleType="Dumper")
#         VehicleTypeCreation.objects.create(vehicleType="TATA ACE")

#     # ----------------------------------------------------------------------
#     # VEHICLES
#     # ----------------------------------------------------------------------
#     def _seed_vehicles(self):
#         state = State.objects.first()
#         dist = District.objects.first()
#         city = City.objects.first()
#         zone = Zone.objects.first()
#         ward = Ward.objects.first()

#         for i in range(12):
#             VehicleCreation.objects.create(
#                 vehicle_no=f"TN38AB{i:04d}",
#                 driver_name=fake.name(),
#                 state=state,
#                 district=dist,
#                 city=city,
#                 zone=zone,
#                 ward=ward,
#             )

#     # ----------------------------------------------------------------------
#     # CUSTOMERS
#     # ----------------------------------------------------------------------
#     # def _seed_customers(self):
#     #     india = Country.objects.first()
#     #     tn = State.objects.first()
#     #     dist = District.objects.first()
#     #     city = City.objects.first()
#     #     zones = list(Zone.objects.all())
#     #     wards = list(Ward.objects.all())

#     #     prop = Property.objects.first()
#     #     subprops = list(SubProperty.objects.filter(property=prop))

#     #     citizen_type = UserType.objects.get(name="Citizen")

#     #     for _ in range(15):
#     #         z = random.choice(zones)
#     #         w = random.choice(wards)

#     #         CustomerCreation.objects.create(
#     #             customer_name=fake.name(),
#     #             contact_no=fake.msisdn()[:10],
#     #             building_no=fake.building_number(),
#     #             street=fake.street_name(),
#     #             area=fake.city_suffix(),
#     #             id_proof_type="AADHAAR",
#     #             id_no="1234-5678-9012",
#     #             ward=w,
#     #             zone=z,
#     #             city=city,
#     #             district=dist,
#     #             state=tn,
#     #             country=india,
#     #             pincode="641001",
#     #             latitude=str(fake.latitude()),
#     #             longitude=str(fake.longitude()),
#     #             property=prop,
#     #             sub_property=random.choice(subprops),
#     #             user_type=citizen_type,
#     #         )

#     # ----------------------------------------------------------------------
#     # COMPLAINTS
#     # ----------------------------------------------------------------------
#     def _seed_complaints(self):
#         customers = list(CustomerCreation.objects.all())

#         for _ in range(10):
#             c = random.choice(customers)
#             Complaint.objects.create(
#                 customer=c,
#                 category="COLLECTION",
#                 details=fake.sentence(),
#             )

#     # ----------------------------------------------------------------------
#     # FEEDBACK
#     # ----------------------------------------------------------------------
#     def _seed_feedback(self):
#         customers = list(CustomerCreation.objects.all())

#         for _ in range(10):
#             FeedBack.objects.create(
#                 customer=random.choice(customers),
#                 category=random.choice(["Excellent", "Satisfied", "Not Satisfied"]),
#                 feedback_details=fake.sentence(),
#             )


# core/management/commands/seed.py
from django.conf import settings
from django.core.management.base import BaseCommand
from api.management.commands.seeders.masters import MASTER_SEEDERS
from api.management.commands.seeders.role_assign import ROLE_ASSIGN_SEEDERS
from api.management.commands.seeders.assets import ASSET_SEEDERS
from api.management.commands.seeders.customers import CUSTOMER_SEEDERS
from api.management.commands.seeders.userCreation import USER_CREATION_SEEDERS
from api.management.commands.seeders.permissions import PERMISSION_SEEDERS


SEED_GROUPS = {
    "masters": MASTER_SEEDERS,
    "role-assign": ROLE_ASSIGN_SEEDERS,
    "assets":ASSET_SEEDERS,
      "customers": CUSTOMER_SEEDERS,
      "user-creation": USER_CREATION_SEEDERS,
       "permission": PERMISSION_SEEDERS,
}

class Command(BaseCommand):
    help = "Run database seeders"

    def add_arguments(self, parser):
        parser.add_argument(
            "--group",
            type=str,
            help="Seeder group (masters, assets, users)"
        )

    def handle(self, *args, **options):

        if settings.ENVIRONMENT == "production":
            self.stdout.write(
                self.style.ERROR(" Seeding is disabled in PRODUCTION environment")
            )
            return

      
        if not settings.DEBUG:
            self.stdout.write(
                self.style.ERROR(" Seeding blocked because DEBUG=False")
            )
            return

        # ---------------------------------------
        # EXISTING LOGIC (UNCHANGED)
        # ---------------------------------------
        group = options.get("group")

        if group:
            seeders = SEED_GROUPS.get(group)
            if not seeders:
                self.stdout.write(self.style.ERROR("Invalid group"))
                return
        else:
            # Run ALL
            seeders = []
            for g in SEED_GROUPS.values():
                seeders.extend(g)

        for seeder_cls in seeders:
            seeder = seeder_cls()
            seeder.run()

        self.stdout.write(self.style.SUCCESS("✅ Seeding completed"))