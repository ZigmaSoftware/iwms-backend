from django.db import models
from .country import Country
from .state import State
from .district import District
from .city import City
from .zone import Zone
from .ward import Ward
from .property import Property
from .subproperty import SubProperty
from .utils.comfun import generate_unique_id


def generate_customer_id():
    """Generate readable prefixed ID, e.g., CUS-20251028001"""
    return f"CUS-{generate_unique_id()}"


class CustomerCreation(models.Model):
    class IDProofType(models.TextChoices):
        AADHAAR = "AADHAAR", "Aadhaar"
        VOTER_ID = "VOTER_ID", "Voter ID"
        PAN_CARD = "PAN_CARD", "PAN Card"
        DRIVING_LICENSE = "DL", "Driving License"
        PASSPORT = "PASSPORT", "Passport"

    unique_id = models.CharField(
        max_length=30,
        unique=True,
        default=generate_customer_id
    )
    customer_name = models.CharField(max_length=100)
    contact_no = models.CharField(max_length=10)
    building_no = models.CharField(max_length=20)
    street = models.CharField(max_length=100)
    area = models.CharField(max_length=50)

    ward = models.ForeignKey(Ward, on_delete=models.PROTECT, related_name='customer_creation', blank=True, null=True)
    zone = models.ForeignKey(Zone, on_delete=models.PROTECT, related_name='customer_creation', blank=True, null=True)
    city = models.ForeignKey(City, on_delete=models.PROTECT, related_name='customer_creation', blank=True, null=True)
    district = models.ForeignKey(District, on_delete=models.PROTECT, related_name='customer_creation', blank=True, null=True)
    state = models.ForeignKey(State, on_delete=models.PROTECT, related_name='customer_creation')
    country = models.ForeignKey(Country, on_delete=models.PROTECT, related_name='customer_creation')

    pincode = models.CharField(max_length=10)
    latitude = models.CharField(max_length=100)
    longitude = models.CharField(max_length=100)

    id_proof_type = models.CharField(
        max_length=20,
        choices=IDProofType.choices,
        blank=False,
        null=False
    )
    id_no = models.CharField(max_length=100)

    property = models.ForeignKey(Property, on_delete=models.PROTECT, related_name="customer_creation")
    sub_property = models.ForeignKey(SubProperty, on_delete=models.PROTECT, related_name="customer_creation")

    qr_code = models.CharField(max_length=400, blank=True, null=True)
    is_deleted = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Customer"
        verbose_name_plural = "Customers"
        ordering = ["customer_name"]

    def __str__(self):
        location = (
            self.zone.name if self.zone else
            self.city.name if self.city else
            self.state.name
        )
        return f"{self.customer_name} ({location})"

    def delete(self, *args, **kwargs):
        """Soft delete this record."""
        self.is_deleted = True
        self.is_active = False
        self.save(update_fields=["is_deleted", "is_active"])
