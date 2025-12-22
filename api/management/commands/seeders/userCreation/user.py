from api.apps.userCreation import User
from api.apps.userType import UserType
from api.apps.staffUserType import StaffUserType
from api.apps.staffcreation import StaffOfficeDetails
from api.apps.district import District
from api.apps.city import City
from api.apps.zone import Zone
from api.apps.ward import Ward


class UserSeeder:
    group = "user-creation"

    def run(self):
        print("Seeding Users...")

        # --------------------------------------------------
        # USER TYPE (ONLY STAFF)
        # --------------------------------------------------
        try:
            staff_type = UserType.objects.get(name__iexact="staff")
        except UserType.DoesNotExist:
            raise Exception("❌ UserType 'staff' missing. Run UserTypeSeeder first.")

        # --------------------------------------------------
        # STAFF ROLES
        # --------------------------------------------------
        def get_role(role_name):
            try:
                return StaffUserType.objects.get(
                    name=role_name,
                    usertype_id=staff_type
                )
            except StaffUserType.DoesNotExist:
                raise Exception(f"❌ Staff role '{role_name}' missing. Run StaffUserTypeSeeder first.")

        roles = {
            "admin": get_role("admin"),
            "driver": get_role("driver"),
            "operator": get_role("operator"),
        }

        # --------------------------------------------------
        # LOCATION
        # --------------------------------------------------
        district = District.objects.first()
        city = City.objects.first()
        zone = Zone.objects.first()
        ward = Ward.objects.first()

        if not all([district, city, zone, ward]):
            raise Exception("❌ Location masters missing. Run masters seeder first.")

        # --------------------------------------------------
        # STAFF USERS
        # --------------------------------------------------
        staff_records = [
            ("Sathya", "admin", "admin@123"),
            ("Gokul", "driver", "7890"),
            ("Rahul", "operator", "7890"),
        ]

        for employee_name, role_key, password in staff_records:
            staff = StaffOfficeDetails.objects.get(employee_name=employee_name)

            User.objects.get_or_create(
                staff_id=staff,  # 🔑 one user per staff
                defaults={
                    "user_type": staff_type,
                    "staffusertype_id": roles[role_key],
                    "customer_id": None,
                    "password": password,  # ⚠ plain text (as requested)
                    "district_id": district,
                    "city_id": city,
                    "zone_id": zone,
                    "ward_id": ward,
                    "is_active": True,
                    "is_deleted": False,
                }
            )

        print("✅ Admin, Driver, and Operator staff users seeded successfully")
