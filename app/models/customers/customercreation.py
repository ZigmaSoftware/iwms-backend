from django.db import models
from app.utils.base_models import BaseMaster
from app.models.common_masters.country import Country
from app.models.common_masters.state import State
from app.models.masters.district import District
from app.models.masters.city import City
from app.models.masters.zone import Zone
from app.models.role_assigns.userType import UserType
from app.models.role_assigns.staffUserType import StaffUserType
from app.models.masters.ward import Ward
from app.models.waste_types.property import Property
from app.models.waste_types.subproperty import SubProperty
from app.utils.comfun import generate_unique_id
from app.models.superadmin_masters.company import Company
from app.models.masters.panchayat import Panchayat
from app.models.superadmin_masters.project import Project



def generate_customer_id():
    """Generate readable prefixed ID, e.g., CUS-20251028001"""
    return f"CUS-{generate_unique_id()}"

class CustomerCreation(BaseMaster):
    company_id = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="company_id",
    )
    project_id = models.ForeignKey(
        Project,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="project_id",
    )

    class IDProofType(models.TextChoices):
        AADHAAR = "AADHAAR", "Aadhaar"
        VOTER_ID = "VOTER_ID", "Voter ID"
        PAN_CARD = "PAN_CARD", "PAN Card"
        DRIVING_LICENSE = "DL", "Driving License"
        PASSPORT = "PASSPORT", "Passport"

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_customer_id,
        editable=False,
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

    panchayat_id = models.ForeignKey(
        Panchayat,
        on_delete=models.PROTECT,
        related_name="customer_creations",
        db_column="panchayat_id",
        blank=True,
        null=True
    )
    sqft = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )

    id_proof_type = models.CharField(
        max_length=20,
        choices=IDProofType.choices,
        blank=False,
        null=False
    )
    id_no = models.CharField(max_length=100)

    property_ref = models.ForeignKey(Property, on_delete=models.PROTECT, related_name="customer_creation", db_column="property")
    sub_property = models.ForeignKey(SubProperty, on_delete=models.PROTECT, related_name="customer_creation")

    # =============================================
    # AUTHENTICATION FIELDS (from User model)
    # =============================================
    username = models.CharField(
        max_length=150,
        unique=True,
        null=True,
        blank=True,
        help_text="Customer login identifier"
    )

    email = models.EmailField(
        null=True,
        blank=True,
    )

    password = models.CharField(
        max_length=128,
        null=True,
        blank=True,
        help_text="Django auth password field"
    )

    is_staff = models.BooleanField(
        default=False,
        help_text="Django admin-site access flag.",
    )

    is_superuser = models.BooleanField(default=False)
    is_bulkwaste_generator = models.BooleanField(default=False)

    user_type_id = models.ForeignKey(
        UserType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column="user_type_id",
        related_name="customer_users"
    )

    staffusertype_id = models.ForeignKey(
        StaffUserType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column="staffusertype_id",
        related_name="customer_users"
    )

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

    @property
    def is_authenticated(self):
        """
        Always return True for authenticated users.
        Required by Django REST Framework's permission system.
        """
        return True
    

# raise, ape