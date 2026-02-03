"""
Seeder for creating a platform super admin user in StaffOfficeDetails.
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.hashers import make_password
from api.apps.staffcreation import StaffOfficeDetails


class Command(BaseCommand):
    help = 'Creates or updates the platform super admin user in StaffOfficeDetails'

    def add_arguments(self, parser):
        parser.add_argument('--username', type=str, default='admin', help='Username for super admin')
        parser.add_argument('--password', type=str, default='admin123', help='Password for super admin')
        parser.add_argument('--name', type=str, default='Platform Admin', help='Employee name')

    def handle(self, *args, **options):
        username = options['username']
        password = options['password']
        name = options['name']

        # Check if platform super admin already exists
        existing = StaffOfficeDetails.objects.filter(
            username__iexact=username,
            is_superuser=True
        ).first()

        if existing:
            # Update password
            existing.password = make_password(password)
            existing.is_active = True
            existing.is_deleted = False
            existing.save()
            self.stdout.write(
                self.style.SUCCESS(f'Updated platform super admin: {username}')
            )
        else:
            # Create new platform super admin
            # Note: company_id is None for platform super admin
            staff = StaffOfficeDetails.objects.create(
                employee_name=name,
                username=username,
                password=make_password(password),
                is_staff=True,
                is_active=True,
                is_deleted=False,
                is_superuser=True,
                # company_id=None (explicitly not set for platform admin)
            )
            self.stdout.write(
                self.style.SUCCESS(f'Created platform super admin: {username}')
            )

        self.stdout.write(self.style.WARNING(
            f'Platform admin can now login at /api/platform/auth/login/ '
            f'with username: {username}, password: {password}'
        ))
