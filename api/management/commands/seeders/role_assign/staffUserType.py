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
            raise Exception("UserType 'staff' not found. Run UserTypeSeeder first.")

        StaffUserType.objects.get_or_create(
            usertype_id=staff_usertype,
            name="admin",
            defaults={
                "is_active": True,
                "is_deleted": False,
            }
        )
        StaffUserType.objects.get_or_create(
            usertype_id=staff_usertype,
            name="driver",
            defaults={
                "is_active": True,
                "is_deleted": False,
            }
        )
        StaffUserType.objects.get_or_create(
            usertype_id=staff_usertype,
            name="operator",
            defaults={
                "is_active": True,
                "is_deleted": False,
            }
        )
        StaffUserType.objects.get_or_create(
            usertype_id=staff_usertype,
            name="supervisor",
            defaults={
                "is_active": True,
                "is_deleted": False,
            }
        )

        self.log("Staff user types seeded for Staff")
