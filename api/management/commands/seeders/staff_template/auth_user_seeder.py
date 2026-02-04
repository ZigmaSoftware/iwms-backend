from api.management.commands.seeders.base import BaseSeeder
from api.models.users.staffcreation import StaffOfficeDetails
from api.models.users.staffUserType import StaffUserType
from api.models.users.userType import UserType
from api.models.superadminmasters.company import Company
from api.models.superadminmasters.project import Project
from api.models.masters.district import District
from api.models.masters.city import City
from api.models.masters.zone import Zone
from api.models.masters.ward import Ward


class AuthUserSeeder(BaseSeeder):
    name = "auth_user"

    def run(self):
        """
        Ensure at least three staff users exist with auth fields for alternative staff template links.
        """
        company = Company.objects.filter(is_deleted=False).first()
        project = None
        if company:
            project = Project.objects.filter(company_id=company, is_deleted=False).first()

        district = District.objects.filter(is_deleted=False).first()
        city = City.objects.filter(is_deleted=False).first()
        zone = Zone.objects.filter(is_deleted=False).first()
        ward = Ward.objects.filter(is_deleted=False).first()

        # Get or create staff user type
        try:
            staff_type = UserType.objects.get(name__iexact="staff")
        except UserType.DoesNotExist:
            self.log("UserType 'staff' not found. Seeder aborted.")
            return

        # Ensure staff user types exist
        driver_role, _ = StaffUserType.objects.get_or_create(
            name="driver",
            usertype_id=staff_type,
            defaults={"display_name": "Driver"}
        )
        operator_role, _ = StaffUserType.objects.get_or_create(
            name="operator",
            usertype_id=staff_type,
            defaults={"display_name": "Operator"}
        )
        approver_role, _ = StaffUserType.objects.get_or_create(
            name="admin",
            usertype_id=staff_type,
            defaults={"display_name": "Admin"}
        )

        seed_staff = [
            ("driver_user", "driver@demo.local", "driver123", driver_role),
            ("operator_user", "operator@demo.local", "operator123", operator_role),
            ("approver_user", "approver@demo.local", "approver123", approver_role),
        ]

        for employee_name, email, password, role in seed_staff:
            staff, created = StaffOfficeDetails.objects.get_or_create(
                employee_name=employee_name,
                defaults={
                    "email": email,
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
                },
            )
            if not created:
                # Update existing staff with auth fields
                staff.user_type_id = staff_type
                staff.staffusertype_id = role
                staff.password = password
                staff.company_id = company
                staff.project_id = project
                staff.district_id = district
                staff.city_id = city
                staff.zone_id = zone
                staff.ward_id = ward
                staff.is_active = True
                staff.is_deleted = False
                staff.save()

        self.log("Auth staff users seeded (driver/operator/approver).")
