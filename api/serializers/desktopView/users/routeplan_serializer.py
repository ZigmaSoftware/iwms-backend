
from rest_framework import serializers
from api.apps.routeplan import RoutePlan



class RoutePlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = RoutePlan
        fields = [
            "id",
            "unique_id",
            "district_id",
            "zone_id",
            "vehicle_id",
            "supervisor_id",
            "status",
            "created_at",
        ]
        read_only_fields = ("id", "unique_id", "created_at")
