from django.db import models
from django.utils import timezone
from api.apps.userCreation import User
from api.apps.utils.comfun import generate_unique_id


def generate_customer_tag_id():
    return f"CUSTTAG-{generate_unique_id()}"


class CustomerTag(models.Model):

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        INACTIVE = "INACTIVE", "Inactive"

    unique_id = models.CharField(
        max_length=40,
        unique=True,
        default=generate_customer_tag_id,
        editable=False
    )

    customer = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="customer_tags",
        to_field="unique_id"
    )

    tag_code = models.CharField(max_length=50, unique=True)

    qr_image = models.ImageField(
        upload_to="customer_qr/",
        null=True,
        blank=True
    )

    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.ACTIVE
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "api_customer_tag"
        constraints = [
            models.UniqueConstraint(
                fields=["customer"],
                name="unique_customer_tag_per_user",
            )
        ]

    def deactivate(self):
        if self.status == self.Status.INACTIVE:
            return
        self.status = self.Status.INACTIVE
        self.updated_at = timezone.now()
        self.save(update_fields=["status", "updated_at"])
