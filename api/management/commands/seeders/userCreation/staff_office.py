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

        for idx, name in enumerate(driver_names, start=1):
            staff_list.append(
                {
                    "employee_name": name,
                    "department": "Operations",
                    "designation": "Driver",
                    "grade": "B",
                    "site_name": f"Depot-{(idx % 3) + 1}",
                    "salary_type": "Monthly",
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
                }
            )

        for staff_data in staff_list:
            StaffOfficeDetails.objects.get_or_create(
                employee_name=staff_data["employee_name"],
                defaults=staff_data
            )

        print("StaffOfficeDetails seeded")
