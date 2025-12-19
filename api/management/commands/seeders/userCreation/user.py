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
        try:
            admin_role = StaffUserType.objects.get(
                name="admin",
                usertype_id=staff_type
            )
            operator_role = StaffUserType.objects.get(
                name="operator",
                usertype_id=staff_type
            )
        except StaffUserType.DoesNotExist:
            raise Exception("❌ Staff roles missing. Run StaffUserTypeSeeder first.")

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
        # STAFF
        # --------------------------------------------------
        admin_staff = StaffOfficeDetails.objects.get(employee_name="Sathya")
        operator_staff = StaffOfficeDetails.objects.get(employee_name="Aakash")

        # --------------------------------------------------
        # USERS (AUTO unique_id, SAFE SEED)
        # --------------------------------------------------
        users = [
            {
                "staffusertype_id": admin_role,
                "staff_id": admin_staff,
                "password": "admin@123",
            },
            {
                "staffusertype_id": operator_role,
                "staff_id": operator_staff,
                "password": "operator@123",
            },
        ]

        for data in users:
            User.objects.get_or_create(
                staff_id=data["staff_id"],   # 🔑 ONE USER PER STAFF
                defaults={
                    "user_type": staff_type,
                    "staffusertype_id": data["staffusertype_id"],
                    "customer_id": None,
                    "password": data["password"],   # ⚠ plain text (as requested)
                    "district_id": district,
                    "city_id": city,
                    "zone_id": zone,
                    "ward_id": ward,
                    "is_active": True,
                    "is_deleted": False,
                }
            )

        print("✅ Staff users seeded safely (no duplicates)")
