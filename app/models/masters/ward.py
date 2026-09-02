from django.db import models
from app.utils.base_models import BaseMaster
from django.core.validators import RegexValidator
from django.core.exceptions import ValidationError
from app.utils.comfun import generate_unique_id
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project
from ..common_masters.state import State
from .district import District
from .city import City
from app.models.masters.zone import Zone
from app.models.masters.panchayat import Panchayat



def generate_ward_id():
    return f"WARD-{generate_unique_id()}"


class GeoFencingType(models.TextChoices):
    POLYGON = "polygon", "Polygon"
    CIRCLE = "circle", "Circle"
    RECTANGLE = "rectangle", "Rectangle"
    SQUARE = "square", "Square"

class Ward(BaseMaster):

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_ward_id,
        editable=False
    )

    company_id = models.ForeignKey(Company, on_delete=models.PROTECT,null=True,blank=True)
    project_id = models.ForeignKey(Project, on_delete=models.PROTECT,null=True,blank=True)

    state_id = models.ForeignKey(State, on_delete=models.PROTECT)
    district_id = models.ForeignKey(District, on_delete=models.PROTECT)
    city_id = models.ForeignKey(City, on_delete=models.PROTECT)

    zone_id = models.ForeignKey(
        Zone,
        on_delete=models.PROTECT,
        related_name="wards",
        null=True,
        blank=True
    )

    panchayat_id = models.ForeignKey(
        Panchayat,
        on_delete=models.PROTECT,
        related_name="wards",
        null=True,
        blank=True
    )

    ward_name = models.CharField(max_length=100)
    description = models.TextField(null=True, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    geofencing_type = models.CharField(max_length=20, choices=GeoFencingType.choices, default=GeoFencingType.SQUARE)
    boundary_coordinates = models.JSONField(
        null=True,
        blank=True,
        help_text=(
            "Ordered list of {latitude, longitude} points tracing this "
            "ward's boundary. Connected in order (and back to the first "
            "point) to draw the geofence polygon on the map. Needs at "
            "least 3 points to render — fewer than that is treated as "
            "'no boundary set' and only the center point is shown."
        ),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        has_zone = bool(self.zone_id_id or self.zone_id)
        has_panchayat = bool(self.panchayat_id_id or self.panchayat_id)

        if has_zone and has_panchayat:
            raise ValidationError("Ward can belong to either Zone or Panchayat.")

        if not has_zone and not has_panchayat:
            raise ValidationError("Ward must belong to Zone or Panchayat.")

        if self.boundary_coordinates is not None:
            if not isinstance(self.boundary_coordinates, list):
                raise ValidationError("boundary_coordinates must be a list of points.")
            for point in self.boundary_coordinates:
                if (
                    not isinstance(point, dict)
                    or "latitude" not in point
                    or "longitude" not in point
                ):
                    raise ValidationError(
                        "Each boundary_coordinates point needs latitude and longitude."
                    )

    def __str__(self):
        if self.zone_id:
            return f"{self.ward_name} (Zone: {self.zone_id.zone_name})"
        if self.panchayat_id:
            return f"{self.ward_name} (Panchayat: {self.panchayat_id.panchayat_name})"
        return self.ward_name

