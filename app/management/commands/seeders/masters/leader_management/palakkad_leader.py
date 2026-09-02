"""Palakkad panchayat (PLB) leader login + trip data for their dashboard.

The localbody portal (`LocalBodyDashboardViewSet`, route `localbody/dashboard`)
reads `DailyTripLog` rows filtered by the leader's own `panchayat_id`. Without
logs for that panchayat the portal authenticates fine and then shows an empty
dashboard, so this seeds both halves together: the login, and enough trip logs
behind it for the monthly comparison, daily breakdown and KPIs to render.

Logs are spread across the current and two previous months so the monthly
trend chart has more than one point, and across wet/dry/mixed waste so the
waste-type breakdown is not a single bar.

`DailyTripLog.trip_assignment_id` is a required FK, and `save()` runs
`autofill_from_assignment`, which copies company/project/panchayat FROM that
assignment. So a log cannot simply be stamped with a panchayat — it needs an
assignment that already carries one. This seeder therefore creates one trip
plan and one assignment per PAL panchayat, then hangs the logs off those.

Must run AFTER the masters seed group (needs the PAL panchayats and their
collection points) and after `waste-types`.
"""

import random
from datetime import timedelta

from django.utils import timezone

from app.management.commands.seeders.base import BaseSeeder
from app.models.masters.panchayat import Panchayat
from app.models.masters.panchayat_leader_login import PanchayatLeaderLogin
from app.models.schedule_masters.collection_point import Collection_point
from app.models.schedule_masters.daily_trip_assignment import DailyTripAssignment
from app.models.schedule_masters.daily_trip_log import DailyTripLog
from app.models.schedule_masters.trip_plan import TripPlan
from app.models.staff_creations.waste_collection_bluetooth import WasteType
from app.models.superadmin_masters.project import Project


class PalakkadLeaderSeeder(BaseSeeder):
    name = "palakkad_plb_leader"

    PROJECT_NAME = "Palakkad BP"
    PASSWORD = "Leader123"

    # (panchayat_name, username, leader_name, email)
    LEADERS = [
        ("PAL PLB 1", "pal_plb1_leader", "Ravi Shankar", "pal.plb1.leader@example.com"),
        ("PAL PLB 2", "pal_plb2_leader", "Latha Devi", "pal.plb2.leader@example.com"),
        ("PAL PLB 3", "pal_plb3_leader", "Mohan Das", "pal.plb3.leader@example.com"),
    ]

    # Trip logs per panchayat, spread over this many days back.
    DAYS_OF_HISTORY = 75
    LOGS_PER_PANCHAYAT = 24

    def _waste_types(self):
        """One waste type per name, so the breakdown has three distinct bars.

        The table holds duplicate names (several rows each for Wet/Dry/Mixed),
        which would otherwise split one waste stream across several chart
        entries.
        """
        seen = {}
        for waste in WasteType.objects.filter(is_deleted=False).order_by("unique_id"):
            name = (waste.waste_type_name or "").strip()
            if name and name not in seen:
                seen[name] = waste
        return list(seen.values())

    def run(self):
        project = Project.objects.filter(
            name=self.PROJECT_NAME, is_deleted=False
        ).select_related("company_id").first()
        if not project:
            self.log(f"Project '{self.PROJECT_NAME}' not found — skipping.")
            return
        company = project.company_id

        waste_types = self._waste_types()
        if not waste_types:
            self.log("No waste types seeded — skipping.")
            return

        # A fixed seed keeps the numbers stable across re-runs, so a
        # screenshot or a manual check does not change every time.
        rng = random.Random(20260902)
        today = timezone.localdate()

        created_leaders = 0
        created_logs = 0
        created_plans_local = []
        summary = []

        for panchayat_name, username, leader_name, email in self.LEADERS:
            panchayat = Panchayat.objects.filter(
                panchayat_name=panchayat_name, is_deleted=False
            ).first()
            if not panchayat:
                self.log(f"Panchayat '{panchayat_name}' not found — skipped.")
                continue

            leader, created = PanchayatLeaderLogin.objects.get_or_create(
                username=username,
                defaults={
                    "panchayat_id": panchayat,
                    "company_id": company,
                    "project_id": project,
                    "password": self.PASSWORD,
                    "leader_name": leader_name,
                    "email": email,
                    "is_active": True,
                    "is_deleted": False,
                },
            )
            if not created:
                leader.panchayat_id = panchayat
                leader.company_id = company
                leader.project_id = project
                leader.password = self.PASSWORD
                leader.leader_name = leader_name
                leader.email = email
                leader.is_active = True
                leader.is_deleted = False
                leader.save()
            created_leaders += 1 if created else 0

            points = list(
                Collection_point.objects.filter(
                    panchayat_id=panchayat, is_deleted=False
                )[:6]
            )

            # A plan scoped to this panchayat, reusing an existing Palakkad
            # plan's staff template so the assignment has a valid crew.
            template_source = TripPlan.objects.filter(
                project_id=project, staff_template_id__isnull=False, is_deleted=False
            ).first()
            if not template_source:
                self.log("No Palakkad trip plan with a staff template — skipping logs.")
                continue

            plan, _ = TripPlan.objects.get_or_create(
                display_code=f"PAL-PLB-{panchayat.panchayat_name.split()[-1]}-LEADER",
                defaults={
                    "company_id": company,
                    "project_id": project,
                    "panchayat_id": panchayat,
                    "staff_template_id": template_source.staff_template_id,
                    "vehicle_id": template_source.vehicle_id,
                    "collection_type": template_source.collection_type,
                    "scheduled_time": template_source.scheduled_time,
                    "is_active": True,
                    "is_deleted": False,
                },
            )
            if plan.panchayat_id_id != panchayat.unique_id:
                plan.panchayat_id = panchayat
                plan.save(update_fields=["panchayat_id"])
            created_plans_local.append(plan.display_code)

            existing = DailyTripLog.objects.filter(
                panchayat_id=panchayat.unique_id, is_deleted=False
            ).count()
            to_create = max(0, self.LOGS_PER_PANCHAYAT - existing)

            for index in range(to_create):
                # Spread across the history window so the monthly trend has
                # several months and the daily view has several days.
                day = today - timedelta(
                    days=rng.randint(0, self.DAYS_OF_HISTORY)
                )
                # One assignment per (plan, date): the log's FK requires it,
                # and `autofill_from_assignment` reads the panchayat off it.
                assignment, _ = DailyTripAssignment.objects.get_or_create(
                    trip_plan_id=plan,
                    trip_date=day,
                    defaults={
                        "company_id": company,
                        "project_id": project,
                        "panchayat_id": panchayat,
                        "staff_template_id": plan.staff_template_id,
                        "scheduled_time": plan.scheduled_time
                        or template_source.scheduled_time,
                        "is_active": True,
                        "is_deleted": False,
                    },
                )
                if assignment.panchayat_id_id != panchayat.unique_id:
                    assignment.panchayat_id = panchayat
                    assignment.save(update_fields=["panchayat_id"])

                waste = waste_types[index % len(waste_types)]
                point = points[index % len(points)] if points else None
                collected = rng.randint(120, 900)
                DailyTripLog.objects.create(
                    trip_assignment_id=assignment,
                    collection_point_id=point,
                    waste_type_id=waste,
                    trip_date=day,
                    collected_weight_kg=collected,
                    household_collected_weight_kg=rng.randint(20, collected),
                    log_status="Verified",
                    remarks="Seeded sample trip log",
                    is_active=True,
                    is_deleted=False,
                )
                created_logs += 1

            total = DailyTripLog.objects.filter(
                panchayat_id=panchayat.unique_id, is_deleted=False
            ).count()
            summary.append(f"{username} -> {panchayat_name} ({total} logs)")

        # Point the Palakkad trip plans at a panchayat so the plan list reads
        # the same way as the dashboard; most were seeded without one.
        first = Panchayat.objects.filter(
            panchayat_name=self.LEADERS[0][0], is_deleted=False
        ).first()
        plans_fixed = 0
        if first:
            plans_fixed = TripPlan.objects.filter(
                project_id=project, panchayat_id__isnull=True, is_deleted=False
            ).update(panchayat_id=first)

        self.log(
            f"---Palakkad PLB leaders seeded (+{created_leaders} new, "
            f"password {self.PASSWORD}); +{created_logs} trip log(s); "
            f"{plans_fixed} trip plan(s) given a panchayat---"
        )
        for line in summary:
            self.log(f"    {line}")
