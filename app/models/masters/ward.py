from django.db import models
from app.utils.tenancy import CompanyProjectMixin
from app.utils.base_models import BaseMaster
from django.core.validators import RegexValidator
from app.utils.comfun import generate_unique_id


def generate_ward_id():
    return f"WARD-{generate_unique_id()}"


class GeoFencingType(models.TextChoices):
    POLYGON = "polygon", "Polygon"
    CIRCLE = "circle", "Circle"
    RECTANGLE = "rectangle", "Rectangle"
    SQUARE = "square", "Square"


class AreaType(models.TextChoices):
    URBAN = "urban", "Urban"
    RURAL = "rural", "Rural"
    PERI_URBAN = "peri_urban", "Peri-Urban"
    INDUSTRIAL = "industrial", "Industrial"
    COMMERCIAL = "commercial", "Commercial"


hex_color_validator = RegexValidator(
    regex=r'^#(?:[0-9a-fA-F]{3}){1,2}$',
    message="Invalid HEX color code"
)


class Ward(CompanyProjectMixin, BaseMaster):
    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_ward_id,
        editable=False
    )

    continent_id = models.ForeignKey("Continent", on_delete=models.PROTECT)
    country_id = models.ForeignKey("Country", on_delete=models.PROTECT)
    state_id = models.ForeignKey("State", on_delete=models.PROTECT)
    district_id = models.ForeignKey("District", on_delete=models.PROTECT)
    city_id = models.ForeignKey("City", on_delete=models.PROTECT)
    zone_id = models.ForeignKey("Zone", on_delete=models.PROTECT)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)

    coordinates = models.JSONField(
        help_text="GeoJSON-compatible coordinates"
    )

    geofencing_type = models.CharField(
        max_length=20,
        choices=GeoFencingType.choices
    )

    geofencing_color = models.CharField(
        max_length=7,
        validators=[hex_color_validator]
    )

    area_type = models.CharField(
        max_length=20,
        choices=AreaType.choices
    )

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["city_id", "zone_id", "area_type"]),
        ]

    def delete(self, *args, **kwargs):
        self.is_deleted = True
        self.is_active = False
        self.save(update_fields=["is_deleted", "is_active"])
