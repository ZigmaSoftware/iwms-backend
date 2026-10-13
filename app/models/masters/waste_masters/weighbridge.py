from django.db import models
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from app.models.core_modules.schedule_setup.trip_plan import TripPlan
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project


def generate_weighbridge_check_id():
    return f"WBC-{generate_unique_id()}"


class WeighbridgeCheck(BaseMaster):
    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_weighbridge_check_id,
        editable=False,
    )

    company_id = models.CharField(max_length=30, null=True, blank=True)
    project_id = models.CharField(max_length=30, null=True, blank=True)

    trip_id = models.CharField(max_length=30, null=True, blank=True)

    weighbridge_weight = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    checked_date = models.DateField(null=True, blank=True)
    collected_date = models.DateField(null=True, blank=True)

    class StatusChoices(models.TextChoices):
        WITHIN_LIMIT = "WITHIN_LIMIT", "Within Limit"
        OVER_WEIGHT = "OVER_WEIGHT", "Over Weight"
        UNDER_WEIGHT = "UNDER_WEIGHT", "Under Weight"

    status = models.CharField(
        max_length=20,
        choices=StatusChoices.choices,
        default=StatusChoices.WITHIN_LIMIT,
    )

    CASCADE_SOFT_DELETE = ()
    CACHE_SCOPES = ("weighbridge_check_list", "weighbridge_check_detail")

    def __str__(self):
        return self.unique_id

    @property
    def company(self):
        if self.company_id:
            return Company.objects.filter(unique_id=self.company_id).first()
        return None

    @property
    def project(self):
        if self.project_id:
            return Project.objects.filter(unique_id=self.project_id).first()
        return None

    @property
    def trip(self):
        if self.trip_id:
            return TripPlan.objects.filter(unique_id=self.trip_id).first()
        return None