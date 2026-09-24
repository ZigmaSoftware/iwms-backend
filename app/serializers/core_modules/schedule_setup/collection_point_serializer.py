from rest_framework import serializers
from app.serializers.company_projects.tenancy import TenancyReadSerializerMixin
from app.models.core_modules.schedule_setup.collection_point import Collection_point
from app.models.masters.city import City
from app.models.masters.district import District
from app.models.masters.panchayat import Panchayat
from app.models.masters.zone import Zone
from app.models.superadmin.common_masters.state import State
from app.models.masters.ward import Ward
from app.validators.unique_name_validator import unique_name_validator


class WardMinimalSerializer(serializers.ModelSerializer):
    zone_name = serializers.SerializerMethodField()
    panchayat_name = serializers.SerializerMethodField()

    def get_zone_name(self, obj):
        zone = Zone.objects.filter(unique_id=obj.zone_id).first()
        return zone.zone_name if zone else None

    def get_panchayat_name(self, obj):
        panchayat = Panchayat.objects.filter(unique_id=obj.panchayat_id).first()
        return panchayat.panchayat_name if panchayat else None

    class Meta:
        model = Ward
        fields = ["unique_id", "ward_name", "zone_id", "zone_name", "panchayat_id", "panchayat_name"]


class CollectionPointSerializer(TenancyReadSerializerMixin, serializers.ModelSerializer):

    created_by = serializers.CharField(source="created_by_id", read_only=True)
    updated_by = serializers.CharField(source="updated_by_id", read_only=True)

    state_name = serializers.SerializerMethodField()
    city_name = serializers.SerializerMethodField()
    district_name = serializers.SerializerMethodField()
    panchayat_name = serializers.SerializerMethodField()

    # Collection points only support bin + bulk. Household collection is
    # valid only at the household-stop level, so it is rejected here.
    collection_type = serializers.ChoiceField(
        choices=Collection_point.COLLECTION_TYPE_CP_CHOICES,
        default=Collection_point.COLLECTION_TYPE_BIN,
    )

    # wards M2M — write accepts list of ward unique_ids; read returns minimal ward objects
    ward_ids = serializers.ListField(
        child=serializers.CharField(),
        write_only=True,
        required=False,
    )
    wards = WardMinimalSerializer(many=True, read_only=True)

    # zone_id is now a direct FK on the model; expose name as read-only
    zone_name = serializers.SerializerMethodField()

    # Convenience flat fields derived from wards (backwards compat)
    ward_id = serializers.SerializerMethodField()
    ward_name = serializers.SerializerMethodField()

    def get_ward_id(self, obj):
        w = obj.wards.first()
        return w.unique_id if w else None

    def get_ward_name(self, obj):
        w = obj.wards.first()
        return w.ward_name if w else None

    def get_state_name(self, obj):
        state = State.objects.filter(unique_id=obj.state_id).first()
        return state.name if state else None

    def get_city_name(self, obj):
        city = City.objects.filter(unique_id=obj.city_id).first()
        return city.name if city else None

    def get_district_name(self, obj):
        district = District.objects.filter(unique_id=obj.district_id).first()
        return district.name if district else None

    def get_panchayat_name(self, obj):
        panchayat = Panchayat.objects.filter(unique_id=obj.panchayat_id).first()
        return panchayat.panchayat_name if panchayat else None

    def get_zone_name(self, obj):
        zone = Zone.objects.filter(unique_id=obj.zone_id).first()
        return zone.zone_name if zone else None

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
            "collection_type",
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

        raw_zone = attrs.get("zone_id", _MISSING)
        zone = (
            getattr(self.instance, "zone_id", None)
            if raw_zone is _MISSING
            else raw_zone
        )

        if "ward_ids" in attrs:
            ward_ids = attrs["ward_ids"]
            has_wards = bool(ward_ids)
        else:
            ward_ids = []
            has_wards = bool(self.instance and self.instance.get_ward_ids())

        # ── Rule: CP must belong to at least a panchayat, zone, or ward ───────
        if not panchayat and not zone and not has_wards:
            raise serializers.ValidationError(
                "Collection Point must belong to a Panchayat, Zone, or Ward."
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
            zone_parents = set(str(w.zone_id) for w in wards_qs if w.zone_id)
            pan_parents = set(str(w.panchayat_id) for w in wards_qs if w.panchayat_id)

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

            # Auto-set zone_id from wards (zone-type wards) or clear it (panchayat-type wards)
            if zone_parents:
                from app.models.masters.zone import Zone as ZoneModel
                zone_unique_id = next(iter(zone_parents))
                try:
                    attrs["zone_id"] = ZoneModel.objects.get(unique_id=zone_unique_id).unique_id
                except ZoneModel.DoesNotExist:
                    pass
            elif pan_parents:
                attrs["zone_id"] = None

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
            valid_ids = list(
                Ward.objects.filter(unique_id__in=ward_ids).values_list("unique_id", flat=True)
            )
            instance.ward_ids = ",".join(valid_ids)
            instance.save(update_fields=["ward_ids"])
        return instance

    def update(self, instance, validated_data):
        ward_ids = validated_data.pop("ward_ids", None)
        instance = super().update(instance, validated_data)
        if ward_ids is not None:
            valid_ids = list(
                Ward.objects.filter(unique_id__in=ward_ids).values_list("unique_id", flat=True)
            )
            instance.ward_ids = ",".join(valid_ids)
            instance.save(update_fields=["ward_ids"])
        return instance
