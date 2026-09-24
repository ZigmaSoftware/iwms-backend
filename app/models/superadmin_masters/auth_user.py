from django.db import models
from django.db.models import Q
from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)

from app.utils.base_models import BaseMaster

from app.utils.comfun import generate_unique_id


def generate_user_id():
    return f"SUPUSER-{generate_unique_id()}"


class UserManager(BaseUserManager):
    """
    Custom user manager to support Django's createsuperuser flow.

    We intentionally keep 'username' only strictly required for platform super admins.
    Staff/customer users can still authenticate via the existing business login flow.
    """

    def create_user(self, username=None, password=None, **extra_fields):
        # DB constraint requires non-superusers to belong to a company.
        is_superuser = bool(extra_fields.get("is_superuser"))
        if not is_superuser and not extra_fields.get("company_id"):
            raise ValueError("Non-superusers must belong to a company")

        user = self.model(username=username, **extra_fields)
        if password:
            user.set_password(password)
        else:
            # Allow system-created users that will set a password later.
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, username, password, **extra_fields):
        if not username:
            raise ValueError("Superuser must have a username")
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("is_deleted", False)
        extra_fields["is_superuser"] = True  # from PermissionsMixin

        # Platform authority must not be mixed with tenant/business identity.
        extra_fields["company_id"] = None
        extra_fields["project_id"] = None
        extra_fields["user_type_id"] = None
        extra_fields["staffusertype_id"] = None
        extra_fields["staff_id"] = None
        extra_fields["customer_id"] = None

        user = self.model(username=username, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user


class User(BaseMaster, AbstractBaseUser, PermissionsMixin):

    company_id = models.CharField(max_length=30, null=True, blank=True)
    project_id = models.CharField(max_length=30, null=True, blank=True)

    # -----------------------------
    # Core User Identity
    # -----------------------------
    username = models.CharField(
        max_length=150,
        unique=True,
        null=True,
        blank=True,
        help_text="Required for platform super admins. Staff users may be created without it.",
    )

    email = models.EmailField(
        null=True,
        blank=True,
    )

    unique_id = models.CharField(
        max_length=100,
        primary_key=True,
        default=generate_user_id,
        editable=False,
    )

    user_type_id = models.CharField(max_length=30, null=True, blank=True)

    # -----------------------------
    # STAFF-RELATED FIELDS
    # -----------------------------
    staffusertype_id = models.CharField(max_length=30, null=True, blank=True)

    staff_id = models.CharField(max_length=30, null=True, blank=True)

    # -----------------------------
    # CUSTOMER-RELATED FIELD
    # -----------------------------
    customer_id = models.CharField(max_length=30, null=True, blank=True)

    # -----------------------------
    # LOCATION FIELDS
    # -----------------------------
    district_id = models.CharField(max_length=30, null=True, blank=True)

    city_id = models.CharField(max_length=30, null=True, blank=True)

    zone_id = models.CharField(max_length=30, null=True, blank=True)

    ward_id = models.CharField(max_length=30, null=True, blank=True)

    # -----------------------------
    # SYSTEM FIELDS
    # -----------------------------
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    is_staff = models.BooleanField(
        default=False,
        help_text="Django admin-site access flag (not a business role).",
    )
    is_active = models.BooleanField(default=True)

    objects = UserManager()

    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = []

    class Meta:
        db_table = "auth_user"
        ordering = ["-created_at"]
        verbose_name = "User"
        verbose_name_plural = "Users"
        constraints = [
            # Platform super admins must not be attached to any tenant/business identity.
            models.CheckConstraint(
                name="platform_superuser_no_tenant_links",
                check=(
                    Q(is_superuser=False)
                    | (
                        Q(is_superuser=True)
                        & Q(staff_id__isnull=True)
                        & Q(customer_id__isnull=True)
                    )
                ),
            ),
            
        ]

    def __str__(self):
        return self.username or self.unique_id

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
    def user_type(self):
        from app.models.superadmin.role_management.userType import UserType
        if self.user_type_id:
            return UserType.objects.filter(unique_id=self.user_type_id).first()
        return None

    @property
    def staffusertype(self):
        from app.models.superadmin.role_management.staffUserType import StaffUserType
        if self.staffusertype_id:
            return StaffUserType.objects.filter(unique_id=self.staffusertype_id).first()
        return None

    @property
    def staff(self):
        from app.models.superadmin.staff_management.staffcreation import StaffcreationOfficeDetails
        if self.staff_id:
            return StaffcreationOfficeDetails.objects.filter(staff_unique_id=self.staff_id).first()
        return None

    @property
    def customer(self):
        from app.models.masters.customer_masters.customercreation import CustomerCreation
        if self.customer_id:
            return CustomerCreation.objects.filter(unique_id=self.customer_id).first()
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