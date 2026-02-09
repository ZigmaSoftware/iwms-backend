from django.db import models
from app.utils.tenancy import CompanyProjectMixin
import uuid
from app.utils.comfun import generate_unique_id  # optional if you want prefixed IDs
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project

def generate_fueltype_id():
    # Prefix for traceability inside the ERP ecosystem
    return f"FUEL-{generate_unique_id()}"


class Fuel(CompanyProjectMixin, models.Model):
    """
    Transport Master: Fuel Type
    -----------------------------------
    Defines available fuel types (e.g. Diesel, Petrol, CNG).
    Supports soft delete and active/inactive toggling.
    """

    # Unique identifier for internal and API-level use
    unique_id = models.CharField(
        max_length=40,
        unique=True,
        default=generate_fueltype_id,
        editable=False
    )

    # Business fields
    fuel_type = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    company_id = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="fuels",
        db_column="company_id",
    )
    project_id = models.ForeignKey(
        Project,
        on_delete=models.PROTECT,
        related_name="fuels",
        db_column="project_id",
    )

    # Status flags
    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Fuel Type"
        verbose_name_plural = "Fuel Types"
        ordering = ["fuel_type"]

    def __str__(self):
        return self.fuel_type

    # Soft delete override
    def delete(self, *args, **kwargs):
        """
        Soft delete: marks record as deleted without physically removing it.
        """
        self.is_deleted = True
        self.is_active = False
        self.save(update_fields=["is_deleted", "is_active"])
