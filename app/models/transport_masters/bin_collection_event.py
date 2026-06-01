from django.db import models

from app.models.assets.bins import Bins
from app.models.assets.collection_point import Collection_point
from app.models.masters.panchayat import Panchayat
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project
from app.models.transport_masters.daily_trip_assignment import DailyTripAssignment
from app.models.transport_masters.daily_trip_collection_point import (
    DailyTripCollectionPoint,
)
from app.models.transport_masters.vehicleCreation import VehicleCreation
from app.models.user_creations.staffcreation import Staffcreation
from app.models.user_creations.waste_collection_bluetooth import WasteType
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id


def generate_bin_collection_event_id():
    return f"BCE-{generate_unique_id(length=10)}"


class BinCollectionEvent(BaseMaster):
    """One row per operator scan-and-submit. Permanent audit ledger."""

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_bin_collection_event_id,
        editable=False,
    )

    company_id = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        db_column="company_id",
        related_name="bin_collection_events",
    )
    project_id = models.ForeignKey(
        Project,
        on_delete=models.PROTECT,
        db_column="project_id",
        related_name="bin_collection_events",
    )

    trip_assignment_id = models.ForeignKey(
        DailyTripAssignment,
        on_delete=models.PROTECT,
        db_column="trip_assignment_id",
        to_field="unique_id",
        related_name="bin_collection_events",
    )
    trip_collection_point_id = models.OneToOneField(
        DailyTripCollectionPoint,
        on_delete=models.PROTECT,
        db_column="trip_collection_point_id",
        to_field="unique_id",
        related_name="bin_collection_event",
    )

    collection_point_id = models.ForeignKey(
        Collection_point,
        on_delete=models.PROTECT,
        db_column="collection_point_id",
        to_field="unique_id",
        related_name="bin_collection_events",
    )
    bin_id = models.ForeignKey(
        Bins,
        on_delete=models.PROTECT,
        db_column="bin_id",
        to_field="unique_id",
        related_name="bin_collection_events",
    )
    panchayat_id = models.ForeignKey(
        Panchayat,
        on_delete=models.PROTECT,
        db_column="panchayat_id",
        to_field="unique_id",
        related_name="bin_collection_events",
    )
    waste_type_id = models.ForeignKey(
        WasteType,
        on_delete=models.PROTECT,
        db_column="waste_type_id",
        to_field="unique_id",
        related_name="bin_collection_events",
    )
    vehicle_id = models.ForeignKey(
        VehicleCreation,
        on_delete=models.PROTECT,
        db_column="vehicle_id",
        to_field="unique_id",
        related_name="bin_collection_events",
        null=True,
        blank=True,
    )

    operator_id = models.ForeignKey(
        Staffcreation,
        on_delete=models.PROTECT,
        db_column="operator_id",
        to_field="staff_unique_id",
        related_name="bin_collection_events_as_operator",
    )
    driver_id = models.ForeignKey(
        Staffcreation,
        on_delete=models.SET_NULL,
        db_column="driver_id",
        to_field="staff_unique_id",
        related_name="bin_collection_events_as_driver",
        null=True,
        blank=True,
    )

    collected_weight_kg = models.DecimalField(max_digits=10, decimal_places=2)
    scanned_qr = models.CharField(max_length=100)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    notes = models.TextField(null=True, blank=True)

    event_at = models.DateTimeField(auto_now_add=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-event_at"]
        indexes = [
            models.Index(fields=["trip_assignment_id", "event_at"]),
            models.Index(fields=["operator_id", "event_at"]),
            models.Index(fields=["panchayat_id", "event_at"]),
        ]

    def __str__(self):
        return self.unique_id
