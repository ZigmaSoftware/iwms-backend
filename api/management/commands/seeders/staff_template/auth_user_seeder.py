from django.contrib.auth import get_user_model

from api.management.commands.seeders.base import BaseSeeder


class AuthUserSeeder(BaseSeeder):
    name = "auth_user"

    def run(self):
        """
        Ensure at least three auth users exist for alternative staff template links.
        """
        User = get_user_model()

        seed_users = [
            ("driver_user", "driver@demo.local", "driver123"),
            ("operator_user", "operator@demo.local", "operator123"),
            ("approver_user", "approver@demo.local", "approver123"),
        ]

        for username, email, password in seed_users:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    "email": email,
                    "is_active": True,
                },
            )
            if created:
                user.set_password(password)
                # Mark basic flags; adjust if custom user model differs.
                if hasattr(user, "is_staff"):
                    user.is_staff = False
                user.save()

        self.log("Auth users seeded (driver/operator/approver).")
