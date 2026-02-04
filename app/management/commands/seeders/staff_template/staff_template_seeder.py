from app.management.commands.seeders.base import BaseSeeder
from app.models.users.stafftemplate import StaffTemplate
from app.models.users.staffcreation import StaffOfficeDetails


class StaffTemplateSeeder(BaseSeeder):
    name = "staff_template"

    def _pick_staff(self, role_name):
        return (
            StaffOfficeDetails.objects.filter(
                staffusertype_id__name__iexact=role_name,
                is_active=True,
                is_deleted=False,
            )
            .order_by("id")
            .first()
        )

    def run(self):
        """
        Seed a minimal staff template using first available driver/operator users.
        """
        driver = self._pick_staff("driver")
        operator = self._pick_staff("operator")

        if not driver or not operator:
            self.log("Driver or Operator staff not found. Seeder aborted.")
            return

        StaffTemplate.objects.get_or_create(
            driver_id=driver,
            operator_id=operator,
            defaults={
                "extra_operator_id": [],
                "created_by": driver,
                "updated_by": driver,
                "approved_by": driver,
                "status": "ACTIVE",
                "approval_status": "APPROVED",
            },
        )

        self.log("StaffTemplate seeded successfully")
