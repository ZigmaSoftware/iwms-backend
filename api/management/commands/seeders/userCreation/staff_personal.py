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
                    "contact_mobile": contact_mobile,
                    "contact_email": contact_email,
                }
            )

            if created:
                continue

            updates = {}
            if not staff_personal.contact_mobile or staff_personal.contact_mobile == "9999999999":
                updates["contact_mobile"] = contact_mobile
            if not staff_personal.contact_email:
                updates["contact_email"] = contact_email
            if not staff_personal.staff_unique_id:
                updates["staff_unique_id"] = staff.staff_unique_id

            if updates:
                StaffPersonalDetails.objects.filter(pk=staff_personal.pk).update(**updates)

        print(" StaffPersonalDetails seeded")
