"""Demo complaint tickets for the "Blue Planet" company / "Blue Planet
Integrated Waste Management" project, exercising the current hierarchy-based
escalation flow end to end.

Each row is created with status SUBMITTED and then routed through
`apply_routing_and_sla` — the same service the live intake paths call — so
assignment (to whichever staff member holds the ticket's SLA rule's lowest
enabled hierarchy level, narrowed by that staff's geo grants) and SLA/
escalation due dates are the real thing, not seeded guesses.

Must run AFTER `complaint_ticket_subcategory`, `complaint_sla_rule` and
`complaint_routing_rule` (needs categories, SLA rules and their escalation
levels), and after the customer seeders (several tickets attach to a real
`CustomerCreation`) and the company/project seeders (needs "Blue Planet" /
"Blue Planet Integrated Waste Management" to already exist). Also assumes
Blue Planet's `ProjectStaffHierarchy` and staff records already exist — run
those (or set them up through the UI) first, or seeded tickets land
unassigned.
"""

from app.management.commands.seeders.base import BaseSeeder
from app.models.customers.customercreation import CustomerCreation
from app.models.complaint_management import (
    ComplaintCategory,
    ComplaintPriority,
    ComplaintSource,
    ComplaintStatus,
    ComplaintSubcategory,
    ComplaintTicket,
)
from app.models.complaint_management.transactions import ComplaintStatusHistory
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project
from app.services.complaint_ticket_routing import apply_routing_and_sla


class ComplaintCurrentTicketSeeder(BaseSeeder):
    name = "complaint_current_ticket"

    COMPANY_NAME = "Blue Planet"
    PROJECT_NAME = "Blue Planet Integrated Waste Management"

    # (category_code, subcategory_code|None, priority_code, title, description,
    #  profile_name, wa_phone, customer_contact_no|None)
    #
    # `assigned_staff`/`escalation_level`/`is_escalated` are deliberately NOT
    # set here — they come entirely from `apply_routing_and_sla`, so this data
    # keeps working as the hierarchy/SLA configuration changes instead of
    # freezing a snapshot of staff usernames that may no longer exist.
    TICKETS = [
        ("MISSED_PICKUP", "WET_NOT_COLLECTED", "P2",
         "Wet waste not collected for 3 days",
         "Wet waste bin has not been emptied since Monday. Smell is spreading.",
         "Anitha Menon", "9940000000", "9940000000"),
        ("GARBAGE", "BIN_OVERFLOW", "P2",
         "Bin overflowing near market",
         "The community bin outside the market is overflowing onto the road.",
         "Anoop Varma", "9940000007", "9940000007"),
        ("VEHICLE_ISSUE", "WASTE_SPILLAGE", "P2",
         "Waste spilling from collection vehicle",
         "Collection vehicle is dropping waste along the street while moving.",
         "Deepa Krishnan", "9940000006", "9940000006"),
        ("BILLING_QUERY", "WRONG_AMOUNT", "P3",
         "Charged more than the usual amount",
         "This month's bill is higher than previous months with no explanation.",
         "Lakshmi Warrier", "9940000004", "9940000004"),
        ("WORKER_CONDUCT", "ABSENT_STAFF", "P2",
         "Collection staff did not turn up",
         "No collection staff visited our street this week.",
         "Radhika Nair", "9940000002", "9940000002"),
        # Priority left as None (below) for these three: they use whatever
        # priority the sub-category (or its category) actually declares as
        # `default_priority`, so they always land on a real seeded SLA rule
        # instead of guessing a priority code that might not have one.
        ("MISSED_PICKUP", "DRY_NOT_COLLECTED", None,
         "Dry waste pickup missed again",
         "Dry waste has not been collected for the second week in a row.",
         None, "2211335566", None),
        ("MISSED_PICKUP", "WET_NOT_COLLECTED", None,
         "Wet waste pickup overdue",
         "Wet waste pickup is overdue by two days.",
         None, "1234567890", None),
        ("MISSED_PICKUP", None, None,
         "Collection vehicle did not arrive",
         "The vehicle has not come to our lane for two days.",
         None, "1234566789", None),
    ]

    def _resolve_category(self, category_code, subcategory_code):
        category = ComplaintCategory.objects.filter(
            category_code=category_code, is_deleted=False
        ).first()
        if not category:
            return None, None
        subcategory = (
            ComplaintSubcategory.objects.filter(
                category=category, subcategory_code=subcategory_code, is_deleted=False
            ).first()
            if subcategory_code
            else None
        )
        return category, subcategory

    def run(self):
        company = Company.objects.filter(name=self.COMPANY_NAME, is_deleted=False).first()
        project = (
            Project.objects.filter(
                name=self.PROJECT_NAME, company_id=company, is_deleted=False
            ).first()
            if company
            else None
        )
        if not company or not project:
            self.log(
                f"---Current tickets skipped ('{self.COMPANY_NAME}' / "
                f"'{self.PROJECT_NAME}' not found — run the company/project "
                "seeders first)---"
            )
            return

        priorities = {
            p.priority_code: p for p in ComplaintPriority.objects.filter(is_deleted=False)
        }
        statuses = {
            s.status_code: s for s in ComplaintStatus.objects.filter(is_deleted=False)
        }
        internal_source, _ = ComplaintSource.objects.get_or_create(
            source_code="ADMIN",
            defaults={"source_name": "Admin", "is_active": True, "is_deleted": False},
        )
        submitted = statuses.get("SUBMITTED")
        if not submitted:
            self.log("---Current tickets skipped (run the complaint-ticket seeders first)---")
            return

        created_count = 0
        for (
            category_code, subcategory_code, priority_code,
            title, description, profile_name, wa_phone, customer_contact_no,
        ) in self.TICKETS:
            if ComplaintTicket.objects.filter(
                source=internal_source, title=title, is_deleted=False
            ).exists():
                continue

            category, subcategory = self._resolve_category(category_code, subcategory_code)
            if not category:
                continue
            priority = (
                priorities.get(priority_code)
                or (subcategory.default_priority if subcategory else None)
                or category.default_priority
            )

            customer = (
                CustomerCreation.objects.filter(contact_no=customer_contact_no, is_deleted=False).first()
                if customer_contact_no
                else None
            )

            ticket = ComplaintTicket.objects.create(
                category=category,
                subcategory=subcategory,
                priority=priority,
                status=submitted,
                source=internal_source,
                title=title,
                description=description,
                profile_name=profile_name,
                wa_phone=wa_phone,
                customer=customer,
                # Pinned explicitly rather than derived from the customer —
                # every ticket this seeder creates belongs to this one
                # company/project regardless of the customer's own tenancy.
                company_id=company,
                project_id=project,
                zone_id=getattr(customer, "zone_id", None),
                ward_id=getattr(customer, "ward_id", None),
                location_text=getattr(customer, "address", "") or "",
            )
            ComplaintStatusHistory.objects.create(
                ticket=ticket,
                from_status=None,
                to_status=submitted,
                changed_by_system=True,
                remarks="Seeded demo ticket",
            )
            # Real routing: assigns from the project's staff hierarchy (geo-
            # matched) and sets sla/escalation due dates, exactly like the
            # live intake paths.
            apply_routing_and_sla(ticket)

            created_count += 1

        self.log(
            f"---Current complaint tickets seeded (+{created_count} of {len(self.TICKETS)}, "
            f"scoped to {self.COMPANY_NAME} / {self.PROJECT_NAME}; total tickets now "
            f"{ComplaintTicket.objects.filter(is_deleted=False).count()})---"
        )
