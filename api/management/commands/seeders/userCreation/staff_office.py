from api.apps.staffcreation import StaffOfficeDetails


class StaffOfficeSeeder:
    group = "user-creation"

    def run(self):
        staff_list = [
            {
                "employee_name": "Sathya",
                "department": "Administration",
                "designation": "System Admin",
                "grade": "A",
                "site_name": "HQ",
                "salary_type": "Monthly",
            },
            {
                "employee_name": "Gokul",
                "department": "Operations",
                "designation": "Driver",
                "grade": "B",
                "site_name": "Depot",
                "salary_type": "Monthly",
            },
            {
                "employee_name": "Rahul",
                "department": "Operations",
                "designation": "Operator",
                "grade": "B",
                "site_name": "Depot",
                "salary_type": "Monthly",
            },
        ]

        for staff_data in staff_list:
            StaffOfficeDetails.objects.get_or_create(
                employee_name=staff_data["employee_name"],
                defaults=staff_data
            )

        print("StaffOfficeDetails (Admin only) seeded")
