from django.db import models
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from app.models.user_creations.waste_collection_bluetooth import WasteType
from app.models.transport_masters.trip import Trip
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project
from app.models.masters.zone import Zone
from app.models.transport_masters.trip_definition import TripDefinition


def generate_zone_collection_id():
    return f"ZCOL-{generate_unique_id()}"


class ZoneCollection(BaseMaster):

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_zone_collection_id,
        editable=False
    )

    zone_id = models.ForeignKey(
        Zone,
        on_delete=models.PROTECT,
        related_name="zone_collections",
        db_column="zone_id"
    )

    waste_type_id = models.ForeignKey(
        WasteType,
        on_delete=models.PROTECT,
        related_name="zone_collections",
        db_column="waste_type_id"
    )

    zone_total_weight = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )

    ward_count = models.PositiveIntegerField(
        default=0
    )

    collection_date = models.DateField()

    trip_id = models.ForeignKey(
        TripDefinition,
        on_delete=models.PROTECT,
        related_name="zone_collections",
        db_column="trip_id"
    )

    company_id = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="zone_collections",
        db_column="company_id"
    )

    project_id = models.ForeignKey(
        Project,
        on_delete=models.PROTECT,
        related_name="zone_collections",
        db_column="project_id"
    )

    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("zone_id", "collection_date", "waste_type_id", "trip_id")
        ordering = ["-collection_date"]

    def __str__(self):
        return f"ZoneCollection({self.zone_id} | {self.collection_date} | {self.zone_total_weight}kg)"