from django.db import models
from .utils.comfun import generate_unique_id
from .userType import UserType


def generate_staff_usertype_id():
    return f"STUSRTYPE{generate_unique_id()}"


class StaffUserType(models.Model):
    STAFF_ROLE_CHOICES = [
        ("admin", "Admin"),
        ("operator", "Operator"),
        ("driver", "Driver"),
        ("user", "User"),
    ]

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        unique=True,
        default=generate_staff_usertype_id,
        editable=False
    )

    usertype_id = models.ForeignKey(
        UserType,
        on_delete=models.PROTECT,
        related_name="staffusertypes",
        to_field="unique_id"
    )

    name = models.CharField(
        max_length=50,
        choices=STAFF_ROLE_CHOICES
    )

    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)

    class Meta:
        ordering = ["name"]
        verbose_name = "Staff User Type"
        verbose_name_plural = "Staff User Types"
        constraints = [
            models.UniqueConstraint(
                fields=["usertype_id", "name", "is_deleted"],
                name="unique_staff_role_per_usertype_not_deleted"
            )
        ]

    def __str__(self):
        return f"{self.usertype_id.name} → {self.name}"

    def delete(self, *args, **kwargs):
        self.is_active = False
        self.is_deleted = True
        self.save(update_fields=["is_active", "is_deleted"])
