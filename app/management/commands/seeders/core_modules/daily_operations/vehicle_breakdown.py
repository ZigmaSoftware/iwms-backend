from datetime import time
from decimal import Decimal

from django.utils import timezone

from app.management.commands.seeders.base import BaseSeeder
from app.models.schedule_masters.daily_trip_assignment import DailyTripAssignment
from app.models.schedule_masters.vehicle_breakdown import VehicleBreakdown
from app.models.transport_masters.vehicleCreation import VehicleCreation
from app.models.user_creations.staffcreation import Staffcreation

# Chennai-area GPS samples, so breakdown pins land in the same demo area as
# the rest of the daily-operations seed data.
GPS_SAMPLES = [
    (13.083000, 80.271000),
    (13.090000, 80.265000),
    (13.077000, 80.280000),
    (13.085000, 80.258000),
    (13.095000, 80.273000),
]

BREAKDOWN_ROADS = [
    "Anna Salai",
    "GST Road",
    "OMR",
    "ECR",
    "Poonamallee High Road",
]


class VehicleBreakdownSeeder(BaseSeeder):
    name = "vehicle_breakdown"

    # (reason, status, approval_status)
    SCENARIOS = [
        ("FLAT_TYRE", VehicleBreakdown.STATUS_REPLACEMENT_ARRANGED, VehicleBreakdown.APPROVAL_APPROVED),
        ("ENGINE_FAILURE", VehicleBreakdown.STATUS_REPORTED, VehicleBreakdown.APPROVAL_PENDING),
        ("ACCIDENT", VehicleBreakdown.STATUS_REJECTED, VehicleBreakdown.APPROVAL_REJECTED),
        ("OVERHEATING", VehicleBreakdown.STATUS_REPORTED, VehicleBreakdown.APPROVAL_PENDING),
        ("ELECTRICAL", VehicleBreakdown.STATUS_REPLACEMENT_ARRANGED, VehicleBreakdown.APPROVAL_APPROVED),
    ]

    def run(self):
        assignments = list(
            DailyTripAssignment.objects.filter(is_deleted=False)
            .exclude(status=DailyTripAssignment.STATUS_CANCELLED)
            .exclude(vehicle_breakdown__isnull=False)
            .select_related("company_id", "project_id", "vehicle_id", "trip_plan_id__vehicle_id", "panchayat_id")
            .order_by("-trip_date", "-scheduled_time")[: len(self.SCENARIOS)]
        )
        if not assignments:
            self.log("VehicleBreakdownSeeder skipped (no assignments without a breakdown).")
            return

        vehicles = list(VehicleCreation.objects.filter(is_deleted=False).order_by("vehicle_no"))
        staff = list(Staffcreation.objects.filter(is_deleted=False).order_by("staff_unique_id")[:4])
        if len(vehicles) < 2 or len(staff) < 2:
            self.log("VehicleBreakdownSeeder skipped (need at least 2 vehicles and 2 staff).")
            return

        approver = staff[0]
        created = 0

        for idx, assignment in enumerate(assignments):
            reason, status, approval = self.SCENARIOS[idx % len(self.SCENARIOS)]
            broken_vehicle = assignment.vehicle_id or getattr(assignment.trip_plan_id, "vehicle_id", None)
            if not broken_vehicle:
                continue
            replacement = next(
                (v for v in vehicles if v.unique_id != broken_vehicle.unique_id), None
            )
            if not replacement:
                continue

            lat, lon = GPS_SAMPLES[idx % len(GPS_SAMPLES)]
            road = BREAKDOWN_ROADS[idx % len(BREAKDOWN_ROADS)]
            panchayat_name = getattr(assignment.panchayat_id, "panchayat_name", None)
            location = f"{road} km {12 + idx}" + (f", {panchayat_name}" if panchayat_name else "")

            VehicleBreakdown.objects.create(
                company_id=assignment.company_id,
                project_id=assignment.project_id,
                trip_assignment_id=assignment,
                breakdown_vehicle_id=broken_vehicle,
                replacement_vehicle_id=replacement,
                replacement_driver_id=staff[idx % len(staff)],
                replacement_operator_id=staff[(idx + 1) % len(staff)],
                breakdown_time=time(8 + (idx % 10), 15),
                breakdown_lat=Decimal(str(lat)),
                breakdown_lng=Decimal(str(lon)),
                breakdown_location=location,
                collected_weight_before_breakdown_kg=Decimal("120.500") + Decimal(idx * 40),
                breakdown_reason=reason,
                breakdown_remarks=f"Seeder demo breakdown ({reason.replace('_', ' ').title()}).",
                status=status,
                approval_status=approval,
                approved_by=approver if approval == VehicleBreakdown.APPROVAL_APPROVED else None,
                approved_at=timezone.now() if approval == VehicleBreakdown.APPROVAL_APPROVED else None,
                rejection_remarks="Replacement vehicle unavailable." if approval == VehicleBreakdown.APPROVAL_REJECTED else None,
            )
            created += 1

        self.log(f"---Vehicle breakdowns seeded ({created} created)---")
