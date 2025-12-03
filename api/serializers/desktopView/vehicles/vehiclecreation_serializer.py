from rest_framework import serializers
from api.apps.vehicleCreation import VehicleCreation
from api.apps.vehicleTypeCreation import VehicleTypeCreation
from api.apps.fuel import Fuel
from api.apps.state import State
from api.apps.district import District
from api.apps.city import City
from api.apps.zone import Zone
from api.apps.ward import Ward


class UniqueIdOrPkField(serializers.SlugRelatedField):
    """
    Accepts related object via unique_id (preferred) or numeric PK; serializes as unique_id.
    """

    def to_representation(self, value):
        return getattr(value, self.slug_field, None) or super().to_representation(value)

    def to_internal_value(self, data):
        try:
            return super().to_internal_value(data)
        except Exception:
            try:
                return self.get_queryset().get(pk=data)
            except Exception:
                raise


class VehicleCreationSerializer(serializers.ModelSerializer):
    vehicle_type_id = UniqueIdOrPkField(
        source="vehicle_type",
        slug_field="unique_id",
        queryset=VehicleTypeCreation.objects.filter(is_delete=False),
        required=False,
        allow_null=True,
    )
    fuel_type_id = UniqueIdOrPkField(
        source="fuel_type",
        slug_field="unique_id",
        queryset=Fuel.objects.filter(is_deleted=False),
        required=False,
        allow_null=True,
    )
    state_id = serializers.PrimaryKeyRelatedField(
        source="state",
        queryset=State.objects.all(),
        required=False,
        allow_null=True,
    )
    district_id = serializers.PrimaryKeyRelatedField(
        source="district",
        queryset=District.objects.all(),
        required=False,
        allow_null=True,
    )
    city_id = serializers.PrimaryKeyRelatedField(
        source="city",
        queryset=City.objects.all(),
        required=False,
        allow_null=True,
    )
    zone_id = serializers.PrimaryKeyRelatedField(
        source="zone",
        queryset=Zone.objects.all(),
        required=False,
        allow_null=True,
    )
    ward_id = serializers.PrimaryKeyRelatedField(
        source="ward",
        queryset=Ward.objects.all(),
        required=False,
        allow_null=True,
    )

    vehicle_type_name = serializers.CharField(source="vehicle_type.vehicleType", read_only=True)
    fuel_type_name = serializers.CharField(source="fuel_type.fuel_type", read_only=True)
    zone_name = serializers.CharField(source="zone.name", read_only=True)
    ward_name = serializers.CharField(source="ward.name", read_only=True)
    state_name = serializers.CharField(source="state.name", read_only=True)
    district_name = serializers.CharField(source="district.name", read_only=True)
    city_name = serializers.CharField(source="city.name", read_only=True)

    class Meta:
        model = VehicleCreation
        fields = [
            "id",
            "unique_id",
            "vehicle_no",
            "chase_no",
            "imei_no",
            "driver_name",
            "driver_no",
            "vehicle_type_id",
            "fuel_type_id",
            "state_id",
            "district_id",
            "city_id",
            "zone_id",
            "ward_id",
            "vehicle_type_name",
            "fuel_type_name",
            "zone_name",
            "ward_name",
            "state_name",
            "district_name",
            "city_name",
            "is_active",
            "is_deleted",
            "created_at",
            "updated_at",
        ]
