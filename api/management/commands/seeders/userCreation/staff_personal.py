from api.apps.staffcreation import StaffOfficeDetails, StaffPersonalDetails

class StaffPersonalSeeder:
    group = "user-creation"

    def run(self):
        for staff in StaffOfficeDetails.objects.all():
            StaffPersonalDetails.objects.get_or_create(
                staff=staff,
                defaults={
                    "staff_unique_id": staff.staff_unique_id,
                    "gender": "Male",
                    "blood_group": "O+",
                    "contact_mobile": "9999999999",
                    "contact_email": f"{staff.employee_name.replace(' ', '').lower()}@example.com",
                }
            )

        print("✅ StaffPersonalDetails seeded")
