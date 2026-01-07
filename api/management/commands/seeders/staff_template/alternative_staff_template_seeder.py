from datetime import date

from api.management.commands.seeders.base import BaseSeeder
from api.apps.alternative_staff_template import AlternativeStaffTemplate
from api.apps.stafftemplate import StaffTemplate
from django.contrib.auth import get_user_model

User = get_user_model()


class AlternativeStaffTemplateSeeder(BaseSeeder):
    name = "alternative_staff_template"

    def run(self):
        """
        Seeds AlternativeStaffTemplate with controlled baseline data.
        Assumes StaffTemplate and User data already exist.
        """

        # ---- FETCH REQUIRED DEPENDENCIES ----
        staff_template = StaffTemplate.objects.first()
        if not staff_template:
            self.log("No StaffTemplate found. Seeder aborted.")
            return

        users = User.objects.all()[:4]
        if users.count() < 3:
            self.log("Insufficient users found. Seeder aborted.")
            return

        driver = users[0]
        operator = users[1]
        approver = users[2]
        extra_operator = users[3] if users.count() > 3 else None

        # ---- SEED DATA ----
        AlternativeStaffTemplate.objects.get_or_create(
            staff_template=staff_template,
            effective_date=date.today(),
            driver=driver,
            operator=operator,
            defaults={
                "extra_operator": extra_operator,
                "change_reason": "Temporary staff substitution",
                "change_remarks": "Seeder-generated record for baseline validation",
                "requested_by": driver,
                "approved_by": approver,
                "approval_status": "APPROVED",
            }
        )

        self.log("Alternative staff templates seeded successfully")
