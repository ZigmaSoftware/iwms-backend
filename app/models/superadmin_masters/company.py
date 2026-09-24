from django.db import models

from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id


def generate_company_id():
    return f"CMP-{generate_unique_id()}"


class Company(BaseMaster):
    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        unique=True,
        default=generate_company_id,
    )

    name = models.CharField(max_length=150)
    description = models.TextField(blank=True, null=True)
    company_logo = models.ImageField(
        upload_to="company_logos/",
        blank=True,
        null=True,
    )

    CASCADE_SOFT_DELETE = (
        "projects",
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
        "staff_access_configurations",
        "customer_access_configurations",
        "property_set",
        "subproperty_set",
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name
