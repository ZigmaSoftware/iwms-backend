from django.db import models
from .utils.comfun import generate_unique_id

def generate_staff_usertype_id():
    return f"STUSRTYPE{generate_unique_id()}"

class StaffUserType(models.Model):
    STAFF_ROLE_CHOICES = [
        ("admin", "Admin"),
        ("operator", "Operator"),
        ("driver", "Driver"),
        ("user", "User"),
    ]

    staffusertype_id = models.CharField(
        max_length=30,
        unique=True,
        default=generate_staff_usertype_id,
        editable=False
    )

    name = models.CharField(
        max_length=50,
        choices=STAFF_ROLE_CHOICES,
        unique=True
    )

    is_active = models.BooleanField(default=True)
    is_delete = models.BooleanField(default=False)

    class Meta:
        ordering = ["id"]
        verbose_name = "Staff User Type"
        verbose_name_plural = "Staff User Types"

    def __str__(self):
        return self.name

    def delete(self, *args, **kwargs):
        self.is_active = False
        self.is_delete = True
        self.save(update_fields=["is_active", "is_delete"])
