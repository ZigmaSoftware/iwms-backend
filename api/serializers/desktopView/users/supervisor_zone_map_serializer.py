from rest_framework import serializers
from api.apps.supervisor_zone_map import SupervisorZoneMap
from api.apps.userCreation import User


class SupervisorZoneMapSerializer(serializers.ModelSerializer):
    supervisor_id = serializers.SlugRelatedField(
        slug_field="unique_id",
        queryset=User.objects.all(),
        source="supervisor"
    )

    class Meta:
        model = SupervisorZoneMap
        fields = [
            "id",
            "unique_id",
            "supervisor_id",
            "district_id",
            "city_id",
            "zone_ids",
            "status",
            "created_at",
        ]
        read_only_fields = ["id", "unique_id", "created_at"]

    # -----------------------------
    # VALIDATIONS
    # -----------------------------
    def validate_zone_ids(self, value):
        if not isinstance(value, list) or not value:
            raise serializers.ValidationError(
                "zone_ids must be a non-empty list of zone IDs"
            )

        if not all(isinstance(z, int) for z in value):
            raise serializers.ValidationError(
                "zone_ids must contain only integers"
            )

        return value

    def validate(self, attrs):
        supervisor = attrs.get("supervisor")
        status = attrs.get("status", "ACTIVE")

        # Prevent multiple ACTIVE assignments
        if status == "ACTIVE":
            qs = SupervisorZoneMap.objects.filter(
                supervisor=supervisor,
                status="ACTIVE"
            )
            if self.instance:
                qs = qs.exclude(id=self.instance.id)

            if qs.exists():
                raise serializers.ValidationError(
                    "An ACTIVE zone mapping already exists for this supervisor"
                )

        return attrs
