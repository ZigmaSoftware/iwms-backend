from rest_framework import serializers
from api.apps.trip_instance import TripInstance
from api.apps.trip_definition import TripDefinition
from api.apps.stafftemplate import StaffTemplate
from api.apps.alternative_staff_template import AlternativeStaffTemplate
from api.apps.zone import Zone
from api.apps.vehicleCreation import VehicleCreation
from api.apps.property import Property
from api.apps.subproperty import SubProperty


class TripInstanceSerializer(serializers.ModelSerializer):

    trip_definition_id = serializers.SlugRelatedField(
        source="trip_definition",
        slug_field="unique_id",
        queryset=TripDefinition.objects.all()
    )

    staff_template_id = serializers.SlugRelatedField(
        source="staff_template",
        slug_field="unique_id",
        queryset=StaffTemplate.objects.all()
    )

    alternative_staff_template_id = serializers.SlugRelatedField(
        source="alternative_staff_template",
        slug_field="unique_id",
        queryset=AlternativeStaffTemplate.objects.all(),
        required=False,
        allow_null=True
    )

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
        model = TripInstance
        fields = "__all__"
        read_only_fields = [
            "id",
            "unique_id",
            "trip_no",
            "created_at",
        ]
