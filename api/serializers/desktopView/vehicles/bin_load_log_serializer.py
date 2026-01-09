from rest_framework import serializers
from api.apps.bin_load_log import BinLoadLog
from api.apps.zone import Zone
from api.apps.vehicleCreation import VehicleCreation
from api.apps.property import Property
from api.apps.subproperty import SubProperty


class BinLoadLogSerializer(serializers.ModelSerializer):

    zone_id = serializers.SlugRelatedField(
        source="zone",
        slug_field="unique_id",
        queryset=Zone.objects.all()
    )

    vehicle_id = serializers.SlugRelatedField(
        source="vehicle",
        slug_field="unique_id",
        queryset=VehicleCreation.objects.all()
    )

    property_id = serializers.SlugRelatedField(
        source="property",
        slug_field="unique_id",
        queryset=Property.objects.all()
    )

    sub_property_id = serializers.SlugRelatedField(
        source="sub_property",
        slug_field="unique_id",
        queryset=SubProperty.objects.all()
    )

    class Meta:
        model = BinLoadLog
        fields = [
            "id",
            "zone_id",
            "vehicle_id",
            "property_id",
            "sub_property_id",
            "weight_kg",
            "source_type",
            "event_time",
            "processed",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "processed",
            "created_at",
        ]
