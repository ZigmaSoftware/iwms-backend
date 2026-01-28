from rest_framework import serializers

from api.apps.staffcreation import StaffOfficeDetails, StaffPersonalDetails


class StaffcreationSerializer(serializers.ModelSerializer):
    # --------------------------------------------------
    # Core identifiers
    # --------------------------------------------------
    unique_id = serializers.CharField(source="staff_unique_id", read_only=True)
    emp_id = serializers.CharField(read_only=True)

    # --------------------------------------------------
    # ✅ Office-level: Driving licence
    # --------------------------------------------------
    driving_licence_no = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
    )
    driving_licence_file = serializers.FileField(
        required=False,
        allow_null=True,
    )

    # --------------------------------------------------
    # Personal details (flattened from StaffPersonalDetails)
    # --------------------------------------------------
    marital_status = serializers.CharField(
        source="personal_details.marital_status",
        required=False,
        allow_blank=True,
        allow_null=True,
    )
    dob = serializers.DateField(
        source="personal_details.dob",
        required=False,
        allow_null=True,
    )
    blood_group = serializers.CharField(
        source="personal_details.blood_group",
        required=False,
        allow_blank=True,
        allow_null=True,
    )
    gender = serializers.CharField(
        source="personal_details.gender",
        required=False,
        allow_blank=True,
        allow_null=True,
    )
    physically_challenged = serializers.CharField(
        source="personal_details.physically_challenged",
        required=False,
        allow_blank=True,
        allow_null=True,
    )
    extra_curricular = serializers.CharField(
        source="personal_details.extra_curricular",
        required=False,
        allow_blank=True,
        allow_null=True,
    )
    present_address = serializers.JSONField(
        source="personal_details.present_address",
        required=False,
        allow_null=True,
    )
    permanent_address = serializers.JSONField(
        source="personal_details.permanent_address",
        required=False,
        allow_null=True,
    )
    contact_mobile = serializers.CharField(
        source="personal_details.contact_mobile",
        required=False,
        allow_blank=True,
        allow_null=True,
    )
    contact_email = serializers.EmailField(
        source="personal_details.contact_email",
        required=False,
        allow_blank=True,
        allow_null=True,
    )

    # --------------------------------------------------
    # Internal mapping for personal table
    # --------------------------------------------------
    personal_field_names = [
        "marital_status",
        "dob",
        "blood_group",
        "gender",
        "physically_challenged",
        "extra_curricular",
        "present_address",
        "permanent_address",
        "contact_mobile",
        "contact_email",
    ]

    class Meta:
        model = StaffOfficeDetails
        fields = [
            "id",
            "unique_id",
            "emp_id",

            # Office details
            "employee_name",
            "doj",
            "department",
            "designation",
            "department_id",
            "designation_id",
            "staff_head_id",
            "grade",
            "site_name",
            "biometric_id",
            "staff_head",
            "employee_known",
            "photo",

            # ✅ Driving licence
            "driving_licence_no",
            "driving_licence_file",

            "active_status",
            "salary_type",

            # Personal details (flattened)
            "marital_status",
            "dob",
            "blood_group",
            "gender",
            "physically_challenged",
            "extra_curricular",
            "present_address",
            "permanent_address",
            "contact_mobile",
            "contact_email",

            "created_at",
            "updated_at",
        ]

        read_only_fields = ["id", "unique_id", "created_at", "updated_at"]

    # --------------------------------------------------
    # Helpers
    # --------------------------------------------------
    def _pop_personal_data(self, validated_data):
        """
        Extract personal detail payload for StaffPersonalDetails
        """
        personal_data = validated_data.pop("personal_details", {})
        return {
            field: personal_data[field]
            for field in self.personal_field_names
            if field in personal_data
        }

    # --------------------------------------------------
    # Create
    # --------------------------------------------------
    def create(self, validated_data):
        personal_data = self._pop_personal_data(validated_data)

        staff = StaffOfficeDetails.objects.create(**validated_data)

        StaffPersonalDetails.objects.create(
            staff=staff,
            staff_unique_id=staff.staff_unique_id,
            **personal_data,
        )

        return staff

    # --------------------------------------------------
    # Update
    # --------------------------------------------------
    def update(self, instance, validated_data):
        personal_data = self._pop_personal_data(validated_data)

        staff = super().update(instance, validated_data)

        if personal_data:
            personal_instance, _ = StaffPersonalDetails.objects.get_or_create(
                staff=staff
            )
            for attr, value in personal_data.items():
                setattr(personal_instance, attr, value)

            personal_instance.staff_unique_id = staff.staff_unique_id
            personal_instance.save()
        else:
            if hasattr(staff, "personal_details"):
                staff.personal_details.staff_unique_id = staff.staff_unique_id
                staff.personal_details.save(update_fields=["staff_unique_id"])

        return staff
