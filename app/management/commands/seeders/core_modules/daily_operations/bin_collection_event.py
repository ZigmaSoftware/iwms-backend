from django.utils import timezone

from app.management.commands.seeders.base import BaseSeeder
from app.models.masters.panchayat import Panchayat
from app.models.schedule_masters.bin_collection_event import BinCollectionEvent
from app.models.schedule_masters.daily_trip_assignment import DailyTripAssignment
from app.models.schedule_masters.daily_trip_collection_point import DailyTripCollectionPoint
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project

TARGET_PER_PROJECT = 60

# Fallback GPS ring (Chennai area) used only when a project has no
# panchayat/zone lat-long of its own to anchor a ring around.
FALLBACK_GPS_SAMPLES = [
    (13.083000, 80.271000),
    (13.090000, 80.265000),
    (13.077000, 80.280000),
    (13.085000, 80.258000),
    (13.095000, 80.273000),
]

# Small deterministic offsets (degrees) applied around each project's own
# anchor coordinate so seeded driver GPS pins cluster near the real
# project location instead of a hardcoded city.
_RING_OFFSETS = [
    (0.0030, -0.0010), (0.0070, 0.0020), (-0.0060, 0.0030), (0.0020, -0.0070),
    (0.0090, 0.0000), (-0.0080, -0.0040), (0.0100, 0.0060), (-0.0020, 0.0090),
    (0.0060, -0.0080), (-0.0090, 0.0010), (0.0040, 0.0080), (-0.0050, -0.0060),
    (0.0110, -0.0030), (-0.0030, 0.0110), (0.0080, 0.0040),
]


def _project_gps_samples(project):
    """Small ring of GPS offsets around this project's own geography, so
    seeded events land near the real project location. Falls back to the
    Chennai constants when a project has no anchor to offset from — keeps
    the generic IWMS demo's existing visual behaviour unchanged."""
    anchor = (
        Panchayat.objects.filter(project_id=project, is_deleted=False)
        .exclude(latitude__isnull=True)
        .order_by("panchayat_name")
        .values_list("latitude", "longitude")
        .first()
    )
    if not anchor:
        return FALLBACK_GPS_SAMPLES

    base_lat, base_lon = float(anchor[0]), float(anchor[1])
    return [(base_lat + d_lat, base_lon + d_lon) for d_lat, d_lon in _RING_OFFSETS]


class BinCollectionEventSeeder(BaseSeeder):
    name = "bin_collection_event"

    def _seed_for_project(self, company, project, gps_samples):
        trip_cps = (
            DailyTripCollectionPoint.objects
            .filter(
                trip_assignment_id__company_id=company,
                trip_assignment_id__project_id=project,
                is_deleted=False,
            )
            .exclude(
                # Skip any DTCP that already has a BCE (OneToOneField enforces uniqueness)
                unique_id__in=BinCollectionEvent.objects.values_list(
                    "trip_collection_point_id", flat=True
                )
            )
            .exclude(trip_assignment_id__status=DailyTripAssignment.STATUS_CANCELLED)
            # Today is reserved for RetripDemoSeeder's own hand-curated
            # partial-completion scenarios — resolving all of today's stops
            # here would leave nothing pending for the Re-Trip demo to act on.
            .exclude(trip_assignment_id__trip_date=timezone.localdate())
            .select_related(
                "trip_assignment_id",
                "trip_assignment_id__company_id",
                "trip_assignment_id__project_id",
                "trip_assignment_id__panchayat_id",
                "trip_assignment_id__vehicle_id",
                "collection_point_id",
                "bin_id",
                "bin_id__wastetype_id",
            )
            .order_by("-trip_assignment_id__trip_date", "sequence")
        )

        available = list(trip_cps[:TARGET_PER_PROJECT])
        if not available:
            return 0, 0

        # Backfill: mark any DTCP as collected if a BCE already exists for it
        orphan_tcps = (
            DailyTripCollectionPoint.objects
            .filter(
                company_id=company,
                project_id=project,
                is_collected=False,
                is_deleted=False,
            )
            .select_related("bin_id")
        )
        backfilled_count = 0
        for tcp in orphan_tcps:
            bce = BinCollectionEvent.objects.filter(
                trip_collection_point_id=tcp
            ).first()
            if bce:
                tcp.mark_collected(
                    weight_kg=float(bce.collected_weight_kg),
                    collected_by=None,
                )
                backfilled_count += 1

        created_count = 0
        for i, trip_cp in enumerate(available):
            if not trip_cp.bin_id:
                continue

            assignment = trip_cp.trip_assignment_id
            bin_obj = trip_cp.bin_id
            weight_kg = round(float(bin_obj.bin_capacity or 240) * 0.65, 2)
            lat, lng = gps_samples[i % len(gps_samples)]

            BinCollectionEvent.objects.create(
                company_id=company,
                project_id=project,
                trip_assignment_id=assignment,
                trip_collection_point_id=trip_cp,
                collection_point_id=trip_cp.collection_point_id,
                bin_id=bin_obj,
                waste_type_id=getattr(bin_obj, "wastetype_id", None),
                vehicle_id=getattr(assignment, "vehicle_id", None),
                panchayat_id=assignment.panchayat_id,
                collected_weight_kg=weight_kg,
                driver_latitude=lat,
                driver_longitude=lng,
                notes="Seeded sample scan event",
            )

            if not trip_cp.is_collected:
                trip_cp.mark_collected(weight_kg=weight_kg, collected_by=None)

            created_count += 1

        return created_count, backfilled_count

    def run(self):
        project_pairs = (
            DailyTripCollectionPoint.objects
            .filter(is_deleted=False)
            .values_list(
                "trip_assignment_id__company_id", "trip_assignment_id__project_id"
            )
            .distinct()
        )

        if not project_pairs:
            self.log("No eligible DailyTripCollectionPoints found — skipping.")
            return

        total_created = 0
        total_backfilled = 0
        for company_id, project_id in project_pairs:
            if not company_id or not project_id:
                continue
            company = Company.objects.filter(unique_id=company_id).first()
            project = Project.objects.filter(unique_id=project_id).first()
            if not company or not project:
                continue

            gps_samples = _project_gps_samples(project)
            created, backfilled = self._seed_for_project(company, project, gps_samples)
            total_created += created
            total_backfilled += backfilled

        self.log(
            f"---BinCollectionEvent seeded | created={total_created} | backfilled={total_backfilled}---"
        )
