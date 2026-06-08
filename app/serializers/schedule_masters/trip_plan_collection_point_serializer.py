from rest_framework import serializers

from app.models.assets.bins import Bins
from app.models.schedule_masters.collection_point import Collection_point
from app.models.schedule_masters.trip_plan import TripPlan
from app.models.schedule_masters.trip_plan_collection_point import (
    TripPlanCollectionPoint,
)
from app.serializers.company_projects.tenancy import TenancyReadSerializerMixin
from app.serializers.user_creations.user_serializer import UniqueIdOrPkField


class TripPlanCollectionPointSerializer(
    TenancyReadSerializerMixin,
    serializers.ModelSerializer,
):
    trip_plan_id = UniqueIdOrPkField(
        slug_field="unique_id",
        queryset=TripPlan.objects.filter(is_deleted=False),
    )
    collection_point_id = UniqueIdOrPkField(
        slug_field="unique_id",
        queryset=Collection_point.objects.filter(is_deleted=False),
    )
    bin_id = UniqueIdOrPkField(
        slug_field="unique_id",
        queryset=Bins.objects.filter(is_deleted=False),
    )

    collection_point = serializers.SerializerMethodField()
    bin = serializers.SerializerMethodField()

    class Meta:
        model = TripPlanCollectionPoint
        fields = [
            "unique_id",
            "company_id",
            "company_name",
            "project_id",
            "project_name",
            "trip_plan_id",
            "collection_point_id",
            "collection_point",
            "bin_id",
            "bin",
            "sequence",
            "is_active",
            "is_deleted",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "unique_id",
            "company_id",
            "company_name",
            "project_id",
            "project_name",
            "created_at",
            "updated_at",
        ]
        validators = []

    def get_collection_point(self, obj):
        cp = obj.collection_point_id
        if not cp:
            return None
        return {
            "unique_id": cp.unique_id,
            "cp_name": cp.cp_name,
            "latitude": cp.latitude,
            "longitude": cp.longitude,
            "panchayat_id": getattr(cp.panchayat_id, "unique_id", None),
            "ward_id": getattr(cp.ward_id, "unique_id", None),
        }

    def get_bin(self, obj):
        bin_obj = obj.bin_id
        if not bin_obj:
            return None
        return {
            "unique_id": bin_obj.unique_id,
            "bin_name": bin_obj.bin_name,
            "bin_capacity": bin_obj.bin_capacity,
            "bin_type": bin_obj.bin_type,
        }

    def validate(self, attrs):
        instance = getattr(self, "instance", None)
        collection_point = attrs.get(
            "collection_point_id",
            getattr(instance, "collection_point_id", None),
        )
        bin_obj = attrs.get("bin_id", getattr(instance, "bin_id", None))

        if bin_obj and collection_point and bin_obj.collection_point_id != collection_point:
            raise serializers.ValidationError(
                {"bin_id": "Selected bin does not belong to the collection point."}
            )
        return attrs
