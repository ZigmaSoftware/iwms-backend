from django.db import models
from django.contrib.auth.hashers import make_password

from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id


def generate_district_leader_id():
    return f"DLDR-{generate_unique_id()}"


class DistrictLeaderLogin(BaseMaster):
    """
    Login credentials for a district leader.
    Each record is scoped to exactly one District.
    """

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        unique=True,
        editable=False,
        default=generate_district_leader_id,
    )

    district_id = models.CharField(max_length=30, null=True, blank=True)

    company_id = models.CharField(max_length=30, null=True, blank=True)
    project_id = models.CharField(max_length=30, null=True, blank=True)

    username = models.CharField(
        max_length=150,
        help_text="Login username for the district leader.",
    )

    password = models.CharField(
        max_length=128,
        help_text="Hashed password (Django PBKDF2).",
    )

    email = models.EmailField(
        blank=True,
        null=True,
    )

    leader_name = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        help_text="Full name of the district leader.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    CASCADE_SOFT_DELETE = ()
    CACHE_SCOPES = ("district_leader_login_list", "district_leader_login_detail")

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "District Leader Login"
        verbose_name_plural = "District Leader Logins"

    def __str__(self):
        from app.models.masters.district import District
        district_name = District.objects.filter(unique_id=self.district_id).values_list("name", flat=True).first()
        return f"{self.username} ({district_name if district_name else '—'})"

    # Required by DRF permission system
    @property
    def is_authenticated(self):
        return True

    @property
    def district(self):
        from app.models.masters.district import District
        if self.district_id:
            return District.objects.filter(unique_id=self.district_id).first()
        return None

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