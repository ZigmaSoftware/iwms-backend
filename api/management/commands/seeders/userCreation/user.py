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
        # USER TYPES
        # --------------------------------------------------
        admin_type, _ = UserType.objects.get_or_create(
            name="Admin",
            defaults={"is_active": True}
        )

        operator_type, _ = UserType.objects.get_or_create(
            name="Operator",
            defaults={"is_active": True}
        )

        # --------------------------------------------------
        # STAFF USER TYPES
        # --------------------------------------------------
        admin_role, _ = StaffUserType.objects.get_or_create(
            usertype_id=admin_type,
            name="admin",
            defaults={"is_active": True}
        )

        operator_role, _ = StaffUserType.objects.get_or_create(
            usertype_id=operator_type,
            name="operator",
            defaults={"is_active": True}
        )

        # --------------------------------------------------
        # LOCATION
        # --------------------------------------------------
        district = District.objects.first()
        city = City.objects.first()
        zone = Zone.objects.first()
        ward = Ward.objects.first()

        if not all([district, city, zone, ward]):
            raise Exception("Location masters missing. Run masters seeder first.")

        # --------------------------------------------------
        # STAFF
        # --------------------------------------------------
        admin_staff = StaffOfficeDetails.objects.get(employee_name="Admin User")
        operator_staff = StaffOfficeDetails.objects.get(employee_name="Operator User")

        # --------------------------------------------------
        # USERS (PLAIN PASSWORD)
        # --------------------------------------------------
        users = [
            {
                "unique_id": "ADMIN001",
                "user_type": admin_type,
                "staffusertype_id": admin_role,
                "staff_id": admin_staff,
                "password": "admin@123",
            },
            {
                "unique_id": "OPERATOR001",
                "user_type": operator_type,
                "staffusertype_id": operator_role,
                "staff_id": operator_staff,
                "password": "operator@123",
            },
        ]

        for data in users:
            User.objects.get_or_create(
                unique_id=data["unique_id"],
                defaults={
                    "user_type": data["user_type"],
                    "staffusertype_id": data["staffusertype_id"],
                    "staff_id": data["staff_id"],
                    "password": data["password"],  # 👈 NO HASH
                    "district_id": district,
                    "city_id": city,
                    "zone_id": zone,
                    "ward_id": ward,
                    "is_active": True,
                }
            )

        print("✅ Users seeded (plain passwords)")
