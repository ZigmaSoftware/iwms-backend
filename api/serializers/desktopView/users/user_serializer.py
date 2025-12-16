from rest_framework import serializers
from django.db.models import Q

from api.apps.userCreation import User
from api.apps.customercreation import CustomerCreation
from api.apps.staffcreation import StaffOfficeDetails


class UniqueIdOrPkField(serializers.SlugRelatedField):
    """
    Accept related object via unique_id (slug) or numeric PK.
    Serialize always as unique_id.
    """

    def to_representation(self, value):
        return getattr(value, self.slug_field, None)

    def to_internal_value(self, data):
        try:
            return super().to_internal_value(data)
        except Exception:
            try:
                return self.get_queryset().get(pk=data)
            except Exception:
                raise serializers.ValidationError("Invalid reference value")


class UserSerializer(serializers.ModelSerializer):

    # ---------- USER TYPE DISPLAY ----------
    user_type_name = serializers.CharField(source="user_type.name", read_only=True)
    user_type_id = serializers.CharField(source="user_type.unique_id", read_only=True)

    # ---------- STAFF BASIC DETAILS ----------
    staffusertype_name = serializers.CharField(source="staffusertype_id.name", read_only=True)
    staff_name = serializers.CharField(source="staff_id.employee_name", read_only=True)
    staff_doj = serializers.DateField(source="staff_id.doj", read_only=True)
    staff_designation = serializers.CharField(source="staff_id.designation", read_only=True)
    staff_department = serializers.CharField(source="staff_id.department", read_only=True)
    staff_grade = serializers.CharField(source="staff_id.grade", read_only=True)
    staff_siteName = serializers.CharField(source="staff_id.site_name", read_only=True)
    staff_biometricId = serializers.CharField(source="staff_id.biometric_id", read_only=True)
    staff_staff_head = serializers.CharField(source="staff_id.staff_head", read_only=True)
    staff_employee_known_as = serializers.CharField(source="staff_id.employee_known", read_only=True)
    staff_photo = serializers.ImageField(source="staff_id.photo", read_only=True)
    staff_salaryType = serializers.CharField(source="staff_id.salary_type", read_only=True)
    staff_activeStatus = serializers.BooleanField(source="staff_id.active_status", read_only=True)

    staff_id = UniqueIdOrPkField(
        slug_field="staff_unique_id",
        queryset=StaffOfficeDetails.objects.all(),
        required=False,
        allow_null=True,
    )

    # ---------- STAFF PERSONAL DETAILS ----------
    staff_contact_mobile = serializers.CharField(
        source="staff_id.personal_details.contact_mobile", read_only=True
    )
    staff_contact_email = serializers.EmailField(
        source="staff_id.personal_details.contact_email", read_only=True
    )

    # ---------- CUSTOMER ----------
    customer_id = UniqueIdOrPkField(
        slug_field="unique_id",
        queryset=CustomerCreation.objects.all(),
        required=False,
        allow_null=True,
    )
    customer_name = serializers.CharField(source="customer_id.customer_name", read_only=True)
    customer_contact=serializers.CharField(source="customer_id.customer_contact_no", read_only=True)
    customer_city = serializers.CharField(source="customer_id.city.name", read_only=True)
    customer_district = serializers.CharField(source="customer_id.district.name", read_only=True)
    customer_zone = serializers.CharField(source="customer_id.zone.name", read_only=True)
    customer_ward = serializers.CharField(source="customer_id.ward.name", read_only=True)

    # ---------- LOCATION ----------
    district_name = serializers.CharField(source="district_id.name", read_only=True)
    city_name = serializers.CharField(source="city_id.name", read_only=True)
    zone_name = serializers.CharField(source="zone_id.name", read_only=True)
    ward_name = serializers.CharField(source="ward_id.name", read_only=True)

    class Meta:
        model = User
        fields = "__all__"
        extra_kwargs = {
            "user_type": {"write_only": True},
        }

    # ==================================================
    # VALIDATION (PHONE-FIRST + PASSWORD UNIQUE)
    # ==================================================
    def validate(self, attrs):
        instance = getattr(self, "instance", None)

        user_type = attrs.get("user_type") or (instance.user_type if instance else None)
        if not user_type:
            return attrs

        staff_id = attrs.get("staff_id") or (instance.staff_id if instance else None)
        staffusertype_id = attrs.get("staffusertype_id") or (
            instance.staffusertype_id if instance else None
        )
        customer_id = attrs.get("customer_id") or (instance.customer_id if instance else None)

        # ==================================================
        # STEP 1: RESOLVE PHONE (PRIMARY IDENTITY)
        # ==================================================
        phone = None

        if staff_id and hasattr(staff_id, "personal_details"):
            phone = staff_id.personal_details.contact_mobile

        elif customer_id:
            phone = customer_id.contact_no

        # ==================================================
        # STEP 2: GLOBAL PHONE DUPLICATE CHECK
        # ==================================================
        if phone:
            duplicate_qs = User.objects.filter(
                is_deleted=False
            ).filter(
                Q(staff_id__personal_details__contact_mobile=phone) |
                Q(customer_id__contact_no=phone)
            )

            if instance:
                duplicate_qs = duplicate_qs.exclude(pk=instance.pk)

            if duplicate_qs.exists():
                raise serializers.ValidationError({
                    "non_field_errors": (
                        "This contact number already exists in the system. "
                        "The same person cannot be created again as Staff or Customer."
                    )
                })

        # ==================================================
        # STEP 3: PASSWORD UNIQUENESS CHECK 
        # ==================================================
        password = attrs.get("password")
        if password:
            pwd_qs = User.objects.filter(
                is_deleted=False,
                password=password
            )

            if instance:
                pwd_qs = pwd_qs.exclude(pk=instance.pk)

            if pwd_qs.exists():
                raise serializers.ValidationError({
                    "password": "This password is already in use. Please choose a different password."
                })

        # ==================================================
        # STEP 4: STRUCTURAL VALIDATION
        # ==================================================
        user_type_name = user_type.name.lower().strip()

        if user_type_name == "customer":

            if not customer_id:
                raise serializers.ValidationError({
                    "customer_id": "customer_id is required when user type is Customer."
                })

            if staff_id or staffusertype_id:
                raise serializers.ValidationError(
                    "Staff fields are not allowed for Customer."
                )

        elif user_type_name == "staff":

            if not staffusertype_id:
                raise serializers.ValidationError({
                    "staffusertype_id": "staffusertype_id is required when user type is Staff."
                })

            if not staff_id:
                raise serializers.ValidationError({
                    "staff_id": "staff_id is required when user type is Staff."
                })

            if customer_id:
                raise serializers.ValidationError(
                    "customer_id is not allowed for Staff."
                )

        return attrs
