from django.db import models
from django.contrib.auth.hashers import make_password

from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id


def generate_panchayat_leader_id():
    return f"PLDR-{generate_unique_id()}"


class PanchayatLeaderLogin(BaseMaster):
    """
    Login credentials for a panchayat local-body leader.
    Each record is scoped to exactly one Panchayat.
    """

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        unique=True,
        editable=False,
        default=generate_panchayat_leader_id,
    )

    panchayat_id = models.CharField(max_length=30, null=True, blank=True)

    company_id = models.CharField(max_length=30, null=True, blank=True)
    project_id = models.CharField(max_length=30, null=True, blank=True)

    username = models.CharField(
        max_length=150,
        help_text="Login username for the panchayat leader.",
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
        help_text="Full name of the panchayat leader.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    CASCADE_SOFT_DELETE = ()
    CACHE_SCOPES = ("panchayat_leader_login_list", "panchayat_leader_login_detail")

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Panchayat Leader Login"
        verbose_name_plural = "Panchayat Leader Logins"

    def __str__(self):
        from app.models.masters.panchayat import Panchayat
        panchayat_name = Panchayat.objects.filter(unique_id=self.panchayat_id).values_list("panchayat_name", flat=True).first()
        return f"{self.username} ({panchayat_name if panchayat_name else '—'})"

    # Required by DRF permission system
    @property
    def is_authenticated(self):
        return True

    @property
    def panchayat(self):
        from app.models.masters.panchayat import Panchayat
        if self.panchayat_id:
            return Panchayat.objects.filter(unique_id=self.panchayat_id).first()
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