from django.db import models
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id


def generate_block_panchayat_union_id():
    return f"BLKPU-{generate_unique_id()}"


class BlockPanchayatUnion(BaseMaster):
    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_block_panchayat_union_id,
        editable=False,
    )
    company_id = models.CharField(max_length=30, null=True, blank=True)
    project_id = models.CharField(max_length=30, null=True, blank=True)
    state_id = models.CharField(max_length=30, null=True, blank=True)
    district_id = models.CharField(max_length=30, null=True, blank=True)
    block_name = models.CharField(max_length=100)
    description = models.TextField(null=True, blank=True)
    latitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
    )
    longitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    CASCADE_SOFT_DELETE = ("panchayats",)
    CACHE_SCOPES = ("block_panchayat_union_list", "block_panchayat_union_detail")

    class Meta:
        ordering = ["block_name"]

    def __str__(self):
        return self.block_name

    @property
    def state(self):
        from app.models.superadmin.common_masters.state import State
        if self.state_id:
            return State.objects.filter(unique_id=self.state_id).first()
        return None

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

    @property
    def panchayats(self):
        from app.models.masters.panchayat import Panchayat
        return Panchayat.objects.filter(block_id=self.unique_id)