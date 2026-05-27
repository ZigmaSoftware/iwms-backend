from datetime import date

from app.management.commands.seeders.base import BaseSeeder
from app.models.user_creations.alternative_staff_template import AlternativeStaffTemplate
from app.models.user_creations.stafftemplate import StaffTemplate
from app.models.user_creations.staffcreation import Staffcreation
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project


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

        # Pull staff from Staffcreation
        staff_list = list(Staffcreation.objects.filter(
            is_active=True,
            is_deleted=False
        ).order_by("staff_unique_id")[:4])
        
        if len(staff_list) < 3:
            self.log("Insufficient staff found (need at least 3). Seeder aborted.")
            return

        driver = staff_list[0]
        operator = staff_list[1]
        approver = staff_list[2]
        extra_operator = staff_list[3] if len(staff_list) > 3 else None
        company = getattr(staff_template, "company_id", None) or getattr(driver, "company_id", None)
        project = getattr(staff_template, "project_id", None) or getattr(driver, "project_id", None)
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

        # ---- SEED DATA ----
        AlternativeStaffTemplate.objects.get_or_create(
            staff_template=staff_template,
            company_id=company,
            project_id=project,
            # effective_date=date.today(),
            driver_id=driver,
            operator_id=operator,
            defaults={
                "extra_operator_id": [str(extra_operator.staff_unique_id)] if extra_operator else [],
                "change_reason": "Temporary staff substitution",
                "change_remarks": "Seeder-generated record for baseline validation",
                # "requested_by": driver,
                "approved_by": approver,
                "approval_status": "APPROVED",
            }
        )

        self.log("---Alternative staff templates seeded successfully---")
