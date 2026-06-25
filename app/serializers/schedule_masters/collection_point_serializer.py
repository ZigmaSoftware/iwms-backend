from rest_framework import serializers
from app.serializers.company_projects.tenancy import TenancyReadSerializerMixin
from app.models.schedule_masters.collection_point import Collection_point
from app.models.masters.ward import Ward
from app.validators.unique_name_validator import unique_name_validator


class WardMinimalSerializer(serializers.ModelSerializer):
    zone_id = serializers.CharField(source="zone_id.unique_id", read_only=True, default=None)
    zone_name = serializers.CharField(source="zone_id.zone_name", read_only=True, default=None)
    panchayat_name = serializers.CharField(source="panchayat_id.panchayat_name", read_only=True, default=None)

    class Meta:
        model = Ward
        fields = ["unique_id", "ward_name", "zone_id", "zone_name", "panchayat_id", "panchayat_name"]


class CollectionPointSerializer(TenancyReadSerializerMixin, serializers.ModelSerializer):

    state_name = serializers.CharField(source="state_id.name", read_only=True)
    city_name = serializers.CharField(source="city_id.name", read_only=True)
    district_name = serializers.CharField(source="district_id.name", read_only=True)
    panchayat_name = serializers.CharField(source="panchayat_id.panchayat_name", read_only=True)

    # wards M2M — write accepts list of ward unique_ids; read returns minimal ward objects
    ward_ids = serializers.ListField(
        child=serializers.CharField(),
        write_only=True,
        required=False,
    )
    wards = WardMinimalSerializer(many=True, read_only=True)

    # Convenience flat fields derived from wards (first ward's zone, for backwards compat)
    zone_id = serializers.SerializerMethodField()
    zone_name = serializers.SerializerMethodField()
    ward_id = serializers.SerializerMethodField()
    ward_name = serializers.SerializerMethodField()

    def get_zone_id(self, obj):
        w = obj.wards.select_related("zone_id").first()
        return w.zone_id.unique_id if w and w.zone_id else None

    def get_zone_name(self, obj):
        w = obj.wards.select_related("zone_id").first()
        return w.zone_id.zone_name if w and w.zone_id else None

    def get_ward_id(self, obj):
        w = obj.wards.first()
        return w.unique_id if w else None

    def get_ward_name(self, obj):
        w = obj.wards.first()
        return w.ward_name if w else None

    class Meta:
        model = Collection_point
        fields = [
            "unique_id",
            "company_id",
            "company_name",
            "project_id",
            "project_name",
            "state_id",
            "state_name",
            "city_id",
            "city_name",
            "district_id",
            "district_name",
            "panchayat_id",
            "panchayat_name",
            "zone_id",
            "zone_name",
            "ward_id",
            "ward_name",
            "ward_ids",
            "wards",
            "cp_name",
            "latitude",
            "longitude",
            "is_active",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
            "is_deleted",
        ]
        read_only_fields = [
            "unique_id",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        # ── Resolve effective values (payload overrides instance) ──────────────
        _MISSING = object()

        raw_panchayat = attrs.get("panchayat_id", _MISSING)
        panchayat = (
            getattr(self.instance, "panchayat_id", None)
            if raw_panchayat is _MISSING
            else raw_panchayat
        )

        if "ward_ids" in attrs:
            ward_ids = attrs["ward_ids"]
            has_wards = bool(ward_ids)
        else:
            ward_ids = []
            has_wards = bool(self.instance and self.instance.wards.exists())

        # ── Rule: CP must belong to at least a panchayat OR one ward ──────────
        if not panchayat and not has_wards:
            raise serializers.ValidationError(
                "Collection Point must belong to Ward or Panchayat."
            )

        # ── Validate ward IDs exist and share the same parent ─────────────────
        if ward_ids:
            existing = set(
                Ward.objects.filter(unique_id__in=ward_ids)
                .values_list("unique_id", flat=True)
            )
            missing = [wid for wid in ward_ids if wid not in existing]
            if missing:
                raise serializers.ValidationError(
                    {"ward_ids": f"Wards not found: {', '.join(missing)}"}
                )

            wards_qs = list(Ward.objects.filter(unique_id__in=ward_ids))
            zone_parents = set(str(w.zone_id_id) for w in wards_qs if w.zone_id_id)
            pan_parents = set(str(w.panchayat_id_id) for w in wards_qs if w.panchayat_id_id)

            if len(zone_parents) > 1:
                raise serializers.ValidationError(
                    {"ward_ids": "All wards must belong to the same zone."}
                )
            if len(pan_parents) > 1:
                raise serializers.ValidationError(
                    {"ward_ids": "All wards must belong to the same panchayat."}
                )

            # Wards cannot mix zone-type and panchayat-type
            if zone_parents and pan_parents:
                raise serializers.ValidationError(
                    {"ward_ids": "Wards must all belong to a zone or all to a panchayat, not both."}
                )

            # When wards are zone-type, CP must not have a panchayat_id
            if zone_parents and panchayat:
                raise serializers.ValidationError(
                    "Zone-based wards cannot be combined with a Panchayat on the same Collection Point."
                )

        if not self.instance or "cp_name" in attrs:
            unique_name_validator(
                Model=Collection_point,
                name_field="cp_name",
                scope_fields=[
                    "state_id",
                    "company_id",
                    "project_id",
                    "panchayat_id",
                ]
            )(self, attrs)

        return attrs

    def create(self, validated_data):
        ward_ids = validated_data.pop("ward_ids", [])
        instance = super().create(validated_data)
        if ward_ids:
            instance.wards.set(Ward.objects.filter(unique_id__in=ward_ids))
        return instance

    def update(self, instance, validated_data):
        ward_ids = validated_data.pop("ward_ids", None)
        instance = super().update(instance, validated_data)
        if ward_ids is not None:
            instance.wards.set(Ward.objects.filter(unique_id__in=ward_ids))
        return instance
