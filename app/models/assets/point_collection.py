from django.db import models
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from app.models.assets.collection_point import Collection_point
from app.models.user_creations.waste_collection_bluetooth import WasteType
from app.models.transport_masters.trip_definition import TripDefinition
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project
from app.models.user_creations.stafftemplate import StaffTemplate
from app.models.assets.bins import Bins
from app.models.masters.panchayat import Panchayat
from app.models.masters.city import City
from app.models.masters.district import District


def generate_point_collection_id():
    return f"PC-{generate_unique_id()}"


class PointCollection(BaseMaster):

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_point_collection_id,
        editable=False
    )

    bin_id = models.ForeignKey(
        Bins,
        on_delete=models.PROTECT,
        related_name="point_collections",
        db_column="bin_id"
    )

    waste_type_id = models.ForeignKey(
        WasteType,
        on_delete=models.PROTECT,
        related_name="point_collections",
        db_column="waste_type_id"
    )

    collection_point_id = models.ForeignKey(
        Collection_point,
        on_delete=models.PROTECT,
        related_name="point_collections",
        db_column="collection_point_id"
    )

    district_id = models.ForeignKey(
        District,
        on_delete=models.PROTECT,
        related_name="point_collections",
        db_column="district_id",
        null=True,
        blank=True
    )

    city_id = models.ForeignKey(
        City,
        on_delete=models.PROTECT,
        related_name="point_collections",
        db_column="city_id",
        null=True,
        blank=True
    )

    point_collection_weight = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    collection_date = models.DateField()
    collection_time = models.TimeField()

    trip_id = models.ForeignKey(
        TripDefinition,
        on_delete=models.PROTECT,
        related_name="point_collections",
        db_column="trip_id"
    )

    company_id = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="point_collections",
        db_column="company_id"
    )

    project_id = models.ForeignKey(
        Project,
        on_delete=models.PROTECT,
        related_name="point_collections",
        db_column="project_id"
    )


    is_collected = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


    def save(self, *args, **kwargs):
        if self.collection_point_id:
            self.district_id = self.collection_point_id.district_id
            self.city_id = self.collection_point_id.city_id

        if self.point_collection_weight and self.point_collection_weight > 0:
            self.is_collected = True
        super().save(*args, **kwargs)
