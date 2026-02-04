from datetime import date

from app.management.commands.seeders.base import BaseSeeder
from app.models.users.alternative_staff_template import AlternativeStaffTemplate
from app.models.users.stafftemplate import StaffTemplate
from app.models.users.staffcreation import StaffOfficeDetails


class AlternativeStaffTemplateSeeder(BaseSeeder):
    name = "alternative_staff_template"

    def run(self):
        """
        Seeds AlternativeStaffTemplate with controlled baseline data.
        Assumes StaffTemplate and Staff data already exist.
        """

        # ---- FETCH REQUIRED DEPENDENCIES ----
        staff_template = StaffTemplate.objects.first()
        if not staff_template:
            self.log("No StaffTemplate found. Seeder aborted.")
            return

        # Pull staff from StaffOfficeDetails
        staff_list = list(StaffOfficeDetails.objects.filter(
            is_active=True,
            is_deleted=False
        ).order_by("id")[:4])
        
        if len(staff_list) < 3:
            self.log("Insufficient staff found (need at least 3). Seeder aborted.")
            return

        driver = staff_list[0]
        operator = staff_list[1]
        approver = staff_list[2]
        extra_operator = staff_list[3] if len(staff_list) > 3 else None

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
