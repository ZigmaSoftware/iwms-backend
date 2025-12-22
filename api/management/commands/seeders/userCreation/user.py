from api.apps.userCreation import User
from api.apps.userType import UserType
from api.apps.staffUserType import StaffUserType
from api.apps.staffcreation import StaffOfficeDetails
from api.apps.customercreation import CustomerCreation

from django.db.models import Q

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

        User.objects.update_or_create(
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
        # STAFF USERS (DRIVER + OPERATOR)
        # ==================================================
        try:
            driver_role = StaffUserType.objects.get(
                name="driver",
                usertype_id=staff_type
            )
        except StaffUserType.DoesNotExist:
            raise Exception("Staff driver role missing. Run StaffUserTypeSeeder first.")

        try:
            operator_role = StaffUserType.objects.get(
                name="operator",
                usertype_id=staff_type
            )
        except StaffUserType.DoesNotExist:
            raise Exception("Staff operator role missing. Run StaffUserTypeSeeder first.")

        role_seed_config = [
            ("driver", driver_role, "driver@123", ["Gokul"], "7890"),
            ("operator", operator_role, "operator@123", ["Rahul"], "7890"),
        ]

        for role_name, role_obj, default_password, special_names, special_password in role_seed_config:
            name_filter = Q()
            for name in special_names:
                name_filter |= Q(employee_name__iexact=name)

            special_staff = StaffOfficeDetails.objects.filter(
                active_status=True
            ).filter(name_filter)

            for staff_member in special_staff:
                User.objects.update_or_create(
                    staff_id=staff_member,
                    defaults={
                        "user_type": staff_type,
                        "staffusertype_id": role_obj,
                        "customer_id": None,
                        "password": special_password,
                        "district_id": district,
                        "city_id": city,
                        "zone_id": zone,
                        "ward_id": ward,
                        "is_active": True,
                        "is_deleted": False,
                    }
                )

            staff_members = StaffOfficeDetails.objects.filter(
                designation__iexact=role_name,
                active_status=True
            ).exclude(name_filter)

            if not staff_members.exists():
                print(f"No active staff with designation '{role_name}' found.")
                continue

            for staff_member in staff_members:
                existing_user = User.objects.filter(staff_id=staff_member).first()

                if existing_user is None:
                    User.objects.create(
                        staff_id=staff_member,
                        user_type=staff_type,
                        staffusertype_id=role_obj,
                        customer_id=None,
                        password=default_password,
                        district_id=district,
                        city_id=city,
                        zone_id=zone,
                        ward_id=ward,
                        is_active=True,
                        is_deleted=False,
                    )
                    continue

                updates = {}
                if existing_user.user_type_id != staff_type.unique_id:
                    updates["user_type"] = staff_type
                if existing_user.staffusertype_id_id != role_obj.unique_id:
                    updates["staffusertype_id"] = role_obj
                if existing_user.customer_id_id is not None:
                    updates["customer_id"] = None
                if not existing_user.password:
                    updates["password"] = default_password
                if existing_user.district_id_id is None:
                    updates["district_id"] = district
                if existing_user.city_id_id is None:
                    updates["city_id"] = city
                if existing_user.zone_id_id is None:
                    updates["zone_id"] = zone
                if existing_user.ward_id_id is None:
                    updates["ward_id"] = ward
                if not existing_user.is_active:
                    updates["is_active"] = True
                if existing_user.is_deleted:
                    updates["is_deleted"] = False

                if updates:
                    User.objects.filter(pk=existing_user.pk).update(**updates)

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
