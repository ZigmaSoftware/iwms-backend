from django.db import models
from .utils.comfun import generate_unique_id

def generate_continent_id():
    # Prepend CONT- to the unique ID
    return f"CONT{generate_unique_id()}"

class Continent(models.Model):
    unique_id = models.CharField(
        max_length=30,
        unique=True,
        default=generate_continent_id
    )
    name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    is_delete = models.BooleanField(default=False) 

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return self.name

    def delete(self, *args, **kwargs):
        """Soft delete: deactivate this Continent and its related Countries."""
        self.is_active = False
        self.save(update_fields=["is_active"])

        # Deactivate all related countries (if relation exists)
        related_countries = getattr(self, "countries", None)
        if related_countries is not None:
            for country in related_countries.all():
                country.is_active = False
                country.save(update_fields=["is_active"])
