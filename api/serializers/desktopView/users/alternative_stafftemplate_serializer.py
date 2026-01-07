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
        if attrs.get('driver') == attrs.get('operator'):
            raise serializers.ValidationError(
                "Driver and Operator cannot be the same user."
            )

        return attrs
