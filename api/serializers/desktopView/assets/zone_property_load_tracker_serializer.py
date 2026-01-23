from rest_framework import serializers

from api.apps.zone_property_load_tracker import ZonePropertyLoadTracker
from api.apps.zone import Zone
from api.apps.vehicleCreation import VehicleCreation
from api.apps.property import Property
from api.apps.subproperty import SubProperty


class ZonePropertyLoadTrackerSerializer(serializers.ModelSerializer):

    # ------------------------------------------------------
    # WRITE-ONLY INPUT (FK OBJECTS)
    # ------------------------------------------------------
    zone = serializers.PrimaryKeyRelatedField(
        queryset=Zone.objects.all(),
        write_only=True
    )

    vehicle = serializers.PrimaryKeyRelatedField(
        queryset=VehicleCreation.objects.all(),
        write_only=True
    )

    property = serializers.PrimaryKeyRelatedField(
        queryset=Property.objects.all(),
        write_only=True
    )

    sub_property = serializers.PrimaryKeyRelatedField(
        queryset=SubProperty.objects.all(),
        write_only=True
    )

    # ------------------------------------------------------
    # READ-ONLY OUTPUT (NESTED OBJECTS)
    # ------------------------------------------------------
    zone_details = serializers.SerializerMethodField(read_only=True)
    vehicle_details = serializers.SerializerMethodField(read_only=True)
    property_details = serializers.SerializerMethodField(read_only=True)
    sub_property_details = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = ZonePropertyLoadTracker
        fields = (
            "unique_id",

            # write-only
            "zone",
            "vehicle",
            "property",
            "sub_property",

            # read-only
            "zone_details",
            "vehicle_details",
            "property_details",
            "sub_property_details",

            "current_weight_kg",
            "last_updated",
        )

        read_only_fields = (
            "unique_id",
            "last_updated",
        )

    # ------------------------------------------------------
    # METHOD FIELDS
    # ------------------------------------------------------
    def get_zone_details(self, obj):
        zone = obj.zone
        return {
            "unique_id": zone.unique_id,
            "name": zone.name,
        }

    def get_vehicle_details(self, obj):
        vehicle = obj.vehicle
        return {
            "unique_id": vehicle.unique_id,
            "vehicle_no": vehicle.vehicle_no,
        }

    def get_property_details(self, obj):
        prop = obj.property
        return {
            "unique_id": prop.unique_id,
            "property_name": prop.property_name,
        }

    def get_sub_property_details(self, obj):
        sub = obj.sub_property
        return {
            "unique_id": sub.unique_id,
            "sub_property_name": sub.sub_property_name,
        }

    # ------------------------------------------------------
    # VALIDATION
    # ------------------------------------------------------
    def validate(self, attrs):
        property_obj = attrs.get("property")
        sub_property_obj = attrs.get("sub_property")

        if (
            property_obj
            and sub_property_obj
            and sub_property_obj.property_id != property_obj
        ):
            raise serializers.ValidationError(
                "Sub-property does not belong to the selected property."
            )

        return attrs
