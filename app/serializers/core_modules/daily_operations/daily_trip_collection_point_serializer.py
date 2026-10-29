from rest_framework import serializers

from app.models.masters.waste_masters.bins import Bins
from app.models.core_modules.schedule_setup.collection_point import Collection_point
from app.models.core_modules.daily_operations.daily_trip_assignment import DailyTripAssignment
from app.models.core_modules.daily_operations.daily_trip_collection_point import (
    DailyTripCollectionPoint,
)
from app.models.masters.panchayat import Panchayat
from app.models.masters.ward import Ward
from app.models.masters.zone import Zone
from app.models.superadmin.staff_management.staffcreation import (
    Staffcreation,
    StaffcreationOfficeDetails,
)
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project
from app.models.waste_collection_bluetooth.waste_collection_bluetooth import WasteType
from app.serializers.company_projects.tenancy import TenancyReadSerializerMixin
from app.serializers.superadmin.staff_management.user_serializer import UniqueIdOrPkField
from app.utils.related_prefetch import prefetch_related_rows, related

STOP_LOOKUPS = {
    "company": (Company, "company_id"),
    "project": (Project, "project_id"),
    "trip_assignment": (DailyTripAssignment, "trip_assignment_id"),
    "collection_point": (Collection_point, "collection_point_id"),
    "bin": (Bins, "bin_id"),
    "collected_by_user": (StaffcreationOfficeDetails, "collected_by", "staff_unique_id"),
}
CP_LOOKUPS = {"panchayat": (Panchayat, "panchayat_id")}
BIN_LOOKUPS = {"wastetype": (WasteType, "wastetype_id")}
WARD_LOOKUPS = {"zone": (Zone, "zone_id")}


def prefetch_stop_rows(stops):
    """Load everything DailyTripCollectionPointSerializer reads for `stops`
    in one query per table. Stops already prefetched are skipped, so callers
    can batch a whole response up front and still serialize per group."""
    stops = [
        stop for stop in stops
        if stop is not None and not getattr(stop, "_stop_prefetched", False)
    ]
    if not stops:
        return
    rows = prefetch_related_rows(stops, STOP_LOOKUPS)
    prefetch_related_rows(list(rows["bin"].values()), BIN_LOOKUPS)
    cps = [cp for cp in rows["collection_point"].values() if not hasattr(cp, "_first_ward")]
    prefetch_related_rows(cps, CP_LOOKUPS)

    # `cp.wards.first()`: Ward has no Meta ordering, so first() orders by pk.
    ward_ids = {wid for cp in cps for wid in cp.get_ward_ids()}
    wards = (
        list(Ward.objects.filter(unique_id__in=ward_ids).order_by("pk"))
        if ward_ids else []
    )
    prefetch_related_rows(wards, WARD_LOOKUPS)
    for cp in cps:
        own = set(cp.get_ward_ids())
        cp._first_ward = next((ward for ward in wards if ward.unique_id in own), None)
    for stop in stops:
        stop._stop_prefetched = True


class DailyTripCollectionPointListSerializer(serializers.ListSerializer):
    def to_representation(self, data):
        instances = list(data.all() if hasattr(data, "all") else data)
        prefetch_stop_rows(instances)
        return super().to_representation(instances)


class DailyTripCollectionPointSerializer(
    TenancyReadSerializerMixin,
    serializers.ModelSerializer,
):
    created_by = serializers.CharField(source="created_by_id", read_only=True)
    updated_by = serializers.CharField(source="updated_by_id", read_only=True)

    trip_assignment_id = UniqueIdOrPkField(
        slug_field="unique_id",
        queryset=DailyTripAssignment.objects.filter(is_deleted=False),
    )
    collection_point_id = UniqueIdOrPkField(
        slug_field="unique_id",
        queryset=Collection_point.objects.filter(is_deleted=False),
    )
    bin_id = UniqueIdOrPkField(
        slug_field="unique_id",
        queryset=Bins.objects.filter(is_deleted=False),
    )
    collected_by = UniqueIdOrPkField(
        slug_field="staff_unique_id",
        queryset=Staffcreation.objects.filter(is_deleted=False),
        required=False,
        allow_null=True,
    )

    trip_assignment = serializers.SerializerMethodField()
    collection_point = serializers.SerializerMethodField()
    bin = serializers.SerializerMethodField()
    collected_by_staff = serializers.SerializerMethodField()

    class Meta:
        model = DailyTripCollectionPoint
        fields = [
            "unique_id",
            "company_id",
            "company_name",
            "project_id",
            "project_name",
            "trip_assignment_id",
            "trip_assignment",
            "collection_point_id",
            "collection_point",
            "zone_id",
            "ward_id",
            "panchayat_id",
            "bin_id",
            "bin",
            "sequence",
            "is_collected",
            "collected_at",
            "collected_weight_kg",
            "collected_by",
            "collected_by_staff",
            "status",
            "status_reason",
            "status_latitude",
            "status_longitude",
            "created_by",
            "updated_by",
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
            "zone_id",
            "ward_id",
            "panchayat_id",
            "created_at",
            "updated_at",
        ]
        validators = []
        list_serializer_class = DailyTripCollectionPointListSerializer

    def get_company_name(self, obj):
        return getattr(related(obj, "company"), "name", None)

    def get_project_name(self, obj):
        return getattr(related(obj, "project"), "name", None)

    def get_trip_assignment(self, obj):
        assignment = related(obj, "trip_assignment")
        if not assignment:
            return None
        trip_plan = getattr(assignment, "trip_plan_id", None)
        return {
            "unique_id": assignment.unique_id,
            "trip_date": assignment.trip_date,
            "scheduled_time": assignment.scheduled_time,
            "status": assignment.status,
            "approval_status": assignment.approval_status,
            "trip_plan_id": getattr(trip_plan, "unique_id", None),
            "trip_plan_display_code": getattr(trip_plan, "display_code", None),
        }

    def get_collection_point(self, obj):
        cp = related(obj, "collection_point")
        if not cp:
            return None
        if hasattr(cp, "_first_ward"):
            first_ward = cp._first_ward
        else:
            first_ward = cp.wards.first()
        zone = related(first_ward, "zone") if first_ward else None
        panchayat = related(cp, "panchayat")
        return {
            "unique_id": cp.unique_id,
            "cp_name": cp.cp_name,
            "latitude": cp.latitude,
            "longitude": cp.longitude,
            "panchayat_id": getattr(panchayat, "unique_id", None),
            "panchayat_name": getattr(panchayat, "panchayat_name", None),
            "ward_id": getattr(first_ward, "unique_id", None),
            "ward_name": getattr(first_ward, "ward_name", None),
            "zone_id": getattr(zone, "unique_id", None),
            "zone_name": getattr(zone, "zone_name", None),
        }

    def get_bin(self, obj):
        bin_obj = related(obj, "bin")
        if not bin_obj:
            return None
        waste_type = related(bin_obj, "wastetype")
        return {
            "unique_id": bin_obj.unique_id,
            "bin_name": bin_obj.bin_name,
            "bin_capacity": bin_obj.bin_capacity,
            "bin_type": bin_obj.bin_type,
            "bin_qr": bin_obj.bin_qr.url if bin_obj.bin_qr else None,
            "waste_type": None if not waste_type else {
                "unique_id": waste_type.unique_id,
                "waste_type_name": waste_type.waste_type_name,
            },
        }

    def get_collected_by_staff(self, obj):
        staff = related(obj, "collected_by_user")
        if not staff:
            return None
        return {
            "unique_id": staff.staff_unique_id,
            "employee_name": staff.employee_name,
        }

    def validate(self, attrs):
        instance = getattr(self, "instance", None)
        assignment = attrs.get(
            "trip_assignment_id",
            getattr(instance, "trip_assignment_id", None),
        )
        collection_point = attrs.get(
            "collection_point_id",
            getattr(instance, "collection_point_id", None),
        )
        bin_obj = attrs.get("bin_id", getattr(instance, "bin_id", None))

        # assignment/bin_obj above are plain unique_id strings (this model's
        # string-pseudo-FK convention, same as trip_assignment_id/bin_id on
        # the model itself) — resolve the actual rows before touching
        # anything but their id.
        assignment_obj = (
            DailyTripAssignment.objects.filter(unique_id=assignment).first()
            if assignment else None
        )
        bin_row = Bins.objects.filter(unique_id=bin_obj).first() if bin_obj else None

        if assignment_obj and assignment_obj.status == DailyTripAssignment.STATUS_CANCELLED:
            raise serializers.ValidationError(
                "Cannot add collection points to a cancelled trip assignment."
            )

        if bin_row and collection_point and bin_row.collection_point_id != collection_point:
            raise serializers.ValidationError(
                {"bin_id": "Selected bin does not belong to the collection point."}
            )

        if assignment and collection_point:
            conflict = DailyTripCollectionPoint.objects.filter(
                trip_assignment_id=assignment,
                collection_point_id=collection_point,
                is_deleted=False,
            )
            if instance:
                conflict = conflict.exclude(pk=instance.pk)
            if conflict.exists():
                raise serializers.ValidationError(
                    "This collection point is already added to the trip assignment."
                )

        is_collected = attrs.get(
            "is_collected",
            getattr(instance, "is_collected", False),
        )
        collected_at = attrs.get(
            "collected_at",
            getattr(instance, "collected_at", None),
        )

        if is_collected or collected_at is not None:
            attrs["is_collected"] = True
            attrs["status"] = DailyTripCollectionPoint.STATUS_COLLECTED
            attrs["status_reason"] = None

        status_value = attrs.get("status", getattr(instance, "status", None))
        if status_value in {
            DailyTripCollectionPoint.STATUS_SKIPPED,
            DailyTripCollectionPoint.STATUS_MISSED,
        } and not (is_collected or collected_at is not None):
            attrs["is_collected"] = False
            attrs["collected_weight_kg"] = None

        return attrs
