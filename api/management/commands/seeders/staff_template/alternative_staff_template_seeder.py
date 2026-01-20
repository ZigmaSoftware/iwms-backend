from datetime import date

from api.management.commands.seeders.base import BaseSeeder
from api.apps.alternative_staff_template import AlternativeStaffTemplate
from api.apps.stafftemplate import StaffTemplate
from api.apps.userCreation import User


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

        # Pull auth users (model tied to AUTH_USER_MODEL)
        users = list(User.objects.filter(is_active=True).order_by("id")[:4])
        if len(users) < 3:
            self.log("Insufficient auth users found (need at least 3). Seeder aborted.")
            return

        driver = users[0]
        operator = users[1]
        approver = users[2]
        extra_operator = users[3] if len(users) > 3 else None

        # ---- SEED DATA ----
        AlternativeStaffTemplate.objects.get_or_create(
            staff_template=staff_template,
            effective_date=date.today(),
            driver_id=driver,
            operator_id=operator,
            defaults={
                "extra_operator_id": [str(extra_operator.pk)] if extra_operator else [],
                "change_reason": "Temporary staff substitution",
                "change_remarks": "Seeder-generated record for baseline validation",
                "requested_by": driver,
                "approved_by": approver,
                "approval_status": "APPROVED",
            }
        )

        self.log("Alternative staff templates seeded successfully")
