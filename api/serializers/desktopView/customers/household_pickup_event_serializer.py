from rest_framework import serializers
from api.apps.household_pickup_event import HouseholdPickupEvent
from api.apps.customercreation import CustomerCreation
from api.apps.zone import Zone
from api.apps.property import Property
from api.apps.subproperty import SubProperty
from api.apps.userCreation import User
from api.apps.vehicleCreation import VehicleCreation


class HouseholdPickupEventSerializer(serializers.ModelSerializer):

    customer_id = serializers.SlugRelatedField(
        source="customer",
        slug_field="unique_id",
        queryset=CustomerCreation.objects.all()
    )

    zone_id = serializers.SlugRelatedField(
        source="zone",
        slug_field="unique_id",
        queryset=Zone.objects.all()
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

    collector_staff_id = serializers.SlugRelatedField(
        source="collector_staff",
        slug_field="unique_id",
        queryset=User.objects.all()
    )

    vehicle_id = serializers.SlugRelatedField(
        source="vehicle",
        slug_field="unique_id",
        queryset=VehicleCreation.objects.all()
    )

    class Meta:
        model = HouseholdPickupEvent
        fields = [
            "id",
            "customer_id",
            "zone_id",
            "property_id",
            "sub_property_id",
            "pickup_time",
            "weight_kg",
            "photo_url",
            "collector_staff_id",
            "vehicle_id",
            "source",
            "created_at",
        ]

        read_only_fields = [
            "id",
            "created_at",
        ]

    def validate(self, attrs):
        source = attrs.get("source", getattr(self.instance, "source", None))
        weight = attrs.get("weight_kg", getattr(self.instance, "weight_kg", None))

        if source == HouseholdPickupEvent.Source.HOUSEHOLD_WASTE and weight is None:
            raise serializers.ValidationError(
                {"weight_kg": "Weight is mandatory for HOUSEHOLD_WASTE source"}
            )

        return attrs
