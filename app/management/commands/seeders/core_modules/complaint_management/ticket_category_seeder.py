from app.management.commands.seeders.base import BaseSeeder
from app.models.complaint_management import (
    ComplaintCategory,
    ComplaintModule,
    ComplaintPriority,
)
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project


class ComplaintCategorySeeder(BaseSeeder):
    name = "complaint_ticket_category"

    # Categories are the root of the complaint-management tenancy chain —
    # ComplaintSubcategory/ComplaintSlaRule derive their own company_id/
    # project_id from the category on save (see their `save()` overrides), so
    # stamping it here is enough for the whole chain. Scoped to this one
    # company/project since that's the only one this dev environment actually
    # has complaint-ticket data (hierarchy, staff, tickets) for; the
    # `MasterForm` edit screens require a company/project to be set to
    # pre-fill their Company/Project dropdowns.
    COMPANY_NAME = "Blue Planet"
    PROJECT_NAME = "Blue Planet Integrated Waste Management"

    # (category_code, category_name, default_priority_code, module_code,
    #  requires_location, requires_media, sort_order)
    CATEGORIES = [
        ("MISSED_PICKUP", "Missed Pickup", "P2", "SANITATION", True, False, 10),
        ("BULK_WASTE", "Bulk Waste Pickup", "P3", "SANITATION", True, True, 20),
        ("WORKER_CONDUCT", "Worker Conduct", "P2", "GENERAL", False, False, 30),
        ("VEHICLE_ISSUE", "Vehicle Issue", "P3", "TRANSPORT", True, True, 40),
        ("BILLING_QUERY", "Billing Inquiry", "P3", "CUSTOMER_SERVICE", False, False, 50),
        ("ADDRESS_CHANGE", "Change of Address", "P3", "CUSTOMER_SERVICE", False, False, 60),
        ("GARBAGE", "Garbage", "P2", "SANITATION", True, False, 70),
        ("PUBLIC_TOILET", "Public Toilet", "P2", "SANITATION", True, False, 80),
        ("OTHER", "Other", "P4", "GENERAL", False, False, 90),
    ]

    def run(self):
        company = Company.objects.filter(name=self.COMPANY_NAME, is_deleted=False).first()
        project = (
            Project.objects.filter(
                name=self.PROJECT_NAME, company_id=company, is_deleted=False,
            ).first()
            if company
            else None
        )
        if not company or not project:
            self.log(
                f"---Complaint ticket categories: '{self.COMPANY_NAME}' / "
                f"'{self.PROJECT_NAME}' not found — seeding without tenancy---"
            )

        for code, name, priority_code, module_code, req_loc, req_media, sort_order in self.CATEGORIES:
            priority = ComplaintPriority.objects.filter(priority_code=priority_code).first()
            module = ComplaintModule.objects.filter(module_code=module_code).first()
            category, created = ComplaintCategory.objects.get_or_create(
                category_code=code,
                defaults={
                    "category_name": name,
                    "default_priority": priority,
                    "module": module,
                    "requires_location": req_loc,
                    "requires_media": req_media,
                    "sort_order": sort_order,
                    "is_active": True,
                    "is_deleted": False,
                    "company_id": company,
                    "project_id": project,
                },
            )
            # Backfill tenancy on a category seeded before this fix, so
            # existing rows aren't left permanently untenanted.
            if not created and company and project and not category.company_id_id:
                category.company_id = company
                category.project_id = project
                category.save(update_fields=["company_id", "project_id"])
        self.log(f"---Complaint ticket categories seeded ({len(self.CATEGORIES)} records)---")
