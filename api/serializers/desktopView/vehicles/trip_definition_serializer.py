from rest_framework import serializers

from api.apps.trip_definition import TripDefinition
from api.apps.routeplan import RoutePlan
from api.apps.stafftemplate import StaffTemplate
from api.apps.property import Property
from api.apps.subproperty import SubProperty


class TripDefinitionSerializer(serializers.ModelSerializer):

    routeplan_id = serializers.SlugRelatedField(
        source="routeplan",
        slug_field="unique_id",
        queryset=RoutePlan.objects.all()
    )

    staff_template_id = serializers.SlugRelatedField(
        source="staff_template",
        slug_field="unique_id",
        queryset=StaffTemplate.objects.all()
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
        model = TripDefinition
        fields = [
            "unique_id",
            "routeplan_id",
            "staff_template_id",
            "property_id",
            "sub_property_id",
            "trip_trigger_weight_kg",
            "max_vehicle_capacity_kg",
            "approval_status",
            "status",
            "created_at",
        ]

        read_only_fields = [
            "unique_id",
            "approval_status",
            "created_at",
        ]

    def validate(self, attrs):
        instance = getattr(self, "instance", None)
        trigger = (
            attrs.get("trip_trigger_weight_kg")
            if "trip_trigger_weight_kg" in attrs
            else getattr(instance, "trip_trigger_weight_kg", None)
        )
        capacity = (
            attrs.get("max_vehicle_capacity_kg")
            if "max_vehicle_capacity_kg" in attrs
            else getattr(instance, "max_vehicle_capacity_kg", None)
        )

        if trigger is not None and capacity is not None and trigger >= capacity:
            raise serializers.ValidationError(
                "Trigger weight must be less than vehicle capacity"
            )

        return attrs
