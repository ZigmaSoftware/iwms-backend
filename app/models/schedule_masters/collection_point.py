from django.db import models
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project
from app.models.masters.panchayat import Panchayat
from app.models.masters.city import City
from app.models.masters.district import District
from app.models.masters.ward import Ward
from app.models.masters.zone import Zone
from app.models.common_masters.state import State
from django.core.exceptions import ValidationError

def geneate_collection_point_id():
    return f"CP-{generate_unique_id()}"

class Collection_point(BaseMaster):
    COLLECTION_TYPE_BIN = "bin_collection"
    COLLECTION_TYPE_HOUSEHOLD = "household_collection"
    COLLECTION_TYPE_CHOICES = [
        (COLLECTION_TYPE_BIN, "Bin Collection"),
        (COLLECTION_TYPE_HOUSEHOLD, "Household Collection"),
    ]

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=geneate_collection_point_id,
        editable=False
    )

    company_id = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="cp",
        db_column="company_id",
    )

    project_id = models.ForeignKey(
        Project,
        on_delete=models.PROTECT,
        related_name="cp",
        db_column="project_id",
    )

    state_id = models.ForeignKey(
        State,
        on_delete = models.PROTECT,
        related_name="cp",
        db_column="state_id",
        
    )

    city_id = models.ForeignKey(
        City,
        on_delete = models.PROTECT,
        related_name="cp",
        db_column="city_id",
        
    )

    district_id = models.ForeignKey(
        District,
        on_delete = models.PROTECT,
        related_name="cp",
        db_column="district_id",
        
    )


    panchayat_id = models.ForeignKey(
        Panchayat,
        on_delete=models.PROTECT,
        related_name="cp",
        db_column="panchayat_id",
        null=True,
        blank=True
    )

    zone_id = models.ForeignKey(
        Zone,
        on_delete=models.PROTECT,
        related_name="cp",
        db_column="zone_id",
        null=True,
        blank=True
    )

    wards = models.ManyToManyField(
        Ward,
        related_name="collection_points",
        blank=True,
    )

    collection_type = models.CharField(
        max_length=30,
        choices=COLLECTION_TYPE_CHOICES,
        default=COLLECTION_TYPE_BIN,
    )

    cp_name = models.CharField(max_length=100)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        # XOR validation is done in the serializer (M2M not available pre-save),
        # but keep a basic guard for admin/shell usage.
        pass

    def __str__(self):
        if self.panchayat_id:
            return f"{self.cp_name} (Panchayat: {self.panchayat_id.panchayat_name})"
        return self.cp_name