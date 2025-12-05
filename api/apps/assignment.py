from django.db import models

from .utils.comfun import generate_unique_id
from .ward import Ward
from .customercreation import CustomerCreation
from .userCreation import User


def generate_assignment_id():
    return f"ASSIGN{generate_unique_id()}"


class DailyAssignment(models.Model):
    unique_id = models.CharField(
        max_length=40,
        unique=True,
        default=generate_assignment_id,
        editable=False,
    )
    date = models.DateField(auto_now_add=True)

    ward = models.ForeignKey(
        Ward,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assignments",
    )
    customer = models.ForeignKey(
        CustomerCreation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assignments",
    )
    driver = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assignments_as_driver",
    )
    operator = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assignments_as_operator",
    )
    assigned_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assignments_created",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "api_daily_assignments"
        ordering = ["-created_at"]

    def __str__(self):
        label = self.ward.name if self.ward else "Assignment"
        return f"{label} → driver/operator"
