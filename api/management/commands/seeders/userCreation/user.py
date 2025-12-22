from api.apps.userCreation import User
from api.apps.userType import UserType
from api.apps.staffUserType import StaffUserType
from api.apps.staffcreation import StaffOfficeDetails
from api.apps.customercreation import CustomerCreation

from api.apps.district import District
from api.apps.city import City
from api.apps.zone import Zone
from api.apps.ward import Ward


class UserSeeder:
    group = "user-creation"

    def run(self):
        print("Seeding Users...")

        # --------------------------------------------------
        # COMMON LOCATION (fallback)
        # --------------------------------------------------
        district = District.objects.first()
        city = City.objects.first()
        zone = Zone.objects.first()
        ward = Ward.objects.first()

        if not all([district, city, zone, ward]):
            raise Exception("Location masters missing. Run masters seeder first.")

        # ==================================================
        # STAFF USER (ADMIN)
        # ==================================================
        try:
            staff_type = UserType.objects.get(name__iexact="staff")
        except UserType.DoesNotExist:
            raise Exception("UserType 'staff' missing. Run UserTypeSeeder first.")

        try:
            admin_role = StaffUserType.objects.get(
                name="admin",
                usertype_id=staff_type
            )
        except StaffUserType.DoesNotExist:
            raise Exception("Staff admin role missing. Run StaffUserTypeSeeder first.")

        admin_staff = StaffOfficeDetails.objects.get(employee_name="Sathya")

        User.objects.get_or_create(
            staff_id=admin_staff,
            defaults={
                "user_type": staff_type,
                "staffusertype_id": admin_role,
                "customer_id": None,
                "password": "admin@123",
                "district_id": district,
                "city_id": city,
                "zone_id": zone,
                "ward_id": ward,
                "is_active": True,
                "is_deleted": False,
            }
        )

        print("Admin staff user seeded successfully")

        # ==================================================
        # CUSTOMER USERS (DYNAMIC)
        # ==================================================
        try:
            customer_type = UserType.objects.get(name__iexact="customer")
        except UserType.DoesNotExist:
            print("UserType 'customer' not found. Skipping customer users.")
            return

        customers = CustomerCreation.objects.filter(is_deleted=False)

        if not customers.exists():
            print("No customers found. Skipping customer users.")
            return

        for customer in customers:
            User.objects.get_or_create(
                customer_id=customer,
                defaults={
                    "user_type": customer_type,
                    "staff_id": None,
                    "staffusertype_id": None,

                    "password": "customer@123",

                    "district_id": customer.district or district,
                    "city_id": customer.city or city,
                    "zone_id": customer.zone or zone,
                    "ward_id": customer.ward or ward,

                    "is_active": True,
                    "is_deleted": False,
                }
            )

            print(f"Customer user seeded: {customer.customer_name}")

        print("Customer users seeded successfully")
