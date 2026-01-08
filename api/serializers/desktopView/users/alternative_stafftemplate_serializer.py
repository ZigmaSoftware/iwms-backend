from rest_framework import serializers
from api.apps.alternative_staff_template import AlternativeStaffTemplate



class AlternativeStaffTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = AlternativeStaffTemplate
        fields = [
            'id',
            'unique_id',
            'staff_template',
            'effective_date',
            'driver',
            'operator',
            'extra_operator',
            'change_reason',
            'change_remarks',
            'requested_by',
            'approved_by',
            'approval_status',
            'created_at',
        ]
        read_only_fields = [
            'id',
            'unique_id',
            'created_at',
        ]

    def validate(self, attrs):
        """
        Hard validation layer.
        Prevents obvious data-quality issues before hitting DB.
        """
        instance = getattr(self, "instance", None)
        request = self.context.get("request")

        def resolve(field_name):
            if field_name in attrs:
                return attrs.get(field_name)
            return getattr(instance, field_name) if instance else None

        def validate_role(user, expected_role, field_name):
            if not user:
                return

            if not user.staffusertype_id:
                raise serializers.ValidationError({
                    field_name: "User has no staff role assigned"
                })

            actual_role = user.staffusertype_id.name
            if actual_role.lower() != expected_role:
                raise serializers.ValidationError({
                    field_name: f"Only '{expected_role}' role allowed. Found '{actual_role}'."
                })

        requested_by = resolve("requested_by")
        if not requested_by and request and hasattr(request, "user"):
            requested_by = request.user

        approved_by = resolve("approved_by")

        if not requested_by:
            raise serializers.ValidationError(
                {"requested_by": "requested_by is required."}
            )
        if not approved_by:
            raise serializers.ValidationError(
                {"approved_by": "approved_by is required."}
            )

        validate_role(requested_by, "supervisor", "requested_by")
        validate_role(approved_by, "admin", "approved_by")

        if attrs.get('driver') == attrs.get('operator'):
            raise serializers.ValidationError(
                "Driver and Operator cannot be the same user."
            )

        return attrs
