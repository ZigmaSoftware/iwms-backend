from django.db import models

from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id


def generate_plant_id():
    return f"PL-{generate_unique_id()}"


class Plant(BaseMaster):
    """A project's waste disposal destination.

    One per project (enforced by project_id being unique) — every trip
    route for that project ends here. Not a collection stop: it never
    appears in DailyTripCollectionPoint, only appended to route geometry
    at render time.
    """

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_plant_id,
        editable=False,
    )

    company_id = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="plants",
        db_column="company_id",
    )

    project_id = models.ForeignKey(
        Project,
        on_delete=models.PROTECT,
        related_name="plants",
        db_column="project_id",
        unique=True,
    )

    name = models.CharField(max_length=100)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name
