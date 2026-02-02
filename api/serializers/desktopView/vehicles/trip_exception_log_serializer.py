from rest_framework import serializers
from api.serializers.utils.tenancy import TenancyReadSerializerMixin
from api.apps.trip_exception_log import TripExceptionLog
from api.apps.trip_instance import TripInstance


class TripExceptionLogSerializer(TenancyReadSerializerMixin, serializers.ModelSerializer):

    trip_instance_id = serializers.SlugRelatedField(
        source="trip_instance",
        slug_field="unique_id",
        queryset=TripInstance.objects.all()
    )

    class Meta:
        model = TripExceptionLog
        fields = [
            "unique_id",
            "company_id",
            "company_name",
            "project_id",
            "project_name",
            "trip_instance_id",
            "exception_type",
            "remarks",
            "detected_by",
            "created_at",
        ]
        read_only_fields = ["unique_id", "created_at"]

    def validate(self, attrs):
        trip = attrs["trip_instance"]

        if trip.status in ["COMPLETED", "CANCELLED"]:
            raise serializers.ValidationError(
                "Exceptions cannot be logged for completed or cancelled trips"
            )

        return attrs
