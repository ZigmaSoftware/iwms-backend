from api.management.commands.seeders.base import BaseSeeder
from api.apps.staffcreation import StaffOfficeDetails
from api.apps.staffUserType import StaffUserType
from api.apps.userType import UserType


class AuthUserSeeder(BaseSeeder):
    name = "auth_user"

    def run(self):
        """
        Ensure at least three staff users exist with auth fields for alternative staff template links.
        """
        # Get or create staff user type
        try:
            staff_type = UserType.objects.get(name__iexact="staff")
        except UserType.DoesNotExist:
            self.log("UserType 'staff' not found. Seeder aborted.")
            return

        # Ensure staff user types exist
        driver_role, _ = StaffUserType.objects.get_or_create(
            name="driver",
            usertype_id=staff_type,
            defaults={"display_name": "Driver"}
        )
        operator_role, _ = StaffUserType.objects.get_or_create(
            name="operator",
            usertype_id=staff_type,
            defaults={"display_name": "Operator"}
        )
        approver_role, _ = StaffUserType.objects.get_or_create(
            name="admin",
            usertype_id=staff_type,
            defaults={"display_name": "Admin"}
        )

        seed_staff = [
            ("driver_user", "driver@demo.local", "driver123", driver_role),
            ("operator_user", "operator@demo.local", "operator123", operator_role),
            ("approver_user", "approver@demo.local", "approver123", approver_role),
        ]

        for employee_name, email, password, role in seed_staff:
            staff, created = StaffOfficeDetails.objects.get_or_create(
                employee_name=employee_name,
                defaults={
                    "email": email,
                    "user_type_id": staff_type,
                    "staffusertype_id": role,
                    "password": password,
                    "is_active": True,
                    "is_deleted": False,
                },
            )
            if not created:
                # Update existing staff with auth fields
                staff.user_type_id = staff_type
                staff.staffusertype_id = role
                staff.password = password
                staff.is_active = True
                staff.is_deleted = False
                staff.save()

        self.log("Auth staff users seeded (driver/operator/approver).")
