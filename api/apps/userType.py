from django.db import models
from .utils.comfun import generate_unique_id


def generate_usertype_id():
    """Generate a unique ID prefixed with UTYPE."""
    return f"UTYPE{generate_unique_id()}"


class UserType(models.Model):
    usertype_id = models.CharField(
        max_length=30,
        unique=True,
        default=generate_usertype_id,
        editable=False
    )

    name = models.CharField(
        max_length=50,
        unique=True
    )

    is_active = models.BooleanField(default=True)
    is_delete = models.BooleanField(default=False)

    class Meta:
        ordering = ["id"]
        verbose_name = "User Type"
        verbose_name_plural = "User Types"

    def __str__(self):
        return self.name

    def delete(self, *args, **kwargs):
        """Soft Delete"""
        self.is_active = False
        self.is_delete = True
        self.save(update_fields=["is_active", "is_delete"])
