from django.db import models
from .country import Country
from .utils.comfun import generate_unique_id


def generate_state_id():
    return f"STATE{generate_unique_id()}"


class State(models.Model):
    state_id = models.CharField(
        max_length=30,
        primary_key=True,
        unique=True,
        default=generate_state_id
    )

    country = models.ForeignKey(
        Country,
        on_delete=models.PROTECT,
        related_name="states",
        to_field="country_id"    # important
    )

    name = models.CharField(max_length=100)
    label = models.CharField(max_length=20, blank=True, null=True)

    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)

    class Meta:
        ordering = ["name"]
        unique_together = ("country", "name")

    def __str__(self):
        return f"{self.name} ({self.country.name})"

    def delete(self, *args, **kwargs):
        self.is_deleted = True
        self.save(update_fields=["is_deleted"])
