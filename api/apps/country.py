from django.db import models
from .continent import Continent
from .utils.comfun import generate_unique_id

def generate_country_id():
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
    mob_code = models.CharField(max_length=5, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    is_delete = models.BooleanField(default=False)

    class Meta:
        verbose_name_plural = "Countries"
        ordering = ["name"]

    def __str__(self):
        return self.name

    def delete(self, *args, **kwargs):
        """
        Soft delete – ONLY mark is_delete=True.
        Do not modify is_active! Toggle uses is_active separately.
        """
        self.is_delete = True
        self.save(update_fields=["is_delete"])
