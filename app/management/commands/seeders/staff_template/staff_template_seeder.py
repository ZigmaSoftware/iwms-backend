from app.management.commands.seeders.base import BaseSeeder
from app.models.user_creations.stafftemplate import StaffTemplate
from app.models.user_creations.staffcreation import StaffOfficeDetails
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project


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

        company = getattr(driver, "company_id", None) or getattr(operator, "company_id", None)
        project = getattr(driver, "project_id", None) or getattr(operator, "project_id", None)
        if not company:
            company, _ = Company.objects.get_or_create(
                name="IWMS",
                defaults={
                    "description": "Integrated Waste Management System",
                    "is_active": True,
                    "is_deleted": False,
                },
            )
        if not project:
            project_name = f"{company.name} Main Project"
            project, _ = Project.objects.get_or_create(
                name=project_name,
                company_id=company,
                defaults={
                    "description": f"Default project for {company.name}",
                    "is_active": True,
                    "is_deleted": False,
                },
            )

        StaffTemplate.objects.get_or_create(
            driver_id=driver,
            operator_id=operator,
            defaults={
                "company_id": company,
                "project_id": project,
                "extra_operator_id": [],
                "created_by": driver,
                "updated_by": driver,
                "approved_by": driver,
                "status": "ACTIVE",
                "approval_status": "APPROVED",
            },
        )

        self.log("---StaffTemplate seeded successfully---")
