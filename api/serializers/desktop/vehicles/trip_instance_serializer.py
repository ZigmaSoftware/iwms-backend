from rest_framework import serializers
from api.serializers.utils.tenancy import TenancyReadSerializerMixin
from api.models.vehicles.trip_instance import TripInstance
from api.models.vehicles.trip_definition import TripDefinition
from api.models.users.stafftemplate import StaffTemplate
from api.models.users.alternative_staff_template import AlternativeStaffTemplate
from api.models.masters.zone import Zone
from api.models.vehicles.vehicleCreation import VehicleCreation
from api.models.assets.property import Property
from api.models.assets.subproperty import SubProperty


class TripInstanceSerializer(TenancyReadSerializerMixin, serializers.ModelSerializer):

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
