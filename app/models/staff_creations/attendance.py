from django.db import models

from app.utils.comfun import generate_unique_id


def generate_employee_unique_id():
    return f"EMP-{generate_unique_id()}"


def generate_recognized_unique_id():
    return f"REC-{generate_unique_id()}"


class Employee(models.Model):
    company_id = models.CharField(max_length=30, null=True, blank=True)
    project_id = models.CharField(max_length=30, null=True, blank=True)

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_employee_unique_id,
        editable=False,
    )
    emp_id = models.CharField(max_length=8, unique=True)
    staff_id = models.CharField(max_length=30, unique=True)
    name = models.CharField(max_length=100)
    department = models.CharField(max_length=100)
    image_path = models.CharField(max_length=255)
    qr_code_path = models.CharField(max_length=255, null=True, blank=True)
    dob = models.DateField(null=True, blank=True)
    blood_group = models.CharField(max_length=10, null=True, blank=True)
    # Face vector for the reference photo at image_path, written when
    # attendance is running on a provider that compares embeddings
    # (InsightFace) so a punch only has to process the incoming selfie.
    # Stays null under CompreFace, which compares the two image files on its
    # own server and has nothing to cache here. Because it is only a cache of
    # `image_path`, it is cleared whenever that image is replaced and can
    # always be rebuilt from it.
    face_embedding = models.JSONField(
        blank=True,
        null=True,
        editable=False,
        help_text=(
            "Cached face vector derived from image_path. Provider-specific; "
            "cleared and recomputed when the reference image changes."
        ),
    )

    class Meta:
        indexes = [
            models.Index(fields=["emp_id"]),
            models.Index(fields=["staff_id"]),
        ]

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
    def staff(self):
        from app.models.staff_creations.staffcreation import Staffcreation
        if self.staff_id:
            return Staffcreation.objects.filter(staff_unique_id=self.staff_id).first()
        return None


class Recognized(models.Model):
    company_id = models.CharField(max_length=30, null=True, blank=True)
    project_id = models.CharField(max_length=30, null=True, blank=True)

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_recognized_unique_id,
        editable=False,
    )

    staff_id = models.CharField(max_length=30)
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
        indexes = [
            models.Index(fields=["emp_id"]),
            models.Index(fields=["staff_id"]),
        ]

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
    def staff(self):
        from app.models.staff_creations.staffcreation import Staffcreation
        if self.staff_id:
            return Staffcreation.objects.filter(staff_unique_id=self.staff_id).first()
        return None
