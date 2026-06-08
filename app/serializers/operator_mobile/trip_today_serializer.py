from rest_framework import serializers

from app.models.schedule_masters.daily_trip_assignment import DailyTripAssignment
from app.models.schedule_masters.daily_trip_collection_point import (
    DailyTripCollectionPoint,
)


class _PanchayatBriefSerializer(serializers.Serializer):
    unique_id = serializers.CharField()
    name = serializers.CharField(source="panchayat_name")
    latitude = serializers.DecimalField(
        max_digits=9, decimal_places=6, allow_null=True
    )
    longitude = serializers.DecimalField(
        max_digits=9, decimal_places=6, allow_null=True
    )


class _WardBriefSerializer(serializers.Serializer):
    unique_id = serializers.CharField()
    name = serializers.CharField(source="ward_name")


class _WasteTypeBriefSerializer(serializers.Serializer):
    unique_id = serializers.CharField()
    name = serializers.CharField(source="waste_type_name")


class _VehicleBriefSerializer(serializers.Serializer):
    unique_id = serializers.CharField()
    vehicle_no = serializers.CharField()
    capacity = serializers.DecimalField(max_digits=10, decimal_places=2)


class _CollectionPointBriefSerializer(serializers.Serializer):
    unique_id = serializers.CharField()
    name = serializers.CharField(source="cp_name")
    latitude = serializers.DecimalField(
        max_digits=9, decimal_places=6, allow_null=True
    )
    longitude = serializers.DecimalField(
        max_digits=9, decimal_places=6, allow_null=True
    )


class _BinBriefSerializer(serializers.Serializer):
    """Bin payload the mobile app needs to render + scan from a card.

    - ``bin_qr``: the bin's unique_id (matches the QR payload `id`). The mobile
      app uses this as the "scanned" value when the operator taps a CP card.
    - ``bin_qr_image_url``: absolute URL to the printed QR PNG so the app can
      display the QR for manual scanning if needed.
    """

    unique_id = serializers.CharField()
    bin_name = serializers.CharField()
    bin_qr = serializers.SerializerMethodField()
    bin_qr_image_url = serializers.SerializerMethodField()
    bin_capacity = serializers.IntegerField()

    def get_bin_qr(self, obj):
        return obj.unique_id

    def get_bin_qr_image_url(self, obj):
        qr = getattr(obj, "bin_qr", None)
        try:
            url = qr.url if qr else None
        except (ValueError, AttributeError):
            url = None
        if not url:
            return None
        request = self.context.get("request")
        return request.build_absolute_uri(url) if request else url


class TripCollectionPointSerializer(serializers.Serializer):
    unique_id = serializers.CharField()
    sequence = serializers.IntegerField()
    is_collected = serializers.BooleanField()
    status = serializers.CharField()
    collected_at = serializers.DateTimeField(allow_null=True)
    collected_weight_kg = serializers.DecimalField(
        max_digits=10, decimal_places=2, allow_null=True
    )
    collection_point = _CollectionPointBriefSerializer(source="collection_point_id")
    bin = _BinBriefSerializer(source="bin_id")


class MyTripTodaySerializer(serializers.Serializer):
    assignment_unique_id = serializers.CharField(source="unique_id")
    trip_date = serializers.DateField()
    status = serializers.CharField()
    scheduled_time = serializers.TimeField()
    actual_start_time = serializers.TimeField(allow_null=True)
    actual_end_time = serializers.TimeField(allow_null=True)
    panchayat = serializers.SerializerMethodField()
    ward = serializers.SerializerMethodField()
    area = serializers.SerializerMethodField()
    waste_type = _WasteTypeBriefSerializer(source="waste_type_id")
    vehicle = _VehicleBriefSerializer(source="vehicle_id", allow_null=True)
    progress = serializers.SerializerMethodField()
    collection_points = serializers.SerializerMethodField()

    def get_panchayat(self, obj):
        p = obj.panchayat_id
        if not p:
            return None
        return _PanchayatBriefSerializer(p).data

    def get_ward(self, obj):
        w = obj.ward_id
        if not w:
            return None
        return _WardBriefSerializer(w).data

    def get_area(self, obj):
        if obj.panchayat_id:
            return {
                "kind": "panchayat",
                "unique_id": obj.panchayat_id.unique_id,
                "name": obj.panchayat_id.panchayat_name,
            }
        if obj.ward_id:
            return {
                "kind": "ward",
                "unique_id": obj.ward_id.unique_id,
                "name": obj.ward_id.ward_name,
            }
        return {"kind": None, "unique_id": None, "name": None}

    def get_progress(self, obj):
        children = list(
            obj.trip_collection_points.filter(is_deleted=False)
        )
        total = len(children)
        collected = sum(1 for c in children if c.is_collected)
        return {
            "collected": collected,
            "total": total,
            "completed": total > 0 and collected == total,
        }

    def get_collection_points(self, obj):
        children = (
            obj.trip_collection_points
            .filter(is_deleted=False)
            .select_related("collection_point_id", "bin_id", "bin_id__wastetype_id")
            .order_by("sequence")
        )
        # Pass `request` through to children so absolute URL building works.
        return TripCollectionPointSerializer(
            children, many=True, context=self.context
        ).data
