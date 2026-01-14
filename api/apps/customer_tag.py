from django.db import models
from django.utils import timezone
from api.apps.customercreation import CustomerCreation


class CustomerTag(models.Model):

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        REVOKED = "REVOKED", "Revoked"

    customer = models.ForeignKey(
        CustomerCreation,
        on_delete=models.PROTECT,
        related_name="customer_tags"
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

    issued_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "api_customer_tag"

    def revoke(self):
        if self.status == self.Status.REVOKED:
            return
        self.status = self.Status.REVOKED
        self.revoked_at = timezone.now()
        self.save(update_fields=["status", "revoked_at"])
