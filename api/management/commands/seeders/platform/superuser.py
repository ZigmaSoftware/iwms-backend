from django.contrib.auth import get_user_model
from django.db import transaction
from api.management.commands.seeders.base import BaseSeeder


class PlatformSuperUserSeeder(BaseSeeder):
    name = "platform_superuser"

    @transaction.atomic
    def run(self):
        UserModel = get_user_model()
        username = "super_admin"
        password = "admin@123"

        user = UserModel.objects.filter(username=username).first()
        if user:
            user.is_superuser = True
            user.is_staff = True
            user.is_active = True
            user.is_deleted = False
            user.company_id = None
            user.project_id = None
            user.user_type_id = None
            user.staffusertype_id = None
            user.staff_id = None
            user.customer_id = None
            user.set_password(password)
            user.save()
            self.log(f"Updated platform superuser: {username}")
            return

        user = UserModel.objects.create_superuser(
            username=username,
            password=password,
        )
        self.log(f"Created platform superuser: {username}")
