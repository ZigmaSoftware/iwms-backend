from app.management.commands.seeders.base import BaseSeeder

from app.models.transport_masters.trip import Trip
from app.models.transport_masters.vehicleCreation import VehicleCreation
from app.models.user_creations.stafftemplate import StaffTemplate
from app.models.user_creations.waste_collection_bluetooth import WasteType
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project


class TripSeeder(BaseSeeder):
    name = "trip"

    def run(self):

        # --------------------------------------------------
        # COMPANY & PROJECT
        # --------------------------------------------------
        company = Company.objects.get(name="IWMS")
        project = Project.objects.get(name=f"{company.name} Main Project")

        # --------------------------------------------------
        # REQUIRED DEPENDENCIES
        # --------------------------------------------------
        vehicle = VehicleCreation.objects.first()
        staff = StaffTemplate.objects.first()
        waste_type = WasteType.objects.first()

        if not all([vehicle, staff, waste_type]):
            self.log("Missing Vehicle / Staff / WasteType. Skipping Trip seed.")
            return

        # --------------------------------------------------
        # CREATE OR UPDATE TRIP
        # --------------------------------------------------
        trip, created = Trip.objects.update_or_create(
            vehicle_id=vehicle,
            staff_id=staff,
            waste_type_id=waste_type,
            is_completed=False,
            defaults={
                "company_id": company,
                "project_id": project,
                "is_active": True,
                "is_deleted": False,
            },
        )

        action = "Created" if created else "Updated"
        self.log(f"---Trip seeded: {trip.unique_id} ({action})---")