from django.db import models
from .state import State
from .district import District
from .city import City
from .zone import Zone
from .ward import Ward
from .fuel import Fuel
from .vehicleTypeCreation import VehicleTypeCreation

from .utils.comfun import generate_unique_id


def generate_vehicle_id():
    """Readable prefixed vehicle ID like VEH-20251030001"""
    return f"VEH-{generate_unique_id()}"


class VehicleAssigning(models.Model):
    unique_id = models.CharField(
        max_length=30, unique=True, default=generate_vehicle_id, editable=False
    )
    vehicle_no = models.CharField(max_length=50)
    chase_no = models.CharField(max_length=100, blank=True, null=True)
    imei_no = models.CharField(max_length=100, blank=True, null=True)
    driver_name = models.CharField(max_length=100, blank=True, null=True)
   
    driver_no = models.CharField(max_length=20, blank=True, null=True)

    vehicle_type = models.ForeignKey(
        VehicleTypeCreation, on_delete=models.SET_NULL, null=True, blank=True
    )
    fuel_type = models.ForeignKey(
        Fuel, on_delete=models.SET_NULL, null=True, blank=True
    )

    state = models.ForeignKey(State, on_delete=models.SET_NULL, null=True, blank=True)
    district = models.ForeignKey(District, on_delete=models.SET_NULL, null=True, blank=True)
    city = models.ForeignKey(City, on_delete=models.SET_NULL, null=True, blank=True)
    zone = models.ForeignKey(Zone, on_delete=models.SET_NULL, null=True, blank=True)
    ward = models.ForeignKey(Ward, on_delete=models.SET_NULL, null=True, blank=True)

    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.vehicle_no
    def delete(self, *args, **kwargs):
        """
        Soft delete: mark this Vehicle as deleted.
        """
        self.is_deleted = True
        self.is_active = False
        self.save(update_fields=["is_deleted"])
