from app.models.users.staffcreation import StaffOfficeDetails
from app.models.superadminmasters.company import Company
from app.models.superadminmasters.project import Project
from app.models.masters.district import District
from app.models.masters.city import City
from app.models.masters.zone import Zone
from app.models.masters.ward import Ward
from app.models.users.userType import UserType
from app.models.users.staffUserType import StaffUserType


class StaffOfficeSeeder:
    group = "user-creation"

    def run(self):
        company = Company.objects.filter(is_deleted=False).first()
        project = None
        if company:
            project = Project.objects.filter(company_id=company, is_deleted=False).first()

        district = District.objects.filter(is_deleted=False).first()
        city = City.objects.filter(is_deleted=False).first()
        zone = Zone.objects.filter(is_deleted=False).first()
        ward = Ward.objects.filter(is_deleted=False).first()

        staff_type = UserType.objects.filter(name__iexact="staff").first()
        if not staff_type:
            print("UserType 'staff' missing. Skipping StaffOfficeDetails seeding.")
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
                }
            )

        for staff_data in staff_list:
            StaffOfficeDetails.objects.update_or_create(
                employee_name=staff_data["employee_name"],
                defaults=staff_data
            )

        print("StaffOfficeDetails seeded")
