from api.apps.staffcreation import StaffOfficeDetails
from api.apps.userType import UserType
from api.apps.staffUserType import StaffUserType
from api.apps.company import Company
from api.apps.project import Project
from api.apps.district import District
from api.apps.city import City
from api.apps.zone import Zone
from api.apps.ward import Ward


class UserSeeder:
    group = "user-creation"

    def run(self):
        try:
            staff_type = UserType.objects.get(name__iexact="staff")
        except UserType.DoesNotExist:
            print("UserType 'staff' not found. Run role-assign seeders first.")
            return

        roles = {}
        for role_name in ["admin", "driver", "operator", "supervisor"]:
            try:
                roles[role_name] = StaffUserType.objects.get(
                    name__iexact=role_name,
                    usertype_id=staff_type,
                )
            except StaffUserType.DoesNotExist:
                print(f"StaffUserType '{role_name}' not found. Skipping assignment.")
                roles[role_name] = None

        company = Company.objects.filter(is_deleted=False).first()
        project = None
        if company:
            project = Project.objects.filter(company_id=company, is_deleted=False).first()

        district = District.objects.filter(is_deleted=False).first()
        city = City.objects.filter(is_deleted=False).first()
        zone = Zone.objects.filter(is_deleted=False).first()
        ward = Ward.objects.filter(is_deleted=False).first()

        staff_qs = StaffOfficeDetails.objects.filter(is_deleted=False)
        if not staff_qs.exists():
            print("No staff found. Skipping UserSeeder.")
            return

        updated = 0
        for staff in staff_qs:
            designation = (staff.designation or "").lower()
            if "driver" in designation:
                role = roles.get("driver")
            elif "operator" in designation:
                role = roles.get("operator")
            elif "supervisor" in designation:
                role = roles.get("supervisor")
            else:
                role = roles.get("admin")

            if role:
                staff.staffusertype_id = role
            staff.user_type_id = staff_type
            staff.is_active = True
            staff.is_deleted = False

            if not staff.company_id:
                staff.company_id = company
            if not staff.project_id:
                staff.project_id = project
            if not staff.district_id:
                staff.district_id = district
            if not staff.city_id:
                staff.city_id = city
            if not staff.zone_id:
                staff.zone_id = zone
            if not staff.ward_id:
                staff.ward_id = ward

            staff.save()
            updated += 1

        print(f"UserSeeder updated {updated} staff records.")
