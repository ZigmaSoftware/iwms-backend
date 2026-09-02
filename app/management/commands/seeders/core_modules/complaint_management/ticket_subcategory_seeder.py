"""Complaint ticket sub-categories.

The one master in this group that never had a seeder — `sub_category_seeder.py`
seeds the LEGACY `app.models.grivences.SubCategory`, a different table used by
the pre-rename grievance screens, so `ComplaintSubcategory` stayed empty and
the Complaint Types "Sub Category" tab had nothing to list.

Sub-categories are optional refinements: only the categories where a citizen's
complaint genuinely splits several ways get them, and a sub-category's
`default_priority` is set only where it should override its parent's (e.g. a
blocked public toilet is more urgent than the category's default). Left unset,
the routing service falls back to the category priority.

Must run AFTER `ComplaintCategorySeeder` (each row needs its parent category)
and AFTER `ComplaintPrioritySeeder` — see TICKET_SEEDERS ordering in
`__init__.py`.
"""

from app.management.commands.seeders.base import BaseSeeder
from app.models.complaint_management import (
    ComplaintCategory,
    ComplaintPriority,
    ComplaintSubcategory,
)


class ComplaintSubcategorySeeder(BaseSeeder):
    name = "complaint_ticket_subcategory"

    # category_code -> [(subcategory_code, subcategory_name, priority_code|None, sort_order)]
    SUBCATEGORIES = {
        "MISSED_PICKUP": [
            ("WET_NOT_COLLECTED", "Wet waste not collected", None, 10),
            ("DRY_NOT_COLLECTED", "Dry waste not collected", None, 20),
            ("VEHICLE_NOT_ARRIVED", "Vehicle did not arrive", None, 30),
            ("PARTIAL_PICKUP", "Only part of the waste collected", "P3", 40),
        ],
        "BULK_WASTE": [
            ("CONSTRUCTION_DEBRIS", "Construction debris", None, 10),
            ("GARDEN_WASTE", "Garden / green waste", None, 20),
            ("FURNITURE", "Furniture / large items", None, 30),
            ("E_WASTE", "E-waste", None, 40),
        ],
        "WORKER_CONDUCT": [
            ("RUDE_BEHAVIOUR", "Rude behaviour", None, 10),
            ("NOT_IN_UNIFORM", "Not in uniform", "P4", 20),
            ("ABSENT_STAFF", "Staff did not turn up", None, 30),
            ("BRIBE_DEMAND", "Demanded extra payment", "P1", 40),
        ],
        "VEHICLE_ISSUE": [
            ("WASTE_SPILLAGE", "Waste spilling from vehicle", "P2", 10),
            ("VEHICLE_BREAKDOWN", "Vehicle broken down on route", None, 20),
            ("RASH_DRIVING", "Rash driving", "P2", 30),
            ("HORN_NUISANCE", "Excessive horn / noise", "P4", 40),
        ],
        "BILLING_QUERY": [
            ("WRONG_AMOUNT", "Incorrect amount charged", None, 10),
            ("RECEIPT_NOT_GIVEN", "Receipt not provided", None, 20),
            ("DOUBLE_CHARGED", "Charged twice", "P2", 30),
            ("REFUND_REQUEST", "Refund request", None, 40),
        ],
        "ADDRESS_CHANGE": [
            ("MOVED_HOUSE", "Moved to a new address", None, 10),
            ("WRONG_WARD", "Assigned to the wrong ward", None, 20),
            ("PROPERTY_TYPE", "Property type is incorrect", None, 30),
        ],
        "GARBAGE": [
            ("OPEN_DUMPING", "Open dumping / illegal dump", "P2", 10),
            ("BIN_OVERFLOW", "Bin overflowing", None, 20),
            ("BIN_DAMAGED", "Bin damaged or missing", "P3", 30),
            ("DEAD_ANIMAL", "Dead animal", "P1", 40),
        ],
        "PUBLIC_TOILET": [
            ("NOT_CLEANED", "Not cleaned", None, 10),
            ("NO_WATER", "No water supply", None, 20),
            ("BLOCKED_DRAIN", "Blocked drain / overflow", "P1", 30),
            ("NO_LIGHTING", "No lighting", "P4", 40),
        ],
        "OTHER": [
            ("GENERAL_QUERY", "General query", None, 10),
            ("SUGGESTION", "Suggestion / feedback", None, 20),
        ],
    }

    def run(self):
        total = 0
        skipped_categories = []

        for category_code, rows in self.SUBCATEGORIES.items():
            category = ComplaintCategory.objects.filter(
                category_code=category_code, is_deleted=False
            ).first()
            if not category:
                skipped_categories.append(category_code)
                continue

            for code, name, priority_code, sort_order in rows:
                priority = (
                    ComplaintPriority.objects.filter(priority_code=priority_code).first()
                    if priority_code
                    else None
                )
                # `unique_together = ("category", "subcategory_code")`, so the
                # lookup has to carry both — the same code under a different
                # category is a different row.
                ComplaintSubcategory.objects.get_or_create(
                    category=category,
                    subcategory_code=code,
                    defaults={
                        "subcategory_name": name,
                        "default_priority": priority,
                        "sort_order": sort_order,
                        "is_active": True,
                        "is_deleted": False,
                    },
                )
                total += 1

        if skipped_categories:
            self.log(
                "---Complaint subcategories: skipped "
                f"{', '.join(skipped_categories)} (category not seeded)---"
            )
        self.log(f"---Complaint ticket subcategories seeded ({total} records)---")
