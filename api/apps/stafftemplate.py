from django.db import models
from .utils.comfun import generate_unique_id
from .userCreation import User

def generate_stafftemplate_id():
    return f"STAFFTEMPLATE-{generate_unique_id()}"


class StaffTemplate(models.Model):
    unique_id = models.CharField(
        max_length=40,
        primary_key=True,
        default=generate_stafftemplate_id,
        editable=False
    )

    # ---- DRIVER ROLES ----
    primary_driver_id = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="primary_driver_templates",
        db_column="primary_driver_id",
        to_field="unique_id"
    )

    secondary_driver_id = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="secondary_driver_templates",
        db_column="secondary_driver_id",
        to_field="unique_id",
        null=True,
        blank=True
    )

    # ---- OPERATOR ROLES ----
    primary_operator_id = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="primary_operator_templates",
        db_column="primary_operator_id",
        to_field="unique_id"
    )

    secondary_operator_id = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="secondary_operator_templates",
        db_column="secondary_operator_id",
        to_field="unique_id",
        null=True,
        blank=True
    )

    extra_staff_ids = models.JSONField(
        default=list,
        blank=True,
        help_text="Additional staff user IDs linked to this template",
    )

    # ---- STATUS ----
    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Staff Template"
        verbose_name_plural = "Staff Templates"
        indexes = [
            models.Index(fields=["is_active", "is_deleted"]),
        ]

    def __str__(self):
        return self.unique_id

    def delete(self, *args, **kwargs):
        self.is_deleted = True
        self.is_active = False
        self.save(update_fields=["is_deleted", "is_active"])
