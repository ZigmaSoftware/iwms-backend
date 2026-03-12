from django.db import models
from app.utils.base_models import BaseMaster
from django.core.validators import RegexValidator
from ..common_masters.continent import Continent
from ..common_masters.country import Country
from ..common_masters.state import State
from .district import District
from .city import City
from app.utils.comfun import generate_unique_id
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project
from app.models.masters.hierarchy import AdministrativeHierarchy
from app.models.masters.areatype import AreaType



# ----------------------------------
# ID GENERATOR
# ----------------------------------
def generate_zone_id():
    return f"ZONE-{generate_unique_id()}"


# ----------------------------------
# ENUMS
# ----------------------------------
class GeoFencingType(models.TextChoices):
    POLYGON = "polygon", "Polygon"
    CIRCLE = "circle", "Circle"
    RECTANGLE = "rectangle", "Rectangle"
    SQUARE = "square", "Square"


# class AreaType(models.TextChoices):
#     URBAN = "urban", "Urban"
#     RURAL = "rural", "Rural"
#     PERI_URBAN = "peri_urban", "Peri-Urban"
#     INDUSTRIAL = "industrial", "Industrial"
#     COMMERCIAL = "commercial", "Commercial"


# ----------------------------------
# VALIDATORS
# ----------------------------------
hex_color_validator = RegexValidator(
    regex=r"^#(?:[0-9a-fA-F]{3}){1,2}$",
    message="Invalid HEX color code"
)


# ----------------------------------
# MODEL
# ----------------------------------
# class Zone(BaseMaster):
#     company_id = models.ForeignKey(
#         Company,
#         on_delete=models.PROTECT,
#         null=True,
#         blank=True,
#         db_column="company_id",
#     )
#     project_id = models.ForeignKey(
#         Project,
#         on_delete=models.PROTECT,
#         null=True,
#         blank=True,
#         db_column="project_id",
#     )

#     # -----------------------------
#     # SYSTEM IDENTIFIER
#     # -----------------------------
#     unique_id = models.CharField(
#         max_length=30,
#         primary_key=True,
#         unique=True,
#         default=generate_zone_id,
#         editable=False
#     )

#     # -----------------------------
#     # LOCATION HIERARCHY
#     # -----------------------------
#     continent_id = models.ForeignKey(
#         Continent,
#         on_delete=models.PROTECT,
#         related_name="zones",
#         db_column="continent_id",
#     )

#     country_id = models.ForeignKey(
#         Country,
#         on_delete=models.PROTECT,
#         related_name="zones",
#         db_column="country_id",
#     )

#     state_id = models.ForeignKey(
#         State,
#         on_delete=models.PROTECT,
#         related_name="zones",
#            db_column="state_id",
#     )

#     district_id = models.ForeignKey(
#         District,
#         on_delete=models.PROTECT,
#         related_name="zones",
#         db_column="district_id",
#     )

#     city_id = models.ForeignKey(
#         City,
#         on_delete=models.PROTECT,
#         related_name="zones",
#         db_column="city_id",
#     )

#     # -----------------------------
#     # GEO FENCING
#     # -----------------------------
#     coordinates = models.JSONField(
#         help_text="GeoJSON-compatible coordinates",
#         default=dict
#     )

#     geofencing_type = models.CharField(
#         max_length=20,
#         choices=GeoFencingType.choices,
#         default=GeoFencingType.POLYGON
#     )

#     geofencing_color = models.CharField(
#         max_length=7,
#         validators=[hex_color_validator],
#         default="#FF0000"
#     )

#     # -----------------------------
#     # ZONE TYPE
#     # -----------------------------
#     area_type = models.CharField(
#         max_length=20,
#         choices=AreaType.choices,
#         default=AreaType.URBAN
#     )

#     # -----------------------------
#     # METADATA
#     # -----------------------------
#     name = models.CharField(max_length=100)
#     description = models.TextField(blank=True, null=True)

#     # -----------------------------
#     # STATE FLAGS
#     # -----------------------------
#     # -----------------------------
#     # META
#     # -----------------------------
#     class Meta:
#         ordering = ["name"]
#         indexes = [
#             models.Index(fields=["city_id", "area_type"]),
#             models.Index(fields=["is_active", "is_deleted"]),
#         ]

#     # -----------------------------
#     # STRING
#     # -----------------------------
#     def __str__(self):
#         location = self.city_id.name if self.city_id else ""
#         return f"{self.name} ({location})" if location else self.name

#     # -----------------------------
#     # SOFT DELETE
#     # -----------------------------
#     def delete(self, *args, **kwargs):
#         self.is_deleted = True
#         self.is_active = False
#         self.save(update_fields=["is_deleted", "is_active"])






class Zone(BaseMaster):

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_zone_id,
        editable=False
    )

    company_id = models.ForeignKey(Company, on_delete=models.PROTECT,null=True,blank=True)
    project_id = models.ForeignKey(Project, on_delete=models.PROTECT,null=True,blank=True)

    state_id = models.ForeignKey(State, on_delete=models.PROTECT)
    district_id = models.ForeignKey(District, on_delete=models.PROTECT)
    city_id = models.ForeignKey(City, on_delete=models.PROTECT)

    area_type_id = models.ForeignKey(
        AreaType,
        on_delete=models.PROTECT,
        limit_choices_to={"name": "Urban"},
        null=True,
        blank=True
    )

    hierarchy_id = models.ForeignKey(
        AdministrativeHierarchy,
        on_delete=models.PROTECT,
        limit_choices_to={"level_name": "Zone"},
        null=True,
        blank=True
    )

    zone_name = models.CharField(max_length=100)
    latitude = models.DecimalField(max_digits=9, decimal_places=6,null=True,blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6,null=True,blank=True)
    geofencing_type = models.CharField(max_length=20, choices=GeoFencingType.choices, default=GeoFencingType.SQUARE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)     
    
    
