"""Sample complaint tickets — internal (staff-raised) and public grievance.

Gives the Complaint Desk something to show: its four tabs (All / Public
Grievances / Internal / With Feedback), the SLA countdown column, the Kanban
board, and the Feedback list all render off real rows rather than an empty
table.

The two kinds mirror the two real intake paths:

  * INTERNAL  — raised by staff/call-centre against a known `CustomerCreation`.
    Carries `customer`, and its geo is copied from that customer so the row
    lands in the same zone/ward the supervisor queues filter on.
  * PUBLIC    — raised anonymously through `PublicGrievanceViewSet`. No
    customer; identity is just `profile_name`/`wa_phone`, and it carries the
    `PUBLIC_GRIEVANCE` source plus an `idempotency_key`, exactly as that
    viewset writes them.

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
from app.models.customers.customercreation import CustomerCreation
from app.models.complaint_management import (
    ComplaintCategory,
    ComplaintFeedback,
    ComplaintPriority,
    ComplaintSource,
    ComplaintStatus,
    ComplaintSubcategory,
    ComplaintTicket,
)
from app.models.complaint_management.transactions import ComplaintStatusHistory
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

    # (category_code, subcategory_code|None, person, phone, title, description)
    PUBLIC = [
        ("GARBAGE", "OPEN_DUMPING", "Rajesh Kumar", "9876543210",
         "Illegal dumping on the vacant plot",
         "People are dumping construction waste on the empty plot at night."),
        ("PUBLIC_TOILET", "NOT_CLEANED", "Meena S", "9876500011",
         "Public toilet not cleaned",
         "The public toilet near the bus stand has not been cleaned for days."),
        ("GARBAGE", "DEAD_ANIMAL", "Anonymous Caller", "9876500022",
         "Dead animal on the roadside",
         "A dead dog has been lying on the roadside since morning."),
        ("MISSED_PICKUP", "VEHICLE_NOT_ARRIVED", "Suresh P", "9876500033",
         "Collection vehicle did not arrive",
         "The vehicle has not come to our lane for two days."),
        ("OTHER", "SUGGESTION", "Lakshmi R", "9876500044",
         "Request for an extra bin",
         "Our street needs one more bin; the existing one fills up by noon."),
    ]

    # Tickets that also get citizen feedback, so the "With Feedback" tab and
    # the Feedback list are not empty. (index into PUBLIC, rating, solved)
    FEEDBACK = [(0, 4, True), (1, 2, False)]

    def _resolve(self, category_code, subcategory_code):
        category = ComplaintCategory.objects.filter(
            category_code=category_code, is_deleted=False
        ).select_related("default_priority").first()
        if not category:
            return None, None
        subcategory = (
            ComplaintSubcategory.objects.filter(
                category=category, subcategory_code=subcategory_code, is_deleted=False
            ).select_related("default_priority").first()
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
            source=source, title=fields.get("title"), is_deleted=False
        ).first()
        if existing:
            return existing, False

        ticket = ComplaintTicket.objects.create(
            category=category,
            subcategory=subcategory,
            priority=priority,
            status=status,
            source=source,
            **fields,
        )
        ComplaintStatusHistory.objects.create(
            ticket=ticket,
            from_status=None,
            to_status=status,
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
        public_source, _ = ComplaintSource.objects.get_or_create(
            source_code="PUBLIC_GRIEVANCE",
            defaults={
                "source_name": "Public Grievance",
                "is_active": True,
                "is_deleted": False,
            },
        )

        customers = list(
            CustomerCreation.objects.filter(is_deleted=False).select_related()[:len(self.INTERNAL)]
        )
        if not customers:
            self.log("---Sample tickets: no customers found, internal tickets skipped---")

        created_internal = 0
        for index, (cat_code, sub_code, title, description) in enumerate(self.INTERNAL):
            category, subcategory = self._resolve(cat_code, sub_code)
            if not category or index >= len(customers):
                continue
            customer = customers[index]
            _, created = self._create(
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
                company_id_id=customer.company_id_id,
                project_id_id=customer.project_id_id,
                zone_id=customer.zone_id,
                ward_id=customer.ward_id,
                location_text=getattr(customer, "address", "") or "",
            )
            created_internal += 1 if created else 0

        # Public grievances resolve tenancy the way the public viewset does:
        # from the chosen ward, falling back to the single active company.
        fallback = customers[0] if customers else None
        created_public = 0
        public_tickets = []
        for cat_code, sub_code, person, phone, title, description in self.PUBLIC:
            category, subcategory = self._resolve(cat_code, sub_code)
            if not category:
                continue
            ticket, created = self._create(
                category=category,
                subcategory=subcategory,
                status=submitted,
                priority=self._priority_for(category, subcategory),
                source=public_source,
                title=title,
                description=description,
                # No `customer` — an anonymous grievance is identified only by
                # the name/phone the citizen typed.
                profile_name=person,
                wa_phone=phone,
                company_id_id=getattr(fallback, "company_id_id", None),
                project_id_id=getattr(fallback, "project_id_id", None),
                zone_id=getattr(fallback, "zone_id", None),
                ward_id=getattr(fallback, "ward_id", None),
                idempotency_key=f"publicgrievance:seed-{phone}",
            )
            public_tickets.append(ticket)
            created_public += 1 if created else 0

        created_feedback = 0
        for index, rating, solved in self.FEEDBACK:
            if index >= len(public_tickets):
                continue
            ticket = public_tickets[index]
            _, created = ComplaintFeedback.objects.get_or_create(
                ticket=ticket,
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
            f"public +{created_public}, feedback +{created_feedback}; "
            f"total tickets now {ComplaintTicket.objects.filter(is_deleted=False).count()})---"
        )
