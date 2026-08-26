"""One DumpYard for Blue Planet / Palakkad BP — the same company/project
`DriverWetDryBinTripsSeeder` seeds driver_user's Wet/Dry bin trips under.

Placed a short drive east of both waste-stream collection point clusters
(see driver_wet_dry_bin_trips.py's WET_POINTS/DRY_POINTS anchors at
10.7867/76.6548 and 10.7950/76.6650) so the Static Route Map has a real,
visually sensible "last stop" to render for every seeded trip in that
project — never inserted into DailyTripCollectionPoint (see
DumpYardViewSet's docstring): the map appends it to route geometry at
render time only.

Idempotent: update_or_create keyed on project (DumpYard.project_id is
unique — one dump yard per project), safe to re-run.
"""

from app.management.commands.seeders.base import BaseSeeder

from app.models.schedule_masters.dump_yard import DumpYard
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project

COMPANY_NAME = "Blue Planet"
PROJECT_NAME = "Palakkad BP"
DUMP_YARD_NAME = "Palakkad Municipal Waste Processing Yard"
LATITUDE = "10.7735"
LONGITUDE = "76.6790"


class DumpYardSeeder(BaseSeeder):
    name = "dump_yard"

    def run(self):
        company = Company.objects.filter(name=COMPANY_NAME, is_deleted=False).first()
        if not company:
            self.log(f"Company '{COMPANY_NAME}' not found — run the superadmin seeders first.")
            return

        project = Project.objects.filter(
            name=PROJECT_NAME, company_id=company, is_deleted=False
        ).first()
        if not project:
            self.log(f"Project '{PROJECT_NAME}' not found under {COMPANY_NAME}.")
            return

        dump_yard, created = DumpYard.objects.update_or_create(
            project_id=project,
            defaults={
                "company_id": company,
                "name": DUMP_YARD_NAME,
                "latitude": LATITUDE,
                "longitude": LONGITUDE,
                "is_active": True,
                "is_deleted": False,
            },
        )
        self.log(
            f"---Dump Yard {'created' if created else 'updated'}: "
            f"{dump_yard.unique_id} [{DUMP_YARD_NAME}] for {PROJECT_NAME}---"
        )
