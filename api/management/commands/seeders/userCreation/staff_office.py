from api.apps.staffcreation import StaffOfficeDetails
from datetime import date

class StaffOfficeSeeder:
    group = "user-creation"

    def run(self):
        staff_data = [
            {
                "employee_name": "Sathya",
                "department": "Administration",
                "designation": "System Admin",
                "grade": "A",
                "site_name": "HQ",
                "salary_type": "Monthly",
            },
            {
                "employee_name": "Aakash",
                "department": "Operations",
                "designation": "Operator",
                "grade": "B",
                "site_name": "Zone Office",
                "salary_type": "Monthly",
            },
        ]

        for data in staff_data:
            StaffOfficeDetails.objects.get_or_create(
                employee_name=data["employee_name"],
                defaults=data
            )

        print("StaffOfficeDetails seeded")
