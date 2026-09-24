from django.db import models
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id


def generate_panchayat_id():
    return f"PANCHAYAT-{generate_unique_id()}"


class GeoFencingType(models.TextChoices):
    POLYGON = "polygon", "Polygon"
    CIRCLE = "circle", "Circle"
    RECTANGLE = "rectangle", "Rectangle"
    SQUARE = "square", "Square"


class WeightUnit(models.TextChoices):
    KG = "kg", "Kg"
    TONNE = "tonne", "Tonne"


class Panchayat(BaseMaster):

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_panchayat_id,
        editable=False
    )

    company_id = models.CharField(max_length=30, null=True, blank=True)
    project_id = models.CharField(max_length=30, null=True, blank=True)

    state_id = models.CharField(max_length=30, null=True, blank=True)
    city_id = models.CharField(max_length=30, null=True, blank=True)
    district_id = models.CharField(max_length=30, null=True, blank=True)

    geofencing_type = models.CharField(
        max_length=20,
        choices=GeoFencingType.choices,
        default=GeoFencingType.SQUARE
    )
    panchayat_name = models.CharField(max_length=100)
    agreed_weight_kg = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Monthly agreed collection weight in kg",
    )
    weight_unit = models.CharField(
        max_length=10,
        choices=WeightUnit.choices,
        default=WeightUnit.KG,
        help_text="Unit for agreed weight",
    )
    effective_from = models.DateField(
        null=True,
        blank=True,
        help_text="Date from which this agreed weight is valid",
    )
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    block_id = models.CharField(max_length=30, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    CASCADE_SOFT_DELETE = ("wards", "leader_logins")
    CACHE_SCOPES = ("panchayat_list", "panchayat_detail")

    def __str__(self):
        return self.panchayat_name

    @property
    def state(self):
        from app.models.superadmin.common_masters.state import State
        if self.state_id:
            return State.objects.filter(unique_id=self.state_id).first()
        return None

    @property
    def city(self):
        from app.models.masters.city import City
        if self.city_id:
            return City.objects.filter(unique_id=self.city_id).first()
        return None

    @property
    def district(self):
        from app.models.masters.district import District
        if self.district_id:
            return District.objects.filter(unique_id=self.district_id).first()
        return None

    @property
    def block(self):
        from app.models.masters.block_panchayat_union import BlockPanchayatUnion
        if self.block_id:
            return BlockPanchayatUnion.objects.filter(unique_id=self.block_id).first()
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

    @property
    def wards(self):
        from app.models.masters.ward import Ward
        return Ward.objects.filter(panchayat_id=self.unique_id)