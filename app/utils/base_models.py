from django.db import models


class BaseMaster(models.Model):
    """Shared active/deleted flags for most tables."""
    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)

    class Meta:
        abstract = True
