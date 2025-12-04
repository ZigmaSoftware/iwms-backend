from django.db import models
from .utils.comfun import generate_unique_id


def generate_staff_unique_id():
    """Generate readable prefixed ID, e.g., ST-20251028001"""
    return f"ST-{generate_unique_id()}"


class StaffOfficeDetails(models.Model):
    staff_unique_id = models.CharField(
        max_length=30,
        unique=True,
        default=generate_staff_unique_id
    )
    employee_name = models.CharField(max_length=200)
    # employee_id = models.CharField(max_length=50, blank=True, null=True)
    doj = models.DateField(blank=True, null=True)
    department = models.CharField(max_length=200, blank=True, null=True)
    designation = models.CharField(max_length=200, blank=True, null=True)
    department_id = models.CharField(max_length=30, blank=True,null=True)
    designation_id = models.CharField(max_length=20, blank=True, null=True)
    
    grade = models.CharField(max_length=50, blank=True, null=True)
    site_name = models.CharField(max_length=200, blank=True, null=True)
    biometric_id = models.CharField(max_length=100, blank=True, null=True)
    staff_head = models.CharField(max_length=200, blank=True, null=True)
    staff_head_id = models.CharField(max_length=30, blank=True, null=True)
    employee_known = models.CharField(max_length=20, blank=True, null=True)
    photo = models.ImageField(upload_to="staff_photos/", blank=True, null=True)
    active_status = models.BooleanField(default=True)
    salary_type = models.CharField(max_length=50, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "api_officedetails"
        ordering = ["-id"]

    def __str__(self):
        return f"{self.employee_name} ({self.staff_unique_id})"


class StaffPersonalDetails(models.Model):
    staff = models.OneToOneField(
        StaffOfficeDetails,
        on_delete=models.CASCADE,
        related_name="personal_details"
    )
    staff_unique_id = models.CharField(max_length=30, blank=True, null=True)
    marital_status = models.CharField(max_length=50, blank=True, null=True)
    dob = models.DateField(blank=True, null=True)
    blood_group = models.CharField(max_length=20, blank=True, null=True)
    gender = models.CharField(max_length=20, blank=True, null=True)
    physically_challenged = models.CharField(max_length=20, blank=True, null=True)
    extra_curricular = models.TextField(blank=True, null=True)
    present_address = models.JSONField(blank=True, null=True)
    permanent_address = models.JSONField(blank=True, null=True)
    contact_mobile = models.CharField(max_length=20, blank=True, null=True)
    contact_email = models.EmailField(max_length=254, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "api_personaldetails"
        ordering = ["-id"]

    def __str__(self):
        return f"Personal details for {self.staff.employee_name}"
