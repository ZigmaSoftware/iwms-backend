from api.management.commands.seeders.base import BaseSeeder
from api.apps.stafftemplate import StaffTemplate
from api.apps.userCreation import User


class StaffTemplateSeeder(BaseSeeder):
    name = "staff_template"

    def _pick_user(self, role_name):
        return (
            User.objects.filter(
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
        driver = self._pick_user("driver")
        operator = self._pick_user("operator")

        if not driver or not operator:
            self.log("Driver or Operator user not found. Seeder aborted.")
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
