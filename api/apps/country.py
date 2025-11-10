from django.db import models
from .continent import Continent

from .utils.comfun import generate_unique_id

def generate_country_id():
    # Prepend COUNTRY- to the unique ID
    return f"COUNTRY{generate_unique_id()}"

class Country(models.Model):
    unique_id = models.CharField(
        max_length=30,
        unique=True,
        default=generate_country_id
    )
    continent = models.ForeignKey(
        Continent,
        on_delete=models.PROTECT,
        related_name='countries'
    )
    name = models.CharField(max_length=100)
    currency = models.CharField(max_length=20, blank=True, null=True)
    mob_code = models.CharField(max_length=5, blank=True, null=True)       # e.g. +91
    is_active = models.BooleanField(default=True)
    is_delete = models.BooleanField(default=False)


    class Meta:
        verbose_name_plural = "Countries"
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.currency  or ''})".strip()

    def delete(self, *args, **kwargs):
        """
        Soft delete:
        - Mark this country inactive.
        - Mark all related states and districts inactive (if relationships exist).
        """
        self.is_active = False
        self.save(update_fields=["is_active"])

        # Deactivate related states
        related_states = getattr(self, "states", None)
        if related_states is not None:
            for state in related_states.all():
                state.is_active = False
                state.save(update_fields=["is_active"])

        # Deactivate related districts (if they directly reference Country)
        related_districts = getattr(self, "districts", None)
        if related_districts is not None:
            for district in related_districts.all():
                district.is_active = False
                district.save(update_fields=["is_active"])
