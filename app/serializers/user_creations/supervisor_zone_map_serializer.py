from rest_framework import serializers

from app.models.user_creations.supervisor_zone_map import SupervisorZoneMap
from app.models.user_creations.staffcreation import Staffcreation
from app.models.masters.district import District
from app.models.masters.city import City


class SupervisorZoneMapSerializer(serializers.ModelSerializer):
    """Read/write serializer for a supervisor's authorized zone scope."""

    supervisor_id = serializers.SlugRelatedField(
        slug_field="staff_unique_id",
        queryset=Staffcreation.objects.all(),
    )
    supervisor_name = serializers.SerializerMethodField()

    district_id = serializers.SlugRelatedField(
        slug_field="unique_id",
        queryset=District.objects.all(),
        required=False,
        allow_null=True,
    )

    city_id = serializers.SlugRelatedField(
        slug_field="unique_id",
        queryset=City.objects.all(),
        required=False,
        allow_null=True,
    )

    class Meta:
        model = SupervisorZoneMap
        fields = [
            "unique_id",
            "company_id",
            "project_id",
            "supervisor_id",
            "supervisor_name",
            "district_id",
            "city_id",
            "zone_ids",
            "status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["unique_id", "created_at", "updated_at"]

    def get_supervisor_name(self, obj):
        supervisor = getattr(obj, "supervisor_id", None)
        if not supervisor:
            return None
        for attr in ("employee_name", "name", "full_name"):
            value = getattr(supervisor, attr, None)
            if value:
                return value
        return str(supervisor)
