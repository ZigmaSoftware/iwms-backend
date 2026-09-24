from django.db import models
from app.utils.comfun import generate_unique_id

def generate_daily_waste_comparison_id():
    return f"DWC-{generate_unique_id()}"

class DailyWasteComparison(models.Model):
    unique_id = models.CharField(max_length=30, primary_key=True, default=generate_daily_waste_comparison_id, editable=False)
    company_id = models.CharField(max_length=30, null=True, blank=True)
    project_id = models.CharField(max_length=30, null=True, blank=True)
    panchayat_id = models.CharField(max_length=30, null=True, blank=True)
    collection_date = models.DateField()
    waste_type_id = models.CharField(max_length=100, null=True, blank=True)
    agreed_weight_kg = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    actual_weight_kg = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    variance_kg = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    variance_percent = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    report_status = models.CharField(max_length=50, blank=True, null=True)
    total_trips = models.PositiveIntegerField(default=0)
    collection_points_covered = models.PositiveIntegerField(default=0)

    class Meta:
        managed = True
        db_table = "daily_waste_comparison"
        ordering = ["-collection_date"]
        indexes = [
            models.Index(fields=["collection_date", "panchayat_id"]),
            models.Index(fields=["company_id", "project_id", "collection_date"]),
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
    def panchayat(self):
        from app.models.masters.panchayat import Panchayat
        if self.panchayat_id:
            return Panchayat.objects.filter(unique_id=self.panchayat_id).first()
        return None

    @property
    def waste_type(self):
        from app.models.staff_creations.waste_collection_bluetooth import WasteType
        if self.waste_type_id:
            return WasteType.objects.filter(unique_id=self.waste_type_id).first()
        return None
