"""One Plant for Blue Planet / Greater Noida BP.

The real Blue Planet Integrated Waste Management Facility site (polygon
boundary + centroid point) so the Static Route Map and Daily Trip
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
PLANT_NAME = "Blue Planet Integrated Waste Management Facility"
# Real site boundary of the facility. Connected in order to draw the plant
# polygon; the plant's point location is the polygon's centroid.
BOUNDARY_COORDINATES = [
    {"latitude": 28.47645880924013, "longitude": 77.48256775824794},
    {"latitude": 28.47745264244425, "longitude": 77.48167913595746},
    {"latitude": 28.477017719240173, "longitude": 77.48090853086369},
    {"latitude": 28.476197241897378, "longitude": 77.47955345309401},
    {"latitude": 28.476029707545056, "longitude": 77.47970739900384},
    {"latitude": 28.47508195738197, "longitude": 77.48061242912536},
    {"latitude": 28.47451946330455, "longitude": 77.48107320560953},
    {"latitude": 28.4748436520733, "longitude": 77.48164345613377},
    {"latitude": 28.475226844216884, "longitude": 77.4826581422479},
    {"latitude": 28.47563534978962, "longitude": 77.4833639687721},
]
LATITUDE = round(sum(p["latitude"] for p in BOUNDARY_COORDINATES) / len(BOUNDARY_COORDINATES), 6)
LONGITUDE = round(sum(p["longitude"] for p in BOUNDARY_COORDINATES) / len(BOUNDARY_COORDINATES), 6)


class PlantGNOSeeder(BaseSeeder):
    name = "plant_gno"

    def run(self):
        company = Company.objects.filter(name=COMPANY_NAME, is_deleted=False).first()
        if not company:
            self.log(f"Company '{COMPANY_NAME}' not found — run the superadmin seeders first.")
            return

        project = Project.objects.filter(
            name=PROJECT_NAME, company_id=company.unique_id, is_deleted=False
        ).first()
        if not project:
            self.log(f"Project '{PROJECT_NAME}' not found under {COMPANY_NAME}.")
            return

        plant, created = Plant.objects.update_or_create(
            project_id=project.unique_id,
            defaults={
                "company_id": company.unique_id,
                "name": PLANT_NAME,
                "latitude": LATITUDE,
                "longitude": LONGITUDE,
                "boundary_coordinates": BOUNDARY_COORDINATES,
                "is_active": True,
                "is_deleted": False,
            },
        )
        self.log(
            f"---Plant {'created' if created else 'updated'}: "
            f"{plant.unique_id} [{PLANT_NAME}] for {PROJECT_NAME}---"
        )
