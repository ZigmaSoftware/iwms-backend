from django.db import models
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id


def generate_continent_id():
    return f"CONT-{generate_unique_id()}"


class Continent(BaseMaster):

    company_id = models.ForeignKey(
        "api.Company",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="company_id",
    )
    project_id = models.ForeignKey(
        "api.Project",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="project_id",
    )

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        unique=True,
        default=generate_continent_id
    )

    name = models.CharField(max_length=100)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def delete(self, *args, **kwargs):
        self.is_deleted = True
        self.save(update_fields=["is_deleted"])
