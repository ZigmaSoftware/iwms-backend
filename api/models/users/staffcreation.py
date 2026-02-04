from django.db import models
from api.utils.tenancy import CompanyProjectMixin
from api.utils.comfun import generate_unique_id
from .userType import UserType
from .staffUserType import StaffUserType
from api.models.masters.district import District
from api.models.masters.city import City
from api.models.masters.zone import Zone
from api.models.masters.ward import Ward


def generate_staff_unique_id():
    """Generate readable prefixed ID, e.g., ST-20251028001"""
    return f"ST-{generate_unique_id()}"


class StaffOfficeDetails(CompanyProjectMixin, models.Model):
    staff_unique_id = models.CharField(
        max_length=30,
        unique=True,
        default=generate_staff_unique_id
    )
    emp_id = models.CharField(
        max_length=8,
        unique=True,
        blank=True,
        null=True,
        editable=False,
    )
    employee_name = models.CharField(max_length=200)
    doj = models.DateField(blank=True, null=True)
    department = models.CharField(max_length=200, blank=True, null=True)
    designation = models.CharField(max_length=200, blank=True, null=True)
    department_id = models.CharField(max_length=30, blank=True, null=True)
    designation_id = models.CharField(max_length=20, blank=True, null=True)

    grade = models.CharField(max_length=50, blank=True, null=True)
    site_name = models.CharField(max_length=200, blank=True, null=True)
    biometric_id = models.CharField(max_length=100, blank=True, null=True)
    staff_head = models.CharField(max_length=200, blank=True, null=True)
    staff_head_id = models.CharField(max_length=30, blank=True, null=True)
    employee_known = models.CharField(max_length=20, blank=True, null=True)
    photo = models.ImageField(upload_to="staff_photos/", blank=True, null=True)
    active_status = models.BooleanField(default=True)
    salary_type = models.CharField(max_length=50, blank=True, null=True)

    # Driving Licence Fields
    driving_licence_no = models.CharField(
        max_length=50,
        blank=True,
        null=True
    )
    driving_licence_file = models.FileField(
        upload_to="staff_licences/",
        blank=True,
        null=True
    )

    # =============================================
    # AUTHENTICATION FIELDS (from User model)
    # =============================================
    username = models.CharField(
        max_length=150,
        unique=True,
        null=True,
        blank=True,
        help_text="Required for platform super admins. Staff users may be created without it."
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
        help_text="Django admin-site access flag (not a business role).",
    )

    is_active = models.BooleanField(default=True)

    is_deleted = models.BooleanField(default=False)

    is_superuser = models.BooleanField(default=False)

    # Type Links
    user_type_id = models.ForeignKey(
        UserType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column="user_type_id",
        related_name="staff_users"
    )

    staffusertype_id = models.ForeignKey(
        StaffUserType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column="staffusertype_id",
        related_name="staff_users"
    )

    # -----------------------------
    # LOCATION FIELDS (match auth_user)
    # -----------------------------
    district_id = models.ForeignKey(
        District,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column="district_id",
        related_name="staff_district"
    )

    city_id = models.ForeignKey(
        City,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column="city_id",
        related_name="staff_city"
    )

    zone_id = models.ForeignKey(
        Zone,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column="zone_id",
        related_name="staff_zone"
    )

    ward_id = models.ForeignKey(
        Ward,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column="ward_id",
        related_name="staff_ward"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "api_staff_officedetails"
        ordering = ["-id"]

    def __str__(self):
        return f"{self.employee_name} ({self.staff_unique_id})"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        if not self.emp_id:
            display_id = f"{self.id:08d}"
            StaffOfficeDetails.objects.filter(
                pk=self.pk,
                emp_id__isnull=True,
            ).update(emp_id=display_id)
            self.emp_id = display_id

    @property
    def is_authenticated(self):
        """
        Always return True for authenticated users.
        Required by Django REST Framework's permission system.
        """
        return True


class StaffPersonalDetails(CompanyProjectMixin, models.Model):
    staff = models.OneToOneField(
        StaffOfficeDetails,
        on_delete=models.CASCADE,
        related_name="personal_details"
    )
    staff_unique_id = models.CharField(max_length=30, blank=True, null=True)
    marital_status = models.CharField(max_length=50, blank=True, null=True)
    dob = models.DateField(blank=True, null=True)
    blood_group = models.CharField(max_length=20, blank=True, null=True)
    gender = models.CharField(max_length=20, blank=True, null=True)
    physically_challenged = models.CharField(max_length=20, blank=True, null=True)
    extra_curricular = models.TextField(blank=True, null=True)
    present_address = models.JSONField(blank=True, null=True)
    permanent_address = models.JSONField(blank=True, null=True)
    contact_mobile = models.CharField(max_length=20, blank=True, null=True)
    contact_email = models.EmailField(max_length=254, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "api_staff_personaldetails"
        ordering = ["-id"]

    def __str__(self):
        return f"Personal details for {self.staff.employee_name}"
