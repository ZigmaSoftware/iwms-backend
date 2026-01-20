from rest_framework import serializers
from api.apps.zone_property_load_tracker import ZonePropertyLoadTracker
from api.apps.zone import Zone
from api.apps.vehicleCreation import VehicleCreation
from api.apps.property import Property
from api.apps.subproperty import SubProperty


class ZonePropertyLoadTrackerSerializer(serializers.ModelSerializer):

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
        model = ZonePropertyLoadTracker
        fields = [
            "unique_id",
            "zone_id",
            "vehicle_id",
            "property_id",
            "sub_property_id",
            "current_weight_kg",
            "last_updated",
        ]
        read_only_fields = [
            "unique_id",
            "last_updated",
        ]
