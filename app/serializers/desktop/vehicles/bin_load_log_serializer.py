from rest_framework import serializers
from app.serializers.utils.tenancy import TenancyReadSerializerMixin

from app.models.vehicles.bin_load_log import BinLoadLog
from app.models.masters.zone import Zone
from app.models.vehicles.vehicleCreation import VehicleCreation
from app.models.assets.property import Property
from app.models.assets.subproperty import SubProperty
from app.models.masters.bin import Bin


class BinLoadLogSerializer(TenancyReadSerializerMixin, serializers.ModelSerializer):

    # ------------------------------------------------------
    # WRITE-ONLY INPUT FIELDS (FK OBJECTS)
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

    bin = serializers.PrimaryKeyRelatedField(
        queryset=Bin.objects.all(),
        write_only=True,
        required=False,
        allow_null=True
    )

    # ------------------------------------------------------
    # READ-ONLY OUTPUT FIELDS (NESTED OBJECTS)
    # ------------------------------------------------------
    zone_details = serializers.SerializerMethodField(read_only=True)
    vehicle_details = serializers.SerializerMethodField(read_only=True)
    property_details = serializers.SerializerMethodField(read_only=True)
    sub_property_details = serializers.SerializerMethodField(read_only=True)
    bin_details = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = BinLoadLog
        fields = [
            "unique_id",
            "company_id",
            "company_name",
            "project_id",
            "project_name",

            # write-only
            "zone",
            "vehicle",
            "property",
            "sub_property",
            "bin",

            # read-only
            "zone_details",
            "vehicle_details",
            "property_details",
            "sub_property_details",
            "bin_details",

            "weight_kg",
            "source_type",
            "event_time",
            "processed",
            "created_at",
        ]

        read_only_fields = [
            "unique_id",
            "processed",
            "created_at",
        ]

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

    def get_bin_details(self, obj):
        bin_obj = obj.bin
        if not bin_obj:
            return None
        return {
            "unique_id": bin_obj.unique_id,
            "bin_code": getattr(bin_obj, "bin_code", None),
        }
