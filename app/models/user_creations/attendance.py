from django.db import models

from app.models.user_creations.staffcreation import StaffOfficeDetails


class Employee(models.Model):
    company_id = models.ForeignKey(
        "api.Company",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="company_id",
    )
    project_id = models.ForeignKey(
        "api.Project",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="project_id",
    )

    emp_id = models.CharField(max_length=8, unique=True)
    staff = models.OneToOneField(
        StaffOfficeDetails,
        on_delete=models.PROTECT,
        to_field="staff_unique_id",
        db_column="staff_id",
        related_name="attendance_profile",
    )
    name = models.CharField(max_length=100)
    department = models.CharField(max_length=100)
    image_path = models.CharField(max_length=255)
    qr_code_path = models.CharField(max_length=255, null=True, blank=True)
    dob = models.DateField(null=True, blank=True)
    blood_group = models.CharField(max_length=10, null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["emp_id"]),
            models.Index(fields=["staff"]),
        ]

class Recognized(models.Model):
    company_id = models.ForeignKey(
        "api.Company",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="company_id",
    )
    project_id = models.ForeignKey(
        "api.Project",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="project_id",
    )

    staff = models.ForeignKey(
        StaffOfficeDetails,
        on_delete=models.PROTECT,
        to_field="staff_unique_id",
        db_column="staff_id",
        related_name="recognitions",
    )
    emp_id = models.CharField(max_length=8)
    emp_id_raw = models.CharField(max_length=50, null=True)
    name = models.CharField(max_length=100)
    records = models.DateTimeField()
    captured_image_path = models.CharField(max_length=255)
    similarity_score = models.FloatField()
    latitude = models.CharField(max_length=50)
    longitude = models.CharField(max_length=50)
    recognition_date = models.DateField()
    recognition_time = models.TimeField()
    punch_type = models.CharField(max_length=3, default="IN")

    class Meta:
        db_table = "api_attendance_recognized"
        indexes = [
            models.Index(fields=["emp_id"]),
            models.Index(fields=["staff"]),
        ]
