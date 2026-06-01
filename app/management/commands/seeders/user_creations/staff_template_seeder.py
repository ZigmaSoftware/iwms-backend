from app.management.commands.seeders.base import BaseSeeder
from app.models.user_creations.stafftemplate import StaffTemplate
from app.models.user_creations.staffcreation import Staffcreation
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project
from app.utils.base_models import Account


class StaffTemplateSeeder(BaseSeeder):
    name = "staff_template"

    def _get_account(self, staff):
        if not staff:
            return None
        account, _ = Account.objects.get_or_create(staff=staff)
        return account

    def _resolve_staff(self, username):
        return (
            Staffcreation.objects
            .filter(username__iexact=username, is_active=True, is_deleted=False)
            .order_by("staff_unique_id")
            .first()
        )

    def _ensure_company_and_project(self, *staff_members):
        for staff in staff_members:
            company = getattr(staff, "company_id", None)
            project = getattr(staff, "project_id", None)
            if company and project:
                return company, project

        company, _ = Company.objects.get_or_create(
            name="IWMS",
            defaults={
                "description": "Integrated Waste Management System",
                "is_active": True,
                "is_deleted": False,
            },
        )
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
        return company, project

    def run(self):
        """Seed two driver+operator staff templates for the operator-mobile flow."""

        pairs = [
            ("driver_user", "operator_user"),
            ("driver2_user", "operator2_user"),
        ]

        created_count = 0
        skipped = 0

        for driver_username, operator_username in pairs:
            driver = self._resolve_staff(driver_username)
            operator = self._resolve_staff(operator_username)
            if not driver or not operator:
                self.log(
                    f"StaffTemplate skipped: missing staff "
                    f"({driver_username}, {operator_username})."
                )
                skipped += 1
                continue

            company, project = self._ensure_company_and_project(driver, operator)
            account = self._get_account(driver)

            _, was_created = StaffTemplate.objects.get_or_create(
                driver_id=driver,
                operator_id=operator,
                defaults={
                    "company_id": company,
                    "project_id": project,
                    "extra_operator_id": [],
                    "created_by": account,
                    "updated_by": account,
                    "approved_by": driver,
                    "status": "ACTIVE",
                    "approval_status": "APPROVED",
                },
            )
            if was_created:
                created_count += 1

        self.log(
            f"---StaffTemplate seeded | created={created_count} | skipped={skipped}---"
        )
