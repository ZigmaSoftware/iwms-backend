from django.db import models
from django.db.models import Max

from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id


def generate_hierarchy_id():
    return f"HIER-{generate_unique_id()}"


class AdministrativeHierarchy(BaseMaster):
    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_hierarchy_id,
        editable=False,
    )
    level_name = models.CharField(max_length=50)
    hierarchy_order = models.PositiveIntegerField(editable=False)

    class Meta:
        ordering = ["hierarchy_order"]
        constraints = [
            models.UniqueConstraint(
                fields=["level_name"],
                name="unique_administrative_hierarchy_level",
            )
        ]

    def save(self, *args, **kwargs):
        if not self.hierarchy_order:
            last_order = (
                AdministrativeHierarchy.objects.aggregate(Max("hierarchy_order")).get(
                    "hierarchy_order__max"
                )
            )
            self.hierarchy_order = (last_order or 0) + 1

        super().save(*args, **kwargs)

    def __str__(self):
        return self.level_name
