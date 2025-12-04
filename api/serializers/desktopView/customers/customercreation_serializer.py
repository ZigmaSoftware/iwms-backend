from typing import Optional

from rest_framework import serializers

from api.apps.customercreation import CustomerCreation
from api.apps.country import Country
from api.apps.state import State
from api.apps.district import District
from api.apps.city import City
from api.apps.zone import Zone
from api.apps.ward import Ward
from api.apps.property import Property
from api.apps.subproperty import SubProperty
from api.validators.unique_name_validator import unique_name_validator


class CustomerCreationSerializer(serializers.ModelSerializer):

    # Rename FK inputs to *_id
    ward_id = serializers.PrimaryKeyRelatedField(
        source="ward",
        queryset=Ward.objects.all(),
        required=False,
        allow_null=True,
    )
    zone_id = serializers.PrimaryKeyRelatedField(
        source="zone",
        queryset=Zone.objects.all(),
        required=False,
        allow_null=True,
    )
    city_id = serializers.PrimaryKeyRelatedField(
        source="city",
        queryset=City.objects.all(),
        required=False,
        allow_null=True,
    )
    district_id = serializers.PrimaryKeyRelatedField(
        source="district",
        queryset=District.objects.all(),
        required=False,
        allow_null=True,
    )
    state_id = serializers.PrimaryKeyRelatedField(
        source="state",
        queryset=State.objects.all(),
    )
    country_id = serializers.PrimaryKeyRelatedField(
        source="country",
        queryset=Country.objects.all(),
    )
    property_id = serializers.PrimaryKeyRelatedField(
        source="property",
        queryset=Property.objects.all(),
    )
    sub_property_id = serializers.PrimaryKeyRelatedField(
        source="sub_property",
        queryset=SubProperty.objects.all(),
    )

    # Read-only mapped fields
    ward_name = serializers.SerializerMethodField()
    zone_name = serializers.SerializerMethodField()
    city_name = serializers.SerializerMethodField()
    district_name = serializers.SerializerMethodField()
    state_name = serializers.SerializerMethodField()
    country_name = serializers.SerializerMethodField()
    property_name = serializers.SerializerMethodField()
    sub_property_name = serializers.SerializerMethodField()

    class Meta:
        model = CustomerCreation
        fields = [
            "id",
            "unique_id",
            "customer_name",
            "contact_no",
            "building_no",
            "street",
            "area",
            "ward_id",
            "zone_id",
            "city_id",
            "district_id",
            "state_id",
            "country_id",
            "pincode",
            "latitude",
            "longitude",
            "id_proof_type",
            "id_no",
            "property_id",
            "sub_property_id",
            "is_deleted",
            "is_active",
            "ward_name",
            "zone_name",
            "city_name",
            "district_name",
            "state_name",
            "country_name",
            "property_name",
            "sub_property_name",
        ]
        read_only_fields = ["unique_id"]
        validators = []  # Disable DRF unique-together enforcement

    # =========================
    # VALIDATION LAYER
    # =========================
    def validate(self, attrs):
        # Run your existing name validator
        attrs = unique_name_validator(
            Model=CustomerCreation,
            name_field="customer_name",
        )(self, attrs)

        # Composite duplicate validation
        name = attrs.get("customer_name")
        mobile = attrs.get("contact_no")

        instance = getattr(self, "instance", None)

        # Query for existing duplicate
        qs = CustomerCreation.objects.filter(
            customer_name__iexact=name,
            contact_no=mobile,
            is_deleted=False
        )

        # Exclude self on update
        if instance:
            qs = qs.exclude(id=instance.id)

        if qs.exists():
            raise serializers.ValidationError({
                "detail": "Customer with the same name and mobile number already exists."
            })

        return attrs

    # =========================
    # RESOLVER HELPERS
    # =========================
    def _resolve_name(self, obj, attr: str) -> Optional[str]:
        related_obj = getattr(obj, attr, None)
        return getattr(related_obj, "name", None) if related_obj else None

    def _resolve_property_name(self, obj) -> Optional[str]:
        related_obj = getattr(obj, "property", None)
        return getattr(related_obj, "property_name", None) if related_obj else None

    def _resolve_sub_property_name(self, obj) -> Optional[str]:
        related_obj = getattr(obj, "sub_property", None)
        return getattr(related_obj, "sub_property_name", None) if related_obj else None

    # =========================
    # SerializerMethodField getters
    # =========================
    def get_ward_name(self, obj):
        return self._resolve_name(obj, "ward")

    def get_zone_name(self, obj):
        return self._resolve_name(obj, "zone")

    def get_city_name(self, obj):
        return self._resolve_name(obj, "city")

    def get_district_name(self, obj):
        return self._resolve_name(obj, "district")

    def get_state_name(self, obj):
        return self._resolve_name(obj, "state")

    def get_country_name(self, obj):
        return self._resolve_name(obj, "country")

    def get_property_name(self, obj):
        return self._resolve_property_name(obj)

    def get_sub_property_name(self, obj):
        return self._resolve_sub_property_name(obj)
