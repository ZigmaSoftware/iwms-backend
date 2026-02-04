# seeders/role_assign/staff_usertype.py

from api.management.commands.seeders.base import BaseSeeder
from api.models.users.userType import UserType
from api.models.users.staffUserType import StaffUserType


class StaffUserTypeSeeder(BaseSeeder):
    name = "staff_user_type"

    def run(self):
        role_map = {
            "staff": ["admin", "driver", "operator", "supervisor"],
            "platform": ["superadmin"],
        }

        for user_type_name, roles in role_map.items():
            user_type = UserType.objects.filter(name__iexact=user_type_name).first()
            if not user_type:
                self.log_error(
                    f"UserType '{user_type_name}' not found. Run UserTypeSeeder first."
                )
                continue

            for role_name in roles:
                StaffUserType.objects.get_or_create(
                    usertype_id=user_type,
                    name=role_name,
                    defaults={
                        "is_active": True,
                        "is_deleted": False,
                    }
                )

        self.log("Staff user types seeded for staff and platform roles")
