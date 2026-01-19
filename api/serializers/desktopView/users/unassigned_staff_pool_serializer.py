from rest_framework import serializers
from api.apps.unassigned_staff_pool import UnassignedStaffPool
from api.apps.userCreation import User
from api.apps.zone import Zone
from api.apps.ward import Ward
from api.apps.trip_instance import TripInstance


class UnassignedStaffPoolSerializer(serializers.ModelSerializer):

    operator_id = serializers.SlugRelatedField(
        source="operator",
        slug_field="unique_id",
        queryset=User.objects.all(),
        required=False,
        allow_null=True
    )

    driver_id = serializers.SlugRelatedField(
        source="driver",
        slug_field="unique_id",
        queryset=User.objects.all(),
        required=False,
        allow_null=True
    )

    zone_id = serializers.SlugRelatedField(
        source="zone",
        slug_field="unique_id",
        queryset=Zone.objects.all()
    )

    ward_id = serializers.SlugRelatedField(
        source="ward",
        slug_field="unique_id",
        queryset=Ward.objects.all()
    )

    trip_instance_id = serializers.SlugRelatedField(
        source="trip_instance",
        slug_field="unique_id",
        queryset=TripInstance.objects.all(),
        required=False,
        allow_null=True
    )

    class Meta:
        model = UnassignedStaffPool
        fields = [
            "id",
            "operator_id",
            "driver_id",
            "zone_id",
            "ward_id",
            "status",
            "trip_instance_id",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def validate(self, attrs):
        instance = getattr(self, "instance", None)
        operator = attrs.get("operator") if "operator" in attrs else getattr(instance, "operator", None)
        driver = attrs.get("driver") if "driver" in attrs else getattr(instance, "driver", None)

        if not operator and not driver:
            raise serializers.ValidationError(
                "Either operator_id or driver_id is required"
            )

        if operator and driver:
            raise serializers.ValidationError(
                "Only one of operator_id or driver_id must be provided"
            )

        staff = operator or driver
        if staff:
            role_name = staff.staffusertype_id.name.lower() if staff.staffusertype_id else ""
            if operator and role_name != "operator":
                raise serializers.ValidationError(
                    {"operator_id": "Selected user is not an operator."}
                )
            if driver and role_name != "driver":
                raise serializers.ValidationError(
                    {"driver_id": "Selected user is not a driver."}
                )

            zone = attrs.get("zone") if "zone" in attrs else getattr(instance, "zone", None)
            ward = attrs.get("ward") if "ward" in attrs else getattr(instance, "ward", None)

            if staff.zone_id_id and zone and staff.zone_id_id != zone.unique_id:
                raise serializers.ValidationError(
                    {"zone_id": "Zone does not match staff's assigned zone."}
                )
            if staff.ward_id_id and ward and staff.ward_id_id != ward.unique_id:
                raise serializers.ValidationError(
                    {"ward_id": "Ward does not match staff's assigned ward."}
                )

        return attrs
