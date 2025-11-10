from django.db import models
from .customercreation import CustomerCreation
from .zone import Zone
from .ward import Ward
from .utils.comfun import generate_unique_id


def generate_complaint_id():
    """Generate readable prefixed ID, e.g., CMP-20251101001"""
    return f"CMP-{generate_unique_id()}"


def complaint_upload_path(instance, filename):
    """Dynamic upload path: uploads/complaints/<unique_id>_<filename>"""
    return f"uploads/complaints/{instance.unique_id}_{filename}"


class Complaint(models.Model):
    class CategoryChoices(models.TextChoices):
        COLLECTION = "COLLECTION", "Collection"
        TRANSPORT = "TRANSPORT", "Transport"
        SEGREGATION = "SEGREGATION", "Segregation"
        VEHICLE = "VEHICLE", "Vehicle"
        WORKER = "WORKER", "Worker"
        OTHER = "OTHER", "Other"

    unique_id = models.CharField(
        max_length=30, unique=True, default=generate_complaint_id
    )

    customer = models.ForeignKey(
        CustomerCreation,
        on_delete=models.PROTECT,
        related_name="complaints"
    )

    zone = models.ForeignKey(
        Zone,
        on_delete=models.PROTECT,
        related_name="complaints",
        blank=True,
        null=True
    )

    ward = models.ForeignKey(
        Ward,
        on_delete=models.PROTECT,
        related_name="complaints",
        blank=True,
        null=True
    )

    contact_no = models.CharField(max_length=15, blank=True, null=True)
    address = models.TextField(blank=True, null=True)

    category = models.CharField(
        max_length=20,
        choices=CategoryChoices.choices,
        blank=False,
        null=False
    )
    details = models.TextField(blank=True, null=True)

    # Use FileField for uploads (Django will manage path)
    image = models.FileField(upload_to=complaint_upload_path, blank=True, null=True)

    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Complaint"
        verbose_name_plural = "Complaints"
        ordering = ["-created"]

    def __str__(self):
        return f"{self.unique_id} - {self.customer.customer_name}"

    def save(self, *args, **kwargs):
        """Auto-fill related zone, ward, and contact info from selected customer."""
        if self.customer:
            self.zone = self.customer.zone
            self.ward = self.customer.ward
            self.contact_no = self.customer.contact_no
            self.address = (
                f"{self.customer.building_no}, {self.customer.street}, "
                f"{self.customer.area}, {self.customer.city.name if self.customer.city else ''}"
            )
        super().save(*args, **kwargs)
