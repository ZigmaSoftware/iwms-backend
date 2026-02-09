from django.db import models
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id


def generate_propertyName_id():
    return f"PROPERTY-{generate_unique_id()}"


class Property(BaseMaster):

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
        max_length=40,
        primary_key=True,               # FIXED
        unique=True,
        default=generate_propertyName_id,
        editable=False
    )

    property_name = models.CharField(max_length=100)

    class Meta:
        verbose_name = "Fuel Type"
        verbose_name_plural = "Fuel Types"
        ordering = ["property_name"]

    def __str__(self):
        return self.property_name

    def delete(self, *args, **kwargs):
        self.is_deleted = True
        self.is_active = False
        self.save(update_fields=["is_deleted", "is_active"])
