from django.conf import settings

from app.management.commands.seeders.base import BaseSeeder
from app.models.staff_creations.staffcreation import Staffcreation
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

        company = Company.objects.filter(is_deleted=False).first()
        project = Project.objects.filter(company_id=company, is_deleted=False).first() if company else None

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
            defaults={"is_active": True, "is_deleted": False},
        )
        operator_role, _ = StaffUserType.objects.get_or_create(
            name="Company Operator",
            usertype_id=staff_type,
            defaults={"is_active": True, "is_deleted": False},
        )
        approver_role, _ = StaffUserType.objects.get_or_create(
            name="Admin",
            usertype_id=staff_type,
            defaults={"is_active": True, "is_deleted": False},
        )

        # 7 driver-operator pairs + 1 approver = 15 entries
        # Passwords: min 6 chars, uppercase + lowercase + digit
        # NOTE: supervisor_user is NOT seeded here — see SupervisorUserSeeder,
        # which wires it to driver_user's real trip plan(s) and complaint
        # teams rather than creating a bare, data-less login.
        seed_staff = [
            ("driver_user",   "driver1@demo.local",   "Driver123",   driver_role),
            ("operator_user", "operator1@demo.local",  "Operator123", operator_role),
            ("driver2_user",  "driver2@demo.local",   "Driver123",   driver_role),
            ("operator2_user","operator2@demo.local",  "Operator123", operator_role),
            ("driver3_user",  "driver3@demo.local",   "Driver123",   driver_role),
            ("operator3_user","operator3@demo.local",  "Operator123", operator_role),
            ("driver4_user",  "driver4@demo.local",   "Driver123",   driver_role),
            ("operator4_user","operator4@demo.local",  "Operator123", operator_role),
            ("driver5_user",  "driver5@demo.local",   "Driver123",   driver_role),
            ("operator5_user","operator5@demo.local",  "Operator123", operator_role),
            ("driver6_user",  "driver6@demo.local",   "Driver123",   driver_role),
            ("operator6_user","operator6@demo.local",  "Operator123", operator_role),
            ("driver7_user",  "driver7@demo.local",   "Driver123",   driver_role),
            ("operator7_user","operator7@demo.local",  "Operator123", operator_role),
            ("approver_user", "approver@demo.local",  "Approver123", approver_role),
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
                "approval_status": Staffcreation.APPROVAL_APPROVED,
                "login_enabled": True,
            }

            staff = Staffcreation.objects.filter(
                company_id=company,
                project_id=project,
                username=username,
            ).first()
            if not staff:
                staff = Staffcreation.objects.filter(
                    company_id=company,
                    project_id=project,
                    employee_name=username,
                ).first()
            if not staff:
                # `username` is globally unique, but the lookups above are
                # scoped to the first company/project. A later seeder may have
                # deliberately repinned this login to a different tenant (e.g.
                # DriverWetDryBinTripsSeeder moves driver_user/operator_user to
                # Blue Planet / Palakkad BP so CompanyScopedViewSet can see
                # their trips). Without this global fallback the scoped lookup
                # misses and create() dies on the unique username index.
                staff = Staffcreation.objects.filter(username=username).first()

            if not staff:
                Staffcreation.objects.create(**defaults)
                continue

            # Never re-tenant an existing login. Another seeder may own where
            # this staff member lives (DriverWetDryBinTripsSeeder pins
            # driver_user/operator_user to Blue Planet / Palakkad BP); blindly
            # writing this seeder's company/project back would undo that and
            # make the result depend on seeder ordering. Everything else —
            # role, password, contact, flags — is still refreshed.
            sticky = {"company_id", "project_id", "district_id", "city_id",
                      "zone_id", "ward_id"}
            for field, value in defaults.items():
                if field in sticky:
                    continue
                setattr(staff, field, value)
            staff.save()

        self.log(f"---Auth staff users seeded ({len(seed_staff)} records)---")
