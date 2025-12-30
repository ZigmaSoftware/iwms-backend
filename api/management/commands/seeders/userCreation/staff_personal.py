from api.apps.staffcreation import StaffOfficeDetails, StaffPersonalDetails


class StaffPersonalSeeder:
    group = "user-creation"

    def run(self):
        base_phone = 9000000000

        for staff in StaffOfficeDetails.objects.all():
            contact_mobile = str(base_phone + staff.id)
            contact_email = f"{staff.employee_name.replace(' ', '').lower()}@example.com"

            staff_personal, created = StaffPersonalDetails.objects.get_or_create(
                staff=staff,
                defaults={
                    "staff_unique_id": staff.staff_unique_id,
                    "gender": "Male",
                    "blood_group": "O+",
                    "contact_mobile": f"900{staff.id:07d}",
                    "contact_email": f"{staff.employee_name.replace(' ', '').lower()}@example.com",
                }
            )

        print(" StaffPersonalDetails seeded")
