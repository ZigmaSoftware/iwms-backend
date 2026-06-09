from django.db import models

from app.models.assets.bins import Bins
from app.models.schedule_masters.collection_point import Collection_point
from app.models.schedule_masters.trip_plan import TripPlan
from app.models.masters.panchayat import Panchayat
from app.models.masters.ward import Ward
from app.models.masters.zone import Zone
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id


def generate_tpcp_id():
    return f"TPCP-{generate_unique_id()}"


class TripPlanCollectionPoint(BaseMaster):
    """Master stop list for a TripPlan."""

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_tpcp_id,
        editable=False,
    )
    company_id = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="trip_plan_collection_points",
        db_column="company_id",
        null=True,
        blank=True,
    )
    project_id = models.ForeignKey(
        Project,
        on_delete=models.PROTECT,
        related_name="trip_plan_collection_points",
        db_column="project_id",
        null=True,
        blank=True,
    )

    trip_plan_id = models.ForeignKey(
        TripPlan,
        on_delete=models.CASCADE,
        to_field="unique_id",
        related_name="plan_collection_points",
        db_column="trip_plan_id",
    )
    collection_point_id = models.ForeignKey(
        Collection_point,
        on_delete=models.PROTECT,
        to_field="unique_id",
        related_name="trip_plan_cps",
        db_column="collection_point_id",
    )
    zone_id = models.ForeignKey(
        Zone,
        on_delete=models.PROTECT,
        related_name="trip_plan_collection_points",
        db_column="zone_id",
        null=True,
        blank=True,
    )
    ward_id = models.ForeignKey(
        Ward,
        on_delete=models.PROTECT,
        related_name="trip_plan_collection_points",
        db_column="ward_id",
        null=True,
        blank=True,
    )
    panchayat_id = models.ForeignKey(
        Panchayat,
        on_delete=models.PROTECT,
        related_name="trip_plan_collection_points",
        db_column="panchayat_id",
        null=True,
        blank=True,
    )
    bin_id = models.ForeignKey(
        Bins,
        on_delete=models.PROTECT,
        to_field="unique_id",
        related_name="trip_plan_cps",
        db_column="bin_id",
    )
    sequence = models.PositiveIntegerField(
        help_text="Visit order within the route.",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Inactive stops are skipped during auto-assignment.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["trip_plan_id", "sequence"]
        indexes = [
            models.Index(fields=["trip_plan_id", "is_active"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["trip_plan_id", "collection_point_id"],
                name="uniq_cp_per_trip_plan",
            ),
            models.UniqueConstraint(
                fields=["trip_plan_id", "sequence"],
                name="uniq_sequence_per_trip_plan",
            ),
        ]

    def save(self, *args, **kwargs):
        if self.trip_plan_id_id and not self.company_id_id:
            plan = self.trip_plan_id
            self.company_id = plan.company_id
            self.project_id = plan.project_id
        if self.collection_point_id_id:
            collection_point = self.collection_point_id
            self.panchayat_id = collection_point.panchayat_id
            self.ward_id = collection_point.ward_id
            self.zone_id = (
                collection_point.ward_id.zone_id
                if collection_point.ward_id_id
                else None
            )
        super().save(*args, **kwargs)

    def __str__(self):
        return (
            f"{self.trip_plan_id_id} -> "
            f"{self.collection_point_id_id} (seq {self.sequence})"
        )
