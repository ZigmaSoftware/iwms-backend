from rest_framework import serializers
from api.apps.supervisor_zone_access_audit import SupervisorZoneAccessAudit
from api.apps.userCreation import User


class SupervisorZoneAccessAuditSerializer(serializers.ModelSerializer):
    supervisor_id = serializers.SlugRelatedField(
        source="supervisor",
        slug_field="unique_id",
        read_only=True
    )

    performed_by = serializers.SlugRelatedField(
        slug_field="unique_id",
        read_only=True
    )

    class Meta:
        model = SupervisorZoneAccessAudit
        fields = [
            "id",
            "supervisor_id",
            "old_zone_ids",
            "new_zone_ids",
            "performed_by",
            "performed_role",
            "remarks",
            "created_at",
        ]
        read_only_fields = fields
