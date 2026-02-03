from api.apps.staffcreation import StaffOfficeDetails
from api.apps.company import Company
from api.apps.project import Project
from api.apps.district import District
from api.apps.city import City
from api.apps.zone import Zone
from api.apps.ward import Ward


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
                }
            )

        for staff_data in staff_list:
            StaffOfficeDetails.objects.update_or_create(
                employee_name=staff_data["employee_name"],
                defaults=staff_data
            )

        print("StaffOfficeDetails seeded")
