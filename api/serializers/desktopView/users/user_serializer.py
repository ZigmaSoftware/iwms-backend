from rest_framework import serializers
from api.apps.userCreation import User
from api.apps.userType import UserType
from api.apps.customercreation import CustomerCreation
from api.apps.staffcreation import StaffOfficeDetails


class UniqueIdOrPkField(serializers.SlugRelatedField):
    """
    Accept a related object by unique_id (slug) or numeric PK; serialize as unique_id.
    """

    def to_representation(self, value):
        return getattr(value, self.slug_field, None) or super().to_representation(value)

    def to_internal_value(self, data):
        try:
            return super().to_internal_value(data)
        except Exception:
            try:
                return self.get_queryset().get(pk=data)
            except Exception:
                raise


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
    staff_maritalStatus = serializers.CharField(source="staff_id.personal_details.marital_status", read_only=True)
    staff_dob = serializers.DateField(source="staff_id.personal_details.dob", read_only=True)
    staff_blood_group = serializers.CharField(source="staff_id.personal_details.blood_group", read_only=True)
    staff_gender = serializers.CharField(source="staff_id.personal_details.gender", read_only=True)
    staff_physical_status = serializers.CharField(source="staff_id.personal_details.physically_challenged", read_only=True)
    staff_extra_curricular = serializers.CharField(source="staff_id.personal_details.extra_curricular", read_only=True)
    staff_present_address = serializers.JSONField(source="staff_id.personal_details.present_address", read_only=True)
    staff_permanent_address = serializers.JSONField(source="staff_id.personal_details.permanent_address", read_only=True)
    staff_contact_details = serializers.JSONField(source="staff_id.personal_details.contact_details", read_only=True)

    # ---------- CUSTOMER IDENTIFIER ----------
    customer_id = UniqueIdOrPkField(
        slug_field="unique_id",
        queryset=CustomerCreation.objects.all(),
        required=False,
        allow_null=True,
    )

    # ---------- LOCATION ----------
    district_name = serializers.CharField(source="district_id.name", read_only=True)
    city_name = serializers.CharField(source="city_id.name", read_only=True)
    zone_name = serializers.CharField(source="zone_id.name", read_only=True)
    ward_name = serializers.CharField(source="ward_id.name", read_only=True)

    class Meta:
        model = User
        fields = "__all__"
        extra_kwargs = {
            # Hide raw FK for user_type; we expose user_type_id instead
            "user_type": {"write_only": True},
        }

    # ---------- VALIDATION ----------
    def validate(self, attrs):
        user_type = attrs.get("user_type")

        if not user_type:
            return attrs

        name = user_type.name.lower().strip()

        # CUSTOMER VALIDATION
        if name == "customer":
            if not attrs.get("customer_id"):
                raise serializers.ValidationError({
                    "customer_id": "customer_id is required when user type is Customer."
                })

            if attrs.get("staffusertype_id") or attrs.get("staff_id"):
                raise serializers.ValidationError("Staff fields are not allowed for Customer.")

        # STAFF VALIDATION
        if name == "staff":

            if not attrs.get("staffusertype_id"):
                raise serializers.ValidationError({
                    "staffusertype_id": "staffusertype_id is required when user type is Staff."
                })

            if not attrs.get("staff_id"):
                raise serializers.ValidationError({
                    "staff_id": "staff_id is required when user type is Staff."
                })

            if attrs.get("customer_id"):
                raise serializers.ValidationError("customer_id is not allowed for Staff.")

        return attrs
