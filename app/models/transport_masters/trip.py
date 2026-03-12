from django.db import models
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from app.models.transport_masters.vehicleCreation import VehicleCreation
from app.models.user_creations.stafftemplate import StaffTemplate
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project
from app.models.user_creations.waste_collection_bluetooth import WasteType

def geneate_trip_id():
    return f"TRIP-{generate_unique_id()}"

class Trip(BaseMaster):

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=geneate_trip_id,
        editable=False
    )

    company_id = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="trip",
        db_column="company_id",
    )

    project_id = models.ForeignKey(
        Project,
        on_delete=models.PROTECT,
        related_name="trip",
        db_column="project_id",
    )

    vehicle_id = models.ForeignKey(
        VehicleCreation,
        on_delete=models.PROTECT,
        related_name="trip",
        db_column="vehicle_id",
    )

    staff_id = models.ForeignKey(
        StaffTemplate,
        on_delete=models.PROTECT,
        related_name="trip",
        db_column="staff_template_id",
        to_field="unique_id"
    )

    waste_type_id = models.ForeignKey(
        WasteType,
        on_delete=models.PROTECT,
        related_name="trip",
        db_column="waste_type_id",
        to_field="unique_id",
    )

    
    is_completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now_add=True)
