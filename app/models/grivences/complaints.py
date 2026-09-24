from django.db import models
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from django.utils import timezone
from django.db.models import Max


def generate_complaint_id():
    """Generate sequential CG-00001 style complaint ID."""
    last_id = Complaint.objects.aggregate(max_id=Max("unique_id"))["max_id"]

    if last_id:
        # Extract numeric part → CG-00025 → 25
        try:
            last_num = int(last_id.split("-")[1])
        except:
            last_num = 0
    else:
        last_num = 0

    new_num = last_num + 1
    return f"CG-{new_num:05d}"    # always 5 digits padded


# def generate_complaint_id():
#     """Readable ID like CG-00004"""
#     return f"CG-{generate_unique_id()}"


def complaint_upload_path(instance, filename):
    return f"uploads/complaints/{instance.unique_id}_{filename}"


class Complaint(BaseMaster):

    company_id = models.CharField(max_length=30, null=True, blank=True)
    project_id = models.CharField(max_length=30, null=True, blank=True)

    class StatusChoices(models.TextChoices):
        PROGRESSING = "PROGRESSING", "Progressing"
        CLOSED = "CLOSED", "Closed"

    class PriorityChoices(models.TextChoices):
        HIGH = "HIGH", "High"
        MEDIUM = "MEDIUM", "Medium"
        LOW = "LOW", "Low"

    class CategoryChoices(models.TextChoices):
        COLLECTION = "COLLECTION", "Collection"
        TRANSPORT = "TRANSPORT", "Transport"
        SEGREGATION = "SEGREGATION", "Segregation"
        VEHICLE = "VEHICLE", "Vehicle"
        WORKER = "WORKER", "Worker"
        OTHER = "OTHER", "Other"

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_complaint_id,
        editable=False,
    )
    

    customer_id = models.CharField(max_length=30, null=True, blank=True)
    zone_id = models.CharField(max_length=30, null=True, blank=True)
    ward_id = models.CharField(max_length=30, null=True, blank=True)

    contact_no = models.CharField(max_length=15, blank=True, null=True)
    address = models.TextField(blank=True, null=True)

    # Frontend-driven categories
    main_category = models.CharField(max_length=120, blank=True, null=True)
    sub_category = models.CharField(max_length=120, blank=True, null=True)

    category = models.CharField(max_length=20, choices=CategoryChoices.choices)
    details = models.TextField(blank=True, null=True)

    image = models.FileField(upload_to=complaint_upload_path, null=True, blank=True)

    # ➜ NEW FIELDS
    priority = models.CharField(
        max_length=10,
        choices=PriorityChoices.choices,
        default=PriorityChoices.MEDIUM,
    )
    status = models.CharField(
        max_length=20,
        choices=StatusChoices.choices,
        default=StatusChoices.PROGRESSING
    )
    close_image = models.FileField(
        upload_to=complaint_upload_path, null=True, blank=True
    )
    action_remarks = models.TextField(blank=True, null=True)
    complaint_closed_at = models.DateTimeField(null=True, blank=True)

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created"]

    def __str__(self):
        return self.unique_id

    def save(self, *args, **kwargs):
        customer = self.customer
        if customer:
            self.zone_id = customer.zone_id
            self.ward_id = customer.ward_id
            self.contact_no = customer.contact_no
            self.address = (
                f"{customer.building_no}, "
                f"{customer.street}, "
                f"{customer.area}, "
                f"{customer.city.name if customer.city else ''}"
            )

        if self.status == "CLOSED" and not self.complaint_closed_at:
            self.complaint_closed_at = timezone.now()

        super().save(*args, **kwargs)

    @property
    def company(self):
        from app.models.superadmin_masters.company import Company
        if self.company_id:
            return Company.objects.filter(unique_id=self.company_id).first()
        return None

    @property
    def project(self):
        from app.models.superadmin_masters.project import Project
        if self.project_id:
            return Project.objects.filter(unique_id=self.project_id).first()
        return None

    @property
    def customer(self):
        from app.models.customers.customercreation import CustomerCreation
        if self.customer_id:
            return CustomerCreation.objects.filter(unique_id=self.customer_id).first()
        return None

    @property
    def zone(self):
        from app.models.masters.zone import Zone
        if self.zone_id:
            return Zone.objects.filter(unique_id=self.zone_id).first()
        return None

    @property
    def ward(self):
        from app.models.masters.ward import Ward
        if self.ward_id:
            return Ward.objects.filter(unique_id=self.ward_id).first()
        return None
