from django.db import models
from .utils.comfun import generate_unique_id


def generate_bin_id():
    return f"BIN{generate_unique_id()}"


class Bin(models.Model):
    unique_id = models.CharField(
        max_length=40,
        primary_key=True,
        unique=True,
        default=generate_bin_id,
        editable=False,
    )

    name = models.CharField(max_length=100)
    code = models.CharField(max_length=60, blank=True, null=True)
    capacity = models.CharField(max_length=60, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    latitude = models.DecimalField(max_digits=10, decimal_places=6, blank=True, null=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=6, blank=True, null=True)

    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def delete(self, *args, **kwargs):
        self.is_deleted = True
        self.is_active = False
        self.save(update_fields=["is_deleted", "is_active"])
