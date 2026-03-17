from django.db import models
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project
from app.models.masters.city import City
from app.models.masters.district import District
from app.models.common_masters.state import State
from app.models.masters.hierarchy import AdministrativeHierarchy
from app.models.masters.areatype import AreaType

def geneate_panchayat_id():
    return f"PANCHAYAT-{generate_unique_id()}"

class GeoFencingType(models.TextChoices):
    POLYGON = "polygon", "Polygon"
    CIRCLE = "circle", "Circle"
    RECTANGLE = "rectangle", "Rectangle"
    SQUARE = "square", "Square"


class Panchayat(BaseMaster):

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=geneate_panchayat_id,
        editable=False
    )

    company_id = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="pancahyat",
        db_column="company_id",
    )

    project_id = models.ForeignKey(
        Project,
        on_delete=models.PROTECT,
        related_name="pancahyat",
        db_column="project_id",
    )

    state_id = models.ForeignKey(
        State,
        on_delete = models.PROTECT,
        related_name="panchayat",
        db_column="state_id",
        
    )

    city_id = models.ForeignKey(
        City,
        on_delete = models.PROTECT,
        related_name="panchayat",
        db_column="city_id",
        
    )

    district_id = models.ForeignKey(
        District,
        on_delete = models.PROTECT,
        related_name="panchayat",
        db_column="district_id",
    )

    area_type_id = models.ForeignKey(
        AreaType,
        on_delete=models.PROTECT,
        limit_choices_to={"name": "Rural"},
        null=True,
        blank=True
    )

    hierarchy_id = models.ForeignKey(
        AdministrativeHierarchy,
        on_delete=models.PROTECT,
        limit_choices_to={"level_name": "Panchayat"},
        null=True,
        blank=True
    )

    geofencing_type = models.CharField(
        max_length=20,
        choices=GeoFencingType.choices,
        default=GeoFencingType.SQUARE
    )
    panchayat_name = models.CharField(max_length=100)
    latitude = models.DecimalField(max_digits=9, decimal_places=6,null=True,blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6,null=True,blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)