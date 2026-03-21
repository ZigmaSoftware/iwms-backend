from django.contrib.auth.hashers import make_password

from app.models.user_creations.staffcreation import Staffcreation
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project
from app.models.masters.district import District
from app.models.masters.city import City
from app.models.masters.zone import Zone
from app.models.masters.ward import Ward
from app.models.role_assigns.userType import UserType
from app.models.role_assigns.staffUserType import StaffUserType


DEFAULT_STAFF_PASSWORD = "Staff@123"


class StaffOfficeSeeder:
    group = "user-creation"

    def run(self):
        company = Company.objects.filter(is_deleted=False).first()
        if not company:
            company, _ = Company.objects.get_or_create(
                name="IWMS",
                defaults={
                    "description": "Integrated Waste Management System",
                    "is_active": True,
                    "is_deleted": False,
                },
            )
        project = Project.objects.filter(company_id=company, is_deleted=False).first()
        if not project:
            project_name = f"{company.name} Main Project"
            project, _ = Project.objects.get_or_create(
                name=project_name,
                company_id=company,
                defaults={
                    "description": f"Default project for {company.name}",
                    "is_active": True,
                    "is_deleted": False,
                },
            )

        district = District.objects.filter(is_deleted=False).first()
        city = City.objects.filter(is_deleted=False).first()
        zone = Zone.objects.filter(is_deleted=False).first()
        ward = Ward.objects.filter(is_deleted=False).first()

        staff_type = UserType.objects.filter(name__iexact="staff").first()
        if not staff_type:
            print("UserType 'staff' missing. Skipping Staffcreation seeding.")
            return

        role_admin = StaffUserType.objects.filter(
            name__iexact="admin",
            usertype_id=staff_type,
        ).first()
        role_driver = StaffUserType.objects.filter(
            name__iexact="driver",
            usertype_id=staff_type,
        ).first()
        role_operator = StaffUserType.objects.filter(
            name__iexact="operator",
            usertype_id=staff_type,
        ).first()
        role_supervisor = StaffUserType.objects.filter(
            name__iexact="supervisor",
            usertype_id=staff_type,
        ).first()

        if not all([role_admin, role_driver, role_operator, role_supervisor]):
            print("Required staff roles missing. Run StaffUserTypeSeeder first.")
            return

        staff_passwords = {
            "Sathya": "Sathya@123",
            "Gokul": "Gokul@123",
            "Arjun": "Arjun@123",
            "Vikram": "Vikram@123",
            "Karan": "Karan@123",
            "Suresh": "Suresh@123",
            "Mani": "Mani@123",
            "Rahul": "Rahul@123",
            "Prakash": "Prakash@123",
            "Deepak": "Deepak@123",
            "Naveen": "Naveen@123",
            "Santhosh": "Santhosh@123",
            "Ajay": "Ajay@123",
            "Anita": "Anita@123",
            "Kumar": "Kumar@123",
            "Priya": "Priya@123",
        }

        staff_list = [
            {
                "employee_name": "Sathya",
                "department": "Administration",
                "designation": "System Admin",
                "grade": "A",
                "site_name": "HQ",
                "salary_type": "Monthly",
                "active_status": True,
                "company_id": company,
                "project_id": project,
                "district_id": district,
                "city_id": city,
                "zone_id": zone,
                "ward_id": ward,
                "user_type_id": staff_type,
                "staffusertype_id": role_admin,
                "password": staff_passwords["Sathya"],
            },
        ]

        driver_names = [
            "Gokul",
            "Arjun",
            "Vikram",
            "Karan",
            "Suresh",
            "Mani",
        ]
        operator_names = [
            "Rahul",
            "Prakash",
            "Deepak",
            "Naveen",
            "Santhosh",
            "Ajay",
        ]
        supervisor_names = [
            "Anita",
            "Kumar",
            "Priya",
        ]

        for idx, name in enumerate(driver_names, start=1):
            staff_list.append(
                {
                    "employee_name": name,
                    "department": "Operations",
                    "designation": "Driver",
                    "grade": "B",
                    "site_name": f"Depot-{(idx % 3) + 1}",
                    "salary_type": "Monthly",
                    "active_status": True,
                    "company_id": company,
                    "project_id": project,
                    "district_id": district,
                    "city_id": city,
                    "zone_id": zone,
                    "ward_id": ward,
                    "user_type_id": staff_type,
                    "staffusertype_id": role_driver,
                    "password": staff_passwords.get(name, DEFAULT_STAFF_PASSWORD),
                }
            )

        for idx, name in enumerate(operator_names, start=1):
            staff_list.append(
                {
                    "employee_name": name,
                    "department": "Operations",
                    "designation": "Operator",
                    "grade": "B",
                    "site_name": f"Depot-{(idx % 3) + 1}",
                    "salary_type": "Monthly",
                    "active_status": True,
                    "company_id": company,
                    "project_id": project,
                    "district_id": district,
                    "city_id": city,
                    "zone_id": zone,
                    "ward_id": ward,
                    "user_type_id": staff_type,
                    "staffusertype_id": role_operator,
                    "password": staff_passwords.get(name, DEFAULT_STAFF_PASSWORD),
                }
            )

        for idx, name in enumerate(supervisor_names, start=1):
            staff_list.append(
                {
                    "employee_name": name,
                    "department": "Operations",
                    "designation": "Supervisor",
                    "grade": "A",
                    "site_name": f"Depot-{(idx % 3) + 1}",
                    "salary_type": "Monthly",
                    "active_status": True,
                    "company_id": company,
                    "project_id": project,
                    "district_id": district,
                    "city_id": city,
                    "zone_id": zone,
                    "ward_id": ward,
                    "user_type_id": staff_type,
                    "staffusertype_id": role_supervisor,
                    "password": staff_passwords.get(name, DEFAULT_STAFF_PASSWORD),
                }
            )

        for staff_data in staff_list:
            raw_password = staff_data.pop("password", None) or DEFAULT_STAFF_PASSWORD
            staff_data["_hashed_password"] = make_password(raw_password)

        for staff_data in staff_list:
            hashed_password = staff_data.pop("_hashed_password", None)
            staff, created = Staffcreation.objects.update_or_create(
                employee_name=staff_data["employee_name"],
                defaults=staff_data
            )

            if hashed_password and (created or not staff.password):
                staff.password = hashed_password
                staff.save(update_fields=["password"])

        print("---Staffcreation seeded---")
