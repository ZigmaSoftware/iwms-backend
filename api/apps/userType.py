from django.db import models
from .utils.comfun import generate_unique_id


def generate_usertype_id():
    return f"UTYPE{generate_unique_id()}"


class UserType(models.Model):
    unique_id = models.CharField(
        max_length=30,
        primary_key=True,            # FIXED
        unique=True,
        default=generate_usertype_id,
        editable=False
    )

    name = models.CharField(
        max_length=50,
        unique=True
    )

    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)   # FIXED

    class Meta:
        ordering = ["name"]   # better than id, and alphabetic
        verbose_name = "User Type"
        verbose_name_plural = "User Types"

    def __str__(self):
        return self.name

    def delete(self, *args, **kwargs):   # Soft delete
        self.is_active = False
        self.is_deleted = True
        self.save(update_fields=["is_active", "is_deleted"])
