from rest_framework import serializers
from api.apps.supervisor_zone_map import SupervisorZoneMap
from api.apps.userCreation import User

from rest_framework import serializers

from api.apps.supervisor_zone_map import SupervisorZoneMap
from api.apps.userCreation import User
from api.apps.zone import Zone
from api.apps.ward import Ward


# ============================================================
# WARD SERIALIZER
# ============================================================
class WardSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ward
        fields = [
            "unique_id",
            "name",
            "area_type",
            "coordinates",
            "geofencing_type",
            "geofencing_color",
        ]


# ============================================================
# ZONE SERIALIZER (WITH WARDS)
# ============================================================
class ZoneWithWardsSerializer(serializers.ModelSerializer):
    wards = serializers.SerializerMethodField()

    class Meta:
        model = Zone
        fields = [
            "unique_id",
            "name",
            "city_id",
            "district_id",
            "area_type",
            "coordinates",
            "geofencing_type",
            "geofencing_color",
            "wards",
        ]

    def get_wards(self, obj):
        wards = obj.ward_set.filter(
            is_active=True,
            is_deleted=False
        )
        return WardSerializer(wards, many=True).data


# ============================================================
# SUPERVISOR → ZONE → WARD MAPPING SERIALIZER
# ============================================================
class SupervisorZoneMapSerializer(serializers.ModelSerializer):
    supervisor_id = serializers.SlugRelatedField(
        slug_field="unique_id",
        queryset=User.objects.all()
    )

    zones = serializers.SerializerMethodField()

    class Meta:
        model = SupervisorZoneMap
        fields = [
            "id",
            "unique_id",
            "supervisor_id",
            "district_id",
            "city_id",
            "zone_ids",
            "zones",          # mapped zones + wards
            "status",
            "created_at",
        ]
        read_only_fields = ["id", "unique_id", "created_at"]

    # ------------------------------------------------------------
    # ZONE + WARD MAPPING
    # ------------------------------------------------------------
    def get_zones(self, obj):
        zones = Zone.objects.filter(
            unique_id__in=obj.zone_ids,
            is_active=True,
            is_deleted=False
        ).prefetch_related(
            "ward_set"
        )

        return ZoneWithWardsSerializer(zones, many=True).data

    # ------------------------------------------------------------
    # VALIDATIONS
    # ------------------------------------------------------------
    def validate_zone_ids(self, value):
        if isinstance(value, str):
            value = [item.strip() for item in value.split(",") if item.strip()]
        elif isinstance(value, (list, tuple)):
            normalized = []
            for item in value:
                if item in ("", None):
                    continue
                if isinstance(item, str):
                    parts = [part.strip() for part in item.split(",") if part.strip()]
                    normalized.extend(parts)
                else:
                    normalized.append(str(item))
            value = normalized
        else:
            value = []

        if not value:
            raise serializers.ValidationError(
                "zone_ids must be a non-empty list of zone IDs"
            )

        if not all(isinstance(z, str) and z.strip() for z in value):
            raise serializers.ValidationError(
                "zone_ids must contain only zone unique_id strings"
            )

        return value

    def validate(self, attrs):
        instance = getattr(self, "instance", None)
        supervisor = (
            attrs.get("supervisor_id")
            if "supervisor_id" in attrs
            else getattr(instance, "supervisor_id", None)
        )
        status = attrs.get("status", getattr(instance, "status", "ACTIVE"))

        # Prevent multiple ACTIVE assignments
        if status == "ACTIVE" and supervisor:
            qs = SupervisorZoneMap.objects.filter(
                supervisor_id=supervisor,
                status="ACTIVE"
            )
            if self.instance:
                qs = qs.exclude(id=self.instance.id)

            if qs.exists():
                raise serializers.ValidationError(
                    "An ACTIVE zone mapping already exists for this supervisor"
                )

        return attrs
