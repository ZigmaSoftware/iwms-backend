"""Sample complaint tickets raised by staff/call-centre.

Gives the Complaint Desk something to show: the SLA countdown column, the
Kanban board, and the Feedback list all render off real rows rather than an
empty table.

Each ticket is raised against a known `CustomerCreation` and its geo is copied
from that customer so the row lands in the same zone/ward the supervisor
queues filter on.

Priority/status/team/SLA are NOT hardcoded here. Each ticket is created with
status SUBMITTED and the priority its category implies, then run through
`apply_routing_and_sla` — the same service the live intake paths call — so the
seeded rows exercise the real routing and get real due dates.

Must run AFTER `complaint_ticket_subcategory`, `complaint_sla_rule` and
`complaint_routing_rule` (needs categories, teams and SLA rules), and after
the customer seeders (internal tickets attach to a real customer).
"""

from django.utils import timezone

from app.management.commands.seeders.base import BaseSeeder
from app.models.masters.customer_masters.customercreation import CustomerCreation
from app.models.core_modules.complaint_management import (
    ComplaintCategory,
    ComplaintFeedback,
    ComplaintPriority,
    ComplaintSource,
    ComplaintStatus,
    ComplaintSubcategory,
    ComplaintTicket,
)
from app.models.core_modules.complaint_management.transactions import ComplaintStatusHistory
from app.services.complaint_ticket_routing import apply_routing_and_sla


class ComplaintSampleTicketSeeder(BaseSeeder):
    name = "complaint_sample_ticket"

    # (category_code, subcategory_code|None, title, description)
    INTERNAL = [
        ("MISSED_PICKUP", "WET_NOT_COLLECTED", "Wet waste not collected for 3 days",
         "Wet waste bin has not been emptied since Monday. Smell is spreading."),
        ("GARBAGE", "BIN_OVERFLOW", "Bin overflowing near market",
         "The community bin outside the market is overflowing onto the road."),
        ("VEHICLE_ISSUE", "WASTE_SPILLAGE", "Waste spilling from collection vehicle",
         "Collection vehicle is dropping waste along the street while moving."),
        ("BILLING_QUERY", "WRONG_AMOUNT", "Charged more than the usual amount",
         "This month's bill is higher than previous months with no explanation."),
        ("WORKER_CONDUCT", "ABSENT_STAFF", "Collection staff did not turn up",
         "No collection staff visited our street this week."),
    ]

    # Tickets that also get citizen feedback, so the Feedback list is not
    # empty. (index into INTERNAL, rating, solved)
    FEEDBACK = [(0, 4, True), (1, 2, False)]

    def _resolve(self, category_code, subcategory_code):
        category = ComplaintCategory.objects.filter(
            category_code=category_code, is_deleted=False
        ).first()
        if not category:
            return None, None
        subcategory = (
            ComplaintSubcategory.objects.filter(
                category_id=category.unique_id, subcategory_code=subcategory_code, is_deleted=False
            ).first()
            if subcategory_code
            else None
        )
        return category, subcategory

    def _priority_for(self, category, subcategory):
        return (
            (subcategory.default_priority if subcategory else None)
            or category.default_priority
            or ComplaintPriority.objects.filter(priority_code="P3", is_deleted=False).first()
        )

    def _create(self, *, category, subcategory, status, priority, source, **fields):
        """Create the ticket if an identical one is not already seeded.

        Keyed on (source, title) rather than `get_or_create` on everything:
        `ticket_no` and `unique_id` are generated per call, so a defaults-based
        lookup would insert a duplicate on every run.
        """
        existing = ComplaintTicket.objects.filter(
            source_id=source.unique_id, title=fields.get("title"), is_deleted=False
        ).first()
        if existing:
            return existing, False

        customer = fields.pop("customer", None)
        if customer is not None:
            fields["customer_id"] = customer.unique_id

        ticket = ComplaintTicket.objects.create(
            category_id=category.unique_id,
            subcategory_id=subcategory.unique_id if subcategory else None,
            priority_id=priority.unique_id if priority else None,
            status_id=status.unique_id,
            source_id=source.unique_id,
            **fields,
        )
        ComplaintStatusHistory.objects.create(
            ticket_id=ticket.unique_id,
            from_status_id=None,
            to_status_id=status.unique_id,
            changed_by_system=True,
            remarks="Seeded sample ticket",
        )
        # Same routing the live intake paths run, so these rows get a real
        # team and real SLA due dates instead of seeded guesses.
        apply_routing_and_sla(ticket)
        return ticket, True

    def run(self):
        submitted = ComplaintStatus.objects.filter(
            status_code="SUBMITTED", is_deleted=False
        ).first()
        if not submitted:
            self.log("---Sample tickets skipped (run the complaint-ticket seeders first)---")
            return

        internal_source, _ = ComplaintSource.objects.get_or_create(
            source_code="ADMIN",
            defaults={"source_name": "Admin", "is_active": True, "is_deleted": False},
        )

        customers = list(
            CustomerCreation.objects.filter(is_deleted=False).select_related()[:len(self.INTERNAL)]
        )
        if not customers:
            self.log("---Sample tickets: no customers found, internal tickets skipped---")

        created_internal = 0
        internal_tickets = {}
        for index, (cat_code, sub_code, title, description) in enumerate(self.INTERNAL):
            category, subcategory = self._resolve(cat_code, sub_code)
            if not category or index >= len(customers):
                continue
            customer = customers[index]
            ticket, created = self._create(
                category=category,
                subcategory=subcategory,
                status=submitted,
                priority=self._priority_for(category, subcategory),
                source=internal_source,
                title=title,
                description=description,
                customer=customer,
                profile_name=customer.customer_name,
                wa_phone=customer.contact_no,
                # Internal tickets inherit the customer's tenancy and geo so
                # they land in the zone/ward the supervisor queues filter on.
                company_id=customer.company_id,
                project_id=customer.project_id,
                zone_id=customer.zone_id,
                ward_id=customer.ward_id,
                location_text=getattr(customer, "address", "") or "",
            )
            internal_tickets[index] = ticket
            created_internal += 1 if created else 0

        created_feedback = 0
        for index, rating, solved in self.FEEDBACK:
            ticket = internal_tickets.get(index)
            if ticket is None:
                continue
            _, created = ComplaintFeedback.objects.get_or_create(
                ticket_id=ticket.unique_id,
                defaults={
                    "rating": rating,
                    "feedback_text": (
                        "Issue was cleared promptly." if solved else "Problem is still not fixed."
                    ),
                    "is_issue_solved": solved,
                    "is_active": True,
                    "is_deleted": False,
                },
            )
            created_feedback += 1 if created else 0

        self.log(
            f"---Sample complaint tickets seeded (internal +{created_internal}, "
            f"feedback +{created_feedback}; "
            f"total tickets now {ComplaintTicket.objects.filter(is_deleted=False).count()})---"
        )
