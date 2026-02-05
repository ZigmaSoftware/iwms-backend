from django.contrib.auth import get_user_model
from django.db import transaction

from app.management.commands.seeders.base import BaseSeeder
from app.models.users.userType import UserType


class PlatformDeveloperSeeder(BaseSeeder):
    name = "platform_developer"

    @transaction.atomic
    def run(self):
        developer_type = UserType.objects.filter(name__iexact="developer").first()
        if not developer_type:
            self.log("UserType 'developer' missing. Run UserTypeSeeder first.")
            return

        UserModel = get_user_model()
        username = "platform_developer"
        password = "Dev@123"
        email = "developer@example.com"

        user, created = UserModel.objects.get_or_create(
            username=username,
            defaults={
                "email": email,
                "user_type_id": developer_type,
                "is_staff": True,
                "is_active": True,
                "is_deleted": False,
            },
        )

        user.user_type_id = developer_type
        user.is_staff = True
        user.is_active = True
        user.is_deleted = False
        user.company_id = None
        user.project_id = None
        user.staffusertype_id = None
        user.staff_id = None
        user.customer_id = None
        user.set_password(password)
        user.save()

        action = "Created" if created else "Updated"
        self.log(f"{action} platform developer: {username}")
