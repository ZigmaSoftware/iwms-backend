from api.apps.userType import UserType
from api.apps.staffUserType import StaffUserType
from api.apps.staffcreation import StaffOfficeDetails
from api.apps.customercreation import CustomerCreation
from api.apps.company import Company

from django.db.models import Q

from api.apps.district import District
from api.apps.city import City
from api.apps.zone import Zone
from api.apps.ward import Ward


class UserSeeder:
    """
    Updated seeder that populates auth fields directly in StaffOfficeDetails and CustomerCreation.
    The separate User model is no longer used.
    """
    group = "user-creation"

    def run(self):
        print("Seeding Users (Staff & Customer auth fields)...")

        # --------------------------------------------------
        # COMMON LOCATION (fallback)
        # --------------------------------------------------
        district = District.objects.first()
        city = City.objects.first()
        zone = Zone.objects.first()
        ward = Ward.objects.first()

        if not all([district, city, zone, ward]):
            raise Exception("Location masters missing. Run masters seeder first.")

        # --------------------------------------------------
        # TENANCY (company is required for non-superusers)
        # --------------------------------------------------
        company = Company.objects.filter(is_deleted=False).order_by("name").first()
        if not company:
            company, _ = Company.objects.update_or_create(
                unique_id="COMP-SEED",
                defaults={
                    "name": "Seed Company",
                    "description": "Auto-created by seed command",
                    "is_active": True,
                    "is_deleted": False,
                },
            )

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

        admin_staff = StaffOfficeDetails.objects.filter(employee_name="Sathya").first()
        if not admin_staff:
            print("Admin staff 'Sathya' not found. Skipping admin user seeding.")
        else:
            # Update admin staff with auth fields directly
            admin_staff.user_type_id = staff_type
            admin_staff.staffusertype_id = admin_role
            admin_staff.password = "admin@123"
            admin_staff.is_active = True
            admin_staff.is_deleted = False
            admin_staff.save()
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

        try:
            supervisor_role = StaffUserType.objects.get(
                name="supervisor",
                usertype_id=staff_type
            )
        except StaffUserType.DoesNotExist:
            raise Exception("Staff supervisor role missing. Run StaffUserTypeSeeder first.")

        def seed_staff_role(role_name, role_obj, default_password, special_names, special_password):
            # Handle special named staff first
            name_filter = Q()
            for name in special_names:
                name_filter |= Q(employee_name__iexact=name)

            special_staff = StaffOfficeDetails.objects.filter(
                active_status=True
            ).filter(name_filter)

            for staff_member in special_staff:
                staff_member.user_type_id = staff_type
                staff_member.staffusertype_id = role_obj
                staff_member.password = special_password
                staff_member.is_active = True
                staff_member.is_deleted = False
                staff_member.save()
                print(f"Special {role_name} user seeded: {staff_member.employee_name}")

            # Handle regular staff by designation
            staff_members = StaffOfficeDetails.objects.filter(
                designation__iexact=role_name,
                active_status=True
            ).exclude(name_filter)

            if not staff_members.exists():
                print(f"No active staff with designation '{role_name}' found.")
                return

            for staff_member in staff_members:
                staff_member.user_type_id = staff_type
                staff_member.staffusertype_id = role_obj
                staff_member.password = default_password
                staff_member.is_active = True
                staff_member.is_deleted = False
                staff_member.save()

            print(f"{role_name} users seeded successfully")

        driver_default_password = "driver@123"
        driver_special_names = ["Gokul"]
        driver_special_password = "7890"
        seed_staff_role(
            "driver",
            driver_role,
            driver_default_password,
            driver_special_names,
            driver_special_password,
        )

        operator_default_password = "operator@123"
        operator_special_names = ["Rahul"]
        operator_special_password = "1234"
        seed_staff_role(
            "operator",
            operator_role,
            operator_default_password,
            operator_special_names,
            operator_special_password,
        )

        supervisor_default_password = "supervisor@123"
        supervisor_special_names = ["Anita", "Kumar", "Priya"]
        supervisor_special_password = "supervisor@123"
        seed_staff_role(
            "supervisor",
            supervisor_role,
            supervisor_default_password,
            supervisor_special_names,
            supervisor_special_password,
        )

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
            customer.user_type_id = customer_type
            customer.staffusertype_id = None
            customer.password = "customer@123"
            customer.is_active = True
            customer.is_deleted = False
            customer.save()
            print(f"Customer user seeded: {customer.customer_name}")

        print("Customer users seeded successfully")
