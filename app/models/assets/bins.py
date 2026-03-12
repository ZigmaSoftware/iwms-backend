from django.db import models
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project
from app.models.masters.panchayat import Panchayat
from app.models.assets.collection_point import Collection_point
from app.models.user_creations.waste_collection_bluetooth import WasteType


def generate_bin_id():
    return f"BIN-{generate_unique_id()}"


class BinType(models.TextChoices):
    SMALL = "small", "Small"
    MEDIUM = "medium", "Medium"
    LARGE = "large", "Large"
   

class Bins(BaseMaster):

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_bin_id,
        editable=False
    )

    company_id = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="bin",
        db_column="company_id",
    )

    project_id = models.ForeignKey(
        Project,
        on_delete=models.PROTECT,
        related_name="bin",
        db_column="project_id",
    )


    collection_point_id = models.ForeignKey(
        Collection_point,
        on_delete=models.PROTECT,
        related_name="bin",
        db_column="collection_point_id"
    )

    wastetype_id = models.ForeignKey(
        WasteType,  
        on_delete=models.PROTECT,
        related_name="bin",
        db_column="wastetype_id"
    )

    bin_name = models.CharField(max_length=100)
    bin_capacity = models.IntegerField()
    bin_type = models.CharField(max_length=10, choices=BinType.choices)
    bin_image = models.CharField(max_length=100)
    bin_qr = models.CharField(max_length=100)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

