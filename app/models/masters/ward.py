from django.db import models
from app.utils.base_models import BaseMaster
from django.core.validators import RegexValidator
from django.core.exceptions import ValidationError
from app.utils.comfun import generate_unique_id


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

    company_id = models.CharField(max_length=30, null=True, blank=True)
    project_id = models.CharField(max_length=30, null=True, blank=True)

    state_id = models.CharField(max_length=30, null=True, blank=True)
    district_id = models.CharField(max_length=30, null=True, blank=True)
    city_id = models.CharField(max_length=30, null=True, blank=True)

    zone_id = models.CharField(max_length=30, null=True, blank=True)
    panchayat_id = models.CharField(max_length=30, null=True, blank=True)

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

    CASCADE_SOFT_DELETE = (
        "waste_collections",
        "complaint_set",
        "complaint_tickets",
        "complaint_routing_rules",
        "address_change_requests",
        "bin",
        "trip_plan_collection_points",
        "daily_trip_collection_points",
        "daily_trip_household_collections",
        "bin_collection_events",
        "customer_creation",
        "users_ward",
        "userscreenpermissions",
        "staff_ward",
    )
    CACHE_SCOPES = ("ward_list", "ward_detail")

    def clean(self):
        has_zone = bool(self.zone_id)
        has_panchayat = bool(self.panchayat_id)

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
        return self.ward_name

    @property
    def state(self):
        from app.models.common_masters.state import State
        if self.state_id:
            return State.objects.filter(unique_id=self.state_id).first()
        return None

    @property
    def district(self):
        from app.models.masters.district import District
        if self.district_id:
            return District.objects.filter(unique_id=self.district_id).first()
        return None

    @property
    def city(self):
        from app.models.masters.city import City
        if self.city_id:
            return City.objects.filter(unique_id=self.city_id).first()
        return None

    @property
    def zone(self):
        from app.models.masters.zone import Zone
        if self.zone_id:
            return Zone.objects.filter(unique_id=self.zone_id).first()
        return None

    @property
    def panchayat(self):
        from app.models.masters.panchayat import Panchayat
        if self.panchayat_id:
            return Panchayat.objects.filter(unique_id=self.panchayat_id).first()
        return None

    @property
    def company(self):
        from app.models.superadmin_masters.company import Company
        if self.company_id:
            return Company.objects.filter(unique_id=self.company_id).first()
        return None

    @property
    def project(self):
        from app.models.superadmin_masters.project import Project
        if self.project_id:
            return Project.objects.filter(unique_id=self.project_id).first()
        return None