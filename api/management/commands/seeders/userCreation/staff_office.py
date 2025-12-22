from api.apps.staffcreation import StaffOfficeDetails


class StaffOfficeSeeder:
    group = "user-creation"

    def run(self):
        staff_data = {
            "employee_name": "Sathya",
            "department": "Administration",
            "designation": "System Admin",
            "grade": "A",
            "site_name": "HQ",
            "salary_type": "Monthly",
        }

        StaffOfficeDetails.objects.get_or_create(
            employee_name=staff_data["employee_name"],
            defaults=staff_data
        )

        print("StaffOfficeDetails (Admin only) seeded")
