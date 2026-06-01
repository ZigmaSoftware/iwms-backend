from django.conf import settings

from app.management.commands.seeders.base import BaseSeeder
from app.models.user_creations.staffcreation import Staffcreation
from app.models.role_assigns.staffUserType import StaffUserType
from app.models.role_assigns.userType import UserType
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project
from app.models.masters.district import District
from app.models.masters.city import City
from app.models.masters.zone import Zone
from app.models.masters.ward import Ward


class AuthUserSeeder(BaseSeeder):
    name = "auth_user"

    def run(self):
        if not getattr(settings, "ENABLE_AUTH_USER_SEEDING", True):
            self.log("Auth user seeding skipped (ENABLE_AUTH_USER_SEEDING=False).")
            return
        """
        Ensure operator/driver auth users exist for the operator-mobile flow.

        Seeds two driver-operator pairs so the seeder can create two staff
        templates (wet trip + dry trip) without colliding on uniqueness.
        Each Staffcreation row has username + password fields populated so the
        mobile login endpoint resolves them by username, employee_name or emp_id.
        """
        company = Company.objects.filter(is_deleted=False).first()
        project = None
        if company:
            project = Project.objects.filter(company_id=company, is_deleted=False).first()

        district = District.objects.filter(is_deleted=False).first()
        city = City.objects.filter(is_deleted=False).first()
        zone = Zone.objects.filter(is_deleted=False).first()
        ward = Ward.objects.filter(is_deleted=False).first()

        try:
            staff_type = UserType.objects.get(name__iexact="staff")
        except UserType.DoesNotExist:
            self.log("UserType 'staff' not found. Seeder aborted.")
            return

        driver_role, _ = StaffUserType.objects.get_or_create(
            name="Company Driver",
            usertype_id=staff_type,
            defaults={"display_name": "Driver"},
        )
        operator_role, _ = StaffUserType.objects.get_or_create(
            name="Company Operator",
            usertype_id=staff_type,
            defaults={"display_name": "Operator"},
        )
        approver_role, _ = StaffUserType.objects.get_or_create(
            name="Admin",
            usertype_id=staff_type,
        )

        seed_staff = [
            ("driver_user", "driver@demo.local", "driver123", driver_role),
            ("operator_user", "operator@demo.local", "operator123", operator_role),
            ("driver2_user", "driver2@demo.local", "driver123", driver_role),
            ("operator2_user", "operator2@demo.local", "operator123", operator_role),
            ("approver_user", "approver@demo.local", "approver123", approver_role),
        ]

        for username, email, password, role in seed_staff:
            defaults = {
                "employee_name": username,
                "username": username,
                "office_email": email,
                "user_type_id": staff_type,
                "staffusertype_id": role,
                "password": password,
                "company_id": company,
                "project_id": project,
                "district_id": district,
                "city_id": city,
                "zone_id": zone,
                "ward_id": ward,
                "is_active": True,
                "is_deleted": False,
            }

            staff = Staffcreation.objects.filter(username=username).first()
            if not staff:
                staff = Staffcreation.objects.filter(employee_name=username).first()

            if not staff:
                Staffcreation.objects.create(**defaults)
                continue

            for field, value in defaults.items():
                setattr(staff, field, value)
            staff.save()

        self.log("---Auth staff users seeded (driver/operator/driver2/operator2/approver).---")
