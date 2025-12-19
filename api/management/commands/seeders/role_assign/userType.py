# seeders/role_assign/usertype.py

from api.management.commands.seeders.base import BaseSeeder
from api.apps.userType import UserType


class UserTypeSeeder(BaseSeeder):
    name = "user_type"

    def run(self):
        allowed_types = ["Staff", "Customer"]

        # -------------------------------------------------
        # Create / ensure only required user types exist
        # -------------------------------------------------
        for name in allowed_types:
            UserType.objects.get_or_create(
                name=name,
                defaults={
                    "is_active": True,
                    "is_deleted": False,
                }
            )

        self.log("User types seeded (Staff, Customer)")
