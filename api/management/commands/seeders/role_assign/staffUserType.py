# seeders/role_assign/staff_usertype.py

from api.management.commands.seeders.base import BaseSeeder
from api.apps.userType import UserType
from api.apps.staffUserType import StaffUserType


class StaffUserTypeSeeder(BaseSeeder):
    name = "staff_user_type"

    def run(self):
        try:
            staff_usertype = UserType.objects.get(name__iexact="staff")
        except UserType.DoesNotExist:
            raise Exception("❌ UserType 'staff' not found. Run UserTypeSeeder first.")

        staff_roles = ["admin", "operator", "driver"]

        for role in staff_roles:
            StaffUserType.objects.get_or_create(
                usertype_id=staff_usertype,
                name=role,
                defaults={
                    "is_active": True,
                    "is_deleted": False,
                }
            )

        self.log("✅ Staff roles created only for staff usertype")
