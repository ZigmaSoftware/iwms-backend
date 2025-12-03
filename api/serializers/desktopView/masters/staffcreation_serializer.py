from rest_framework import serializers

from api.apps.staffcreation import StaffOfficeDetails, StaffPersonalDetails


class StaffcreationSerializer(serializers.ModelSerializer):
    # Expose staff ID as `unique_id` for frontend parity
    unique_id = serializers.CharField(source="staff_unique_id", read_only=True)
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
    contact_details = serializers.JSONField(
        source="personal_details.contact_details",
        required=False,
        allow_null=True,
    )

    personal_field_names = [
        "marital_status",
        "dob",
        "blood_group",
        "gender",
        "physically_challenged",
        "extra_curricular",
        "present_address",
        "permanent_address",
        "contact_details",
    ]

    class Meta:
        model = StaffOfficeDetails
        fields = [
            "id",
            "unique_id",
            # "employee_id",
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
            "active_status",
            "salary_type",
            "marital_status",
            "dob",
            "blood_group",
            "gender",
            "physically_challenged",
            "extra_curricular",
            "present_address",
            "permanent_address",
            "contact_details",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "unique_id", "created_at", "updated_at"]

    def _pop_personal_data(self, validated_data):
        """
        Pull personal detail payload out of validated data so it can be saved
        against the StaffPersonalDetails model.
        """
        personal_data = validated_data.pop("personal_details", {})
        return {
            field: personal_data[field]
            for field in self.personal_field_names
            if field in personal_data
        }

    def create(self, validated_data):
        personal_data = self._pop_personal_data(validated_data)
        staff = StaffOfficeDetails.objects.create(**validated_data)
        StaffPersonalDetails.objects.create(
            staff=staff,
            staff_unique_id=staff.staff_unique_id,
            **personal_data,
        )
        return staff

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
            # Keep personal row in sync with current staff unique id if it already exists
            if hasattr(staff, "personal_details"):
                staff.personal_details.staff_unique_id = staff.staff_unique_id
                staff.personal_details.save(update_fields=["staff_unique_id"])

        return staff
