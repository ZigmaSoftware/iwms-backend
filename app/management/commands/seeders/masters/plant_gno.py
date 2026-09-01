"""One Plant for Blue Planet / Greater Noida BP.

Placed a short drive from the GNO collection point cluster (CP-GNO-01/02/03,
clustered around 28.47/77.51) so the Static Route Map and Daily Trip
Tracking have a real, visually sensible route endpoint for every seeded
trip in that project — never inserted into DailyTripCollectionPoint (see
PlantViewSet's docstring): the map appends it to route geometry at
render time only.

Idempotent: update_or_create keyed on project (Plant.project_id is
unique — one plant per project), safe to re-run.
"""

from app.management.commands.seeders.base import BaseSeeder

from app.models.masters.plant import Plant
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project

COMPANY_NAME = "Blue Planet"
PROJECT_NAME = "Blue Planet Integrated Waste Management"
PLANT_NAME = "Greater Noida Municipal Waste Processing Yard"
LATITUDE = "28.4900"
LONGITUDE = "77.5350"


class PlantGNOSeeder(BaseSeeder):
    name = "plant_gno"

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

        plant, created = Plant.objects.update_or_create(
            project_id=project,
            defaults={
                "company_id": company,
                "name": PLANT_NAME,
                "latitude": LATITUDE,
                "longitude": LONGITUDE,
                "is_active": True,
                "is_deleted": False,
            },
        )
        self.log(
            f"---Plant {'created' if created else 'updated'}: "
            f"{plant.unique_id} [{PLANT_NAME}] for {PROJECT_NAME}---"
        )
