from datetime import time

from django.utils import timezone

from app.management.commands.seeders.base import BaseSeeder
from app.models.masters.panchayat import Panchayat
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project
from app.models.transport_masters.daily_trip_assignment import DailyTripAssignment
from app.models.transport_masters.trip_definition import TripDefinition
from app.models.transport_masters.vehicleCreation import VehicleCreation
from app.models.user_creations.stafftemplate import StaffTemplate
from app.models.user_creations.waste_collection_bluetooth import WasteType


class DailyTripAssignmentSeeder(BaseSeeder):
    name = "daily_trip_assignment"

    def _resolve_staff_template(self, driver_username, operator_username):
        return (
            StaffTemplate.objects
            .filter(
                driver_id__username__iexact=driver_username,
                operator_id__username__iexact=operator_username,
            )
            .order_by("created_at")
            .first()
        )

    def _resolve_waste_type(self, name):
        return WasteType.objects.filter(
            waste_type_name__iexact=name, is_deleted=False
        ).first()

    def _resolve_vehicle(self, vehicle_no):
        return VehicleCreation.objects.filter(vehicle_no=vehicle_no).first()

    def run(self):
        company = Company.objects.filter(name="IWMS").first()
        project = (
            Project.objects.filter(name=f"{company.name} Main Project").first()
            if company
            else None
        )
        if not company or not project:
            self.log("Missing Company/Project — aborting.")
            return

        panchayat = Panchayat.objects.filter(
            panchayat_name="Panchayat 1",
            company_id=company,
            project_id=project,
        ).first()
        if not panchayat:
            self.log("Panchayat 1 not found — aborting.")
            return

        trip_definition = TripDefinition.objects.order_by("created_at").first()
        if not trip_definition:
            self.log("No TripDefinition seeded — aborting.")
            return

        today = timezone.localdate()

        trips = [
            {
                "driver": "driver_user",
                "operator": "operator_user",
                "waste_type_name": "Wet Waste",
                "vehicle_no": "WET-VEHICLE-01",
                "scheduled_time": time(7, 0),
            },
            {
                "driver": "driver2_user",
                "operator": "operator2_user",
                "waste_type_name": "Dry Waste",
                "vehicle_no": "DRY-VEHICLE-01",
                "scheduled_time": time(7, 30),
            },
        ]

        created_count = 0
        skipped = 0
        for trip in trips:
            staff_template = self._resolve_staff_template(
                trip["driver"], trip["operator"]
            )
            waste_type = self._resolve_waste_type(trip["waste_type_name"])
            vehicle = self._resolve_vehicle(trip["vehicle_no"])

            if not staff_template or not waste_type or not vehicle:
                self.log(
                    f"DailyTripAssignment skipped: "
                    f"template={staff_template} waste={waste_type} vehicle={vehicle}"
                )
                skipped += 1
                continue

            existing = DailyTripAssignment.objects.filter(
                trip_date=today,
                staff_template_id=staff_template,
                panchayat_id=panchayat,
                waste_type_id=waste_type,
                is_deleted=False,
            ).first()
            if existing:
                if not existing.vehicle_id_id:
                    existing.vehicle_id = vehicle
                    existing.save(update_fields=["vehicle_id", "updated_at"])
                continue

            DailyTripAssignment.objects.create(
                company_id=company,
                project_id=project,
                trip_definition_id=trip_definition,
                staff_template_id=staff_template,
                panchayat_id=panchayat,
                collection_point_id=None,
                waste_type_id=waste_type,
                vehicle_id=vehicle,
                trip_date=today,
                scheduled_time=trip["scheduled_time"],
                status=DailyTripAssignment.STATUS_SCHEDULED,
                approval_status=DailyTripAssignment.APPROVAL_APPROVED,
            )
            created_count += 1

        self.log(
            f"---DailyTripAssignment seeded | created={created_count} | skipped={skipped}---"
        )
