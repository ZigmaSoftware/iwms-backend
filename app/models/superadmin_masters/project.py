from django.db import models
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id


def generate_project_id():
    return f"PROJ-{generate_unique_id()}"


class Project(BaseMaster):
    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        unique=True,
        default=generate_project_id,
    )

    company_id = models.CharField(max_length=30, null=True, blank=True)

    name = models.CharField(max_length=150)
    description = models.TextField(blank=True, null=True)

    # Local-body / authority emblem printed on customer QR stickers.
    project_logo = models.ImageField(
        upload_to="project_logos/",
        blank=True,
        null=True,
    )
    
    # GPS API URLs (Vamosys)
    gps_api_url = models.URLField(max_length=500, blank=True, null=True)  # Legacy - kept for backward compatibility
    gps_vehicle_history_api = models.URLField(max_length=500, blank=True, null=True)
    gps_vehicle_tracking_api = models.URLField(max_length=500, blank=True, null=True)
    gps_trip_summary_api = models.URLField(max_length=500, blank=True, null=True)
    
    # GPS API Parameters
    gps_user_id = models.CharField(max_length=255, default="BLUEPLANET", blank=True)
    gps_group_name = models.CharField(max_length=255, default="BLUEPLANET:VAM", blank=True)
    gps_provider_name = models.CharField(max_length=255, default="BLUEPLANET", blank=True)
    gps_fcode = models.CharField(max_length=50, default="VAM", blank=True)
    gps_trip_user_id = models.CharField(max_length=255, default="NMCP2DISPOSAL", blank=True)
    
    # Other APIs
    weighment_api_url = models.URLField(max_length=500, blank=True, null=True)
    day_wise_weighment_api_url = models.URLField(max_length=500, blank=True, null=True)
    attendance_api_url = models.URLField(max_length=500, blank=True, null=True)
    attendance_api_key = models.CharField(max_length=255, blank=True, null=True)

    CASCADE_SOFT_DELETE = (
        "district_set",
        "plants",
        "departments",
        "designations",
        "staff_office_details",
        "staff_personal_details",
        "staff_templates",
        "staffusertype_set",
        "contractorusertype_set",
        "usertype_set",
        "wastetype_set",
        "mainscreentype_set",
        "mainscreen_set",
        "userscreen_set",
        "userscreenaction_set",
        "userscreen_column_permissions",
        "user_set",
        "maincategory_set",
        "complaint_set",
        "complaint_categories",
        "complaint_subcategories",
        "complaint_sla_rules",
        "property_set",
        "subproperty_set",
        "staff_hierarchy_levels",
    )
    CACHE_SCOPES = ("project_list", "project_detail")

    class Meta:
        ordering = ["name"]

    def __str__(self):
        from app.models.superadmin_masters.company import Company
        company_name = Company.objects.filter(unique_id=self.company_id).values_list("name", flat=True).first()
        return f"{self.name} ({company_name})"

    @property
    def company(self):
        from app.models.superadmin_masters.company import Company
        if self.company_id:
            return Company.objects.filter(unique_id=self.company_id).first()
        return None