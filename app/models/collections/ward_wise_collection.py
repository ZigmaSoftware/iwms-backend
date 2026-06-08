from django.db import models

from app.models.masters.ward import Ward
from app.models.schedule_masters.collection_point import Collection_point
from app.models.schedule_masters.trip_plan import TripPlan
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project
from app.models.user_creations.waste_collection_bluetooth import WasteType
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id


def generate_ward_collection_id():
    return f"WCOL-{generate_unique_id()}"


class WardCollection(BaseMaster):
    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_ward_collection_id,
        editable=False,
    )
    ward_id = models.ForeignKey(
        Ward,
        on_delete=models.PROTECT,
        related_name="ward_collections",
        db_column="ward_id",
    )
    waste_type_id = models.ForeignKey(
        WasteType,
        on_delete=models.PROTECT,
        related_name="ward_collections",
        db_column="waste_type_id",
    )
    collection_point_id = models.ForeignKey(
        Collection_point,
        on_delete=models.PROTECT,
        related_name="ward_collections",
        db_column="collection_point_id",
        null=True,
        blank=True,
    )
    bin_collection_event_id = models.ForeignKey(
        "app.BinCollectionEvent",
        on_delete=models.PROTECT,
        related_name="ward_collections",
        db_column="bin_collection_event_id",
        null=True,
        blank=True,
    )
    ward_total_weight = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    collection_date = models.DateField()
    trip_id = models.ForeignKey(
        TripPlan,
        on_delete=models.PROTECT,
        related_name="ward_collections",
        db_column="trip_id",
    )
    company_id = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="ward_collections",
        db_column="company_id",
    )
    project_id = models.ForeignKey(
        Project,
        on_delete=models.PROTECT,
        related_name="ward_collections",
        db_column="project_id",
    )
    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-collection_date"]

    def __str__(self):
        return f"WardCollection({self.ward_id_id} | {self.collection_date} | {self.ward_total_weight}kg)"
