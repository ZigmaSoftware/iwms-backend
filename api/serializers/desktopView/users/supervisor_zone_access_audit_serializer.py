from rest_framework import serializers
from api.serializers.utils.tenancy import TenancyReadSerializerMixin
from api.apps.supervisor_zone_access_audit import SupervisorZoneAccessAudit
from api.apps.staffcreation import StaffOfficeDetails


class SupervisorZoneAccessAuditSerializer(TenancyReadSerializerMixin, serializers.ModelSerializer):
    unique_id = serializers.CharField(read_only=True)
    supervisor_id = serializers.SlugRelatedField(
        source="supervisor",
        slug_field="staff_unique_id",
        read_only=True
    )

    performed_by = serializers.SlugRelatedField(
        slug_field="staff_unique_id",
        read_only=True
    )

    class Meta:
        model = SupervisorZoneAccessAudit
        fields = [
            "unique_id",
            "company_id",
            "company_name",
            "project_id",
            "project_name",
            "supervisor_id",
            "old_zone_ids",
            "new_zone_ids",
            "performed_by",
            "performed_role",
            "remarks",
            "created_at",
        ]
        read_only_fields = fields
