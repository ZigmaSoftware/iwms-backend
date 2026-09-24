from django.db import models
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from app.utils.bin_qr import generate_bin_qr_content


def generate_bin_id():
    return f"BIN-{generate_unique_id()}"


class BinType(models.TextChoices):
    SMALL = "small", "Small"
    MEDIUM = "medium", "Medium"
    LARGE = "large", "Large"
   


class Bins(BaseMaster):

    CASCADE_SOFT_DELETE = ("trip_plan_cps", "daily_trip_cps", "bin_collection_events")
    CACHE_SCOPES = ("bin_list", "bin_detail")

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_bin_id,
        editable=False
    )

    company_id = models.CharField(max_length=30, null=True, blank=True)
    project_id = models.CharField(max_length=30, null=True, blank=True)

    collection_point_id = models.CharField(max_length=30, null=True, blank=True)

    district_id = models.CharField(max_length=30, null=True, blank=True)
    city_id = models.CharField(max_length=30, null=True, blank=True)
    panchayat_id = models.CharField(max_length=30, null=True, blank=True)
    zone_id = models.CharField(max_length=30, null=True, blank=True)
    ward_id = models.CharField(max_length=30, null=True, blank=True)

    wastetype_id = models.CharField(max_length=30, null=True, blank=True)

    bin_name = models.CharField(max_length=100)
    bin_capacity = models.IntegerField()
    bin_type = models.CharField(max_length=10, choices=BinType.choices)
    bin_image = models.CharField(max_length=100)
    bin_qr = models.ImageField(upload_to="bin_qr/", blank=True, null=True)

    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def _regenerate_qr_code(self):
        file_content = generate_bin_qr_content(self.unique_id)
        file_name = f"{self.unique_id}.png"
        if self.bin_qr:
            self.bin_qr.delete(save=False)
        self.bin_qr.save(file_name, file_content, save=False)
        super().save(update_fields=["bin_qr"])

    def save(self, *args, **kwargs):
        # Auto-populate geo fields from collection_point if set
        if self.collection_point_id:
            from app.models.schedule_masters.collection_point import Collection_point
            cp = Collection_point.objects.filter(unique_id=self.collection_point_id).first()
            if cp:
                self.district_id = cp.district_id
                self.city_id = cp.city_id
                if not self.panchayat_id:
                    self.panchayat_id = cp.panchayat_id
                if self.latitude is None:
                    self.latitude = cp.latitude
                if self.longitude is None:
                    self.longitude = cp.longitude

        # Auto-populate geo fields from ward if set
        if self.ward_id:
            from app.models.masters.ward import Ward
            ward = Ward.objects.filter(unique_id=self.ward_id).first()
            if ward:
                if not self.zone_id and ward.zone_id:
                    self.zone_id = ward.zone_id
                if not self.panchayat_id and ward.panchayat_id:
                    self.panchayat_id = ward.panchayat_id

        is_create = self._state.adding
        super().save(*args, **kwargs)

        if is_create or not self.bin_qr:
            self._regenerate_qr_code()

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
    def collection_point(self):
        from app.models.schedule_masters.collection_point import Collection_point
        if self.collection_point_id:
            return Collection_point.objects.filter(unique_id=self.collection_point_id).first()
        return None

    @property
    def district(self):
        from app.models.masters.district import District
        if self.district_id:
            return District.objects.filter(unique_id=self.district_id).first()
        return None

    @property
    def city(self):
        from app.models.masters.city import City
        if self.city_id:
            return City.objects.filter(unique_id=self.city_id).first()
        return None

    @property
    def panchayat(self):
        from app.models.masters.panchayat import Panchayat
        if self.panchayat_id:
            return Panchayat.objects.filter(unique_id=self.panchayat_id).first()
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

    @property
    def wastetype(self):
        from app.models.staff_creations.waste_collection_bluetooth import WasteType
        if self.wastetype_id:
            return WasteType.objects.filter(unique_id=self.wastetype_id).first()
        return None