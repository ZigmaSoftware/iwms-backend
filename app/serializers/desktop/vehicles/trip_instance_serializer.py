from rest_framework import serializers
from app.serializers.utils.tenancy import TenancyReadSerializerMixin
from app.models.vehicles.trip_instance import TripInstance
from app.models.vehicles.trip_definition import TripDefinition
from app.models.users.stafftemplate import StaffTemplate
from app.models.users.alternative_staff_template import AlternativeStaffTemplate
from app.models.masters.zone import Zone
from app.models.vehicles.vehicleCreation import VehicleCreation
from app.models.assets.property import Property
from app.models.assets.subproperty import SubProperty


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
