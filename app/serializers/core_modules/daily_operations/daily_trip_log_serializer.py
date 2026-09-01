from django.utils import timezone
from rest_framework import serializers

from app.models.assets.bins import Bins
from app.models.schedule_masters.daily_trip_assignment import DailyTripAssignment
from app.models.schedule_masters.daily_trip_log import DailyTripLog
from app.models.user_creations.staffcreation import Staffcreation
from app.serializers.company_projects.tenancy import TenancyReadSerializerMixin
from app.serializers.superadmin.staff_management.user_serializer import UniqueIdOrPkField
from app.utils.waste_images import capture_images_for_customer
from app.utils.waste_type_breakdown import bulk_waste_type_rows_for_trip_assignments


class DailyTripLogSerializer(TenancyReadSerializerMixin, serializers.ModelSerializer):
    trip_assignment_id = UniqueIdOrPkField(
        slug_field="unique_id",
        queryset=DailyTripAssignment.objects.select_related(
            "company_id",
            "project_id",
            "trip_plan_id",
            "trip_plan_id__vehicle_id",
            "staff_template_id",
            "staff_template_id__driver_id",
            "staff_template_id__operator_id",
            "alt_staff_template_id",
            "alt_staff_template_id__driver_id",
            "alt_staff_template_id__operator_id",
            "panchayat_id",
            "waste_type_id",
        ).filter(is_deleted=False),
        write_only=True,
    )
    bin_ids = serializers.SlugRelatedField(
        slug_field="unique_id",
        queryset=Bins.objects.all(),  # allow historical refs to soft-deleted bins
        many=True,
        required=False,
    )
    extra_operator_ids = serializers.SlugRelatedField(
        slug_field="staff_unique_id",
        queryset=Staffcreation.objects.filter(is_deleted=False),
        many=True,
        required=False,
    )

    trip_assignment = serializers.SerializerMethodField(read_only=True)
    staff_template = serializers.SerializerMethodField(read_only=True)
    panchayat = serializers.SerializerMethodField(read_only=True)
    zone = serializers.SerializerMethodField(read_only=True)
    ward = serializers.SerializerMethodField(read_only=True)
    wards_detail = serializers.SerializerMethodField(read_only=True)
    location = serializers.SerializerMethodField(read_only=True)
    collection_point = serializers.SerializerMethodField(read_only=True)
    collection_points = serializers.SerializerMethodField(read_only=True)
    waste_type = serializers.SerializerMethodField(read_only=True)
    waste_types_detail = serializers.SerializerMethodField(read_only=True)
    driver = serializers.SerializerMethodField(read_only=True)
    operator = serializers.SerializerMethodField(read_only=True)
    extra_operators = serializers.SerializerMethodField(read_only=True)
    vehicle = serializers.SerializerMethodField(read_only=True)
    bins = serializers.SerializerMethodField(read_only=True)
    verified_by_name = serializers.SerializerMethodField(read_only=True)
    collection_status = serializers.SerializerMethodField(read_only=True)
    household_collections = serializers.SerializerMethodField(read_only=True)
    waste_type_breakdown = serializers.SerializerMethodField(read_only=True)
    capture_images = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = DailyTripLog
        fields = [
            "unique_id",
            "trip_assignment_id",
            "trip_assignment",
            "staff_template_id",
            "staff_template",
            "alt_staff_template_id",
            "company_id",
            "company_name",
            "project_id",
            "project_name",
            "panchayat_id",
            "panchayat",
            "zone",
            "ward",
            "wards_detail",
            "location",
            "collection_point_id",
            "collection_point",
            "collection_points",
            "waste_type_id",
            "waste_type",
            "waste_types_detail",
            "trip_date",
            "actual_start_time",
            "actual_end_time",
            "driver_id",
            "driver",
            "operator_id",
            "operator",
            "extra_operator_ids",
            "extra_operators",
            "collected_weight_kg",
            "household_collected_weight_kg",
            "vehicle_id",
            "vehicle",
            "bin_ids",
            "bins",
            "remarks",
            "log_status",
            "verified_by",
            "verified_by_name",
            "verified_at",
            "collection_status",
            "household_collections",
            "waste_type_breakdown",
            "capture_images",
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "unique_id",
            "staff_template_id",
            "alt_staff_template_id",
            "company_id",
            "project_id",
            "panchayat_id",
            "collection_point_id",
            "waste_type_id",
            "trip_date",
            "driver_id",
            "operator_id",
            "vehicle_id",
            "collected_weight_kg",
            "verified_by",
            "verified_at",
            "created_by",
            "created_at",
            "updated_at",
        ]

    def get_trip_assignment(self, obj):
        assignment = obj.trip_assignment_id
        if not assignment:
            return None
        trip_plan = getattr(assignment, "trip_plan_id", None)
        zone = getattr(trip_plan, "zone_id", None)
        return {
            "unique_id": assignment.unique_id,
            "status": assignment.status,
            "approval_status": assignment.approval_status,
            "trip_date": str(assignment.trip_date),
            "scheduled_time": str(assignment.scheduled_time),
            "display_code": getattr(trip_plan, "display_code", assignment.unique_id),
            "zone": (
                {"unique_id": zone.unique_id, "zone_name": zone.zone_name}
                if zone else None
            ),
        }

    def get_wards_detail(self, obj):
        assignment = obj.trip_assignment_id
        if not assignment:
            return []
        return [
            {"unique_id": ward.unique_id, "ward_name": ward.ward_name}
            for ward in assignment.wards.all()
        ]

    def get_staff_template(self, obj):
        # Fall back to trip assignment's templates for records created before the migration
        assignment = obj.trip_assignment_id
        template = obj.staff_template_id or getattr(assignment, "staff_template_id", None)
        alt = obj.alt_staff_template_id or getattr(assignment, "alt_staff_template_id", None)
        if not template and not alt:
            return None
        result = {
            "is_alt": alt is not None,
            "effective_display_code": (alt or template).display_code,
        }
        if template:
            result["base"] = {
                "unique_id": template.unique_id,
                "display_code": template.display_code,
                "driver": self._staff_dict(getattr(template, "driver_id", None)),
                "operator": self._staff_dict(getattr(template, "operator_id", None)),
            }
        if alt:
            result["alt"] = {
                "unique_id": alt.unique_id,
                "display_code": alt.display_code,
                "driver": self._staff_dict(getattr(alt, "driver_id", None)),
                "operator": self._staff_dict(getattr(alt, "operator_id", None)),
            }
        return result

    def get_collection_points(self, obj):
        from django.db.models import Sum
        from app.models.schedule_masters.bin_collection_event import BinCollectionEvent

        assignment = obj.trip_assignment_id
        if not assignment:
            return []
        cps = (
            assignment.trip_collection_points
            .filter(is_deleted=False)
            .select_related("collection_point_id")
            .order_by("sequence")
        )
        breakdown_by_stop = {}
        stop_ids = [tcp.unique_id for tcp in cps]
        if stop_ids:
            rows = (
                BinCollectionEvent.objects.filter(
                    trip_collection_point_id__in=stop_ids, is_deleted=False,
                )
                .values("trip_collection_point_id", "waste_type_id", "waste_type_id__waste_type_name")
                .annotate(total_weight=Sum("collected_weight_kg"))
            )
            for row in rows:
                if not row["total_weight"]:
                    continue
                breakdown_by_stop.setdefault(row["trip_collection_point_id"], []).append({
                    "waste_type_name": row["waste_type_id__waste_type_name"],
                    "collected_weight_kg": str(row["total_weight"]),
                })
        return [
            {
                "unique_id": tcp.collection_point_id.unique_id,
                "cp_name": tcp.collection_point_id.cp_name,
                "sequence": tcp.sequence,
                "is_collected": tcp.is_collected,
                "status": tcp.status,
                "collected_weight_kg": (
                    str(tcp.collected_weight_kg)
                    if tcp.collected_weight_kg is not None
                    else None
                ),
                "waste_type_breakdown": breakdown_by_stop.get(tcp.unique_id, []),
            }
            for tcp in cps
            if tcp.collection_point_id
        ]

    def get_collection_status(self, obj):
        from app.models.schedule_masters.daily_trip_household_collection import (
            DailyTripHouseholdCollection,
        )
        assignment = obj.trip_assignment_id
        if not assignment:
            return "Not Started"
        bin_stops = [cp for cp in assignment.trip_collection_points.all() if not cp.is_deleted]
        hh_stops = list(
            DailyTripHouseholdCollection.objects.filter(
                trip_assignment_id=assignment, is_deleted=False
            )
        )
        total = len(bin_stops) + len(hh_stops)
        if total == 0:
            return "Not Started"
        collected = (
            sum(1 for cp in bin_stops if cp.is_collected)
            + sum(1 for hh in hh_stops if hh.is_collected)
        )
        if collected == 0:
            return "Not Started"
        if collected == total:
            return "Completed"
        return "In Progress"

    def get_household_collections(self, obj):
        from app.models.schedule_masters.daily_trip_household_collection import (
            DailyTripHouseholdCollection,
        )
        assignment = obj.trip_assignment_id
        if not assignment:
            return []
        hh_list = (
            DailyTripHouseholdCollection.objects
            .filter(trip_assignment_id=assignment, is_deleted=False)
            .select_related("customer_id", "waste_collection_id", "waste_collection_id__customer")
            .order_by("sequence")
        )
        result = []
        for hh in hh_list:
            waste = hh.waste_collection_id
            customer = hh.customer_id or getattr(waste, "customer", None)
            waste_type_breakdown = []
            if waste:
                for column, label in (
                    ("wet_waste", "Wet Waste"),
                    ("dry_waste", "Dry Waste"),
                    ("mixed_waste", "Mixed Waste"),
                    ("sanitary_waste", "Sanitary Waste"),
                ):
                    value = getattr(waste, column, None)
                    if not value:
                        continue
                    waste_type_breakdown.append({
                        "waste_type_name": label,
                        "collected_weight_kg": str(value),
                    })
            result.append({
                "unique_id": hh.unique_id,
                "sequence": hh.sequence,
                "customer_name": getattr(customer, "customer_name", None) if customer else None,
                "customer_unique_id": getattr(customer, "unique_id", None) if customer else None,
                "is_collected": hh.is_collected,
                "collected_weight_kg": (
                    str(hh.collected_weight_kg) if hh.collected_weight_kg is not None else None
                ),
                "wet_waste": str(waste.wet_waste) if waste and waste.wet_waste else None,
                "dry_waste": str(waste.dry_waste) if waste and waste.dry_waste else None,
                "mixed_waste": str(waste.mixed_waste) if waste and waste.mixed_waste else None,
                "sanitary_waste": str(waste.sanitary_waste) if waste and waste.sanitary_waste else None,
                "waste_type_breakdown": waste_type_breakdown,
                "collected_at": hh.collected_at.isoformat() if hh.collected_at else None,
                "status": hh.status,
            })
        return result

    def get_capture_images(self, obj):
        """Capture photos taken during this trip — aggregated by matching every
        household collection's customer + collection date against
        WasteCollectionSub photos (there is no direct FK to the photo)."""
        from app.models.schedule_masters.daily_trip_household_collection import (
            DailyTripHouseholdCollection,
        )

        assignment = obj.trip_assignment_id
        if not assignment:
            return []
        request = self.context.get("request")
        images = []
        seen = set()
        hh_list = (
            DailyTripHouseholdCollection.objects
            .filter(trip_assignment_id=assignment, is_deleted=False)
            .select_related("customer_id", "waste_collection_id")
        )
        for hh in hh_list:
            customer = hh.customer_id
            waste = hh.waste_collection_id
            customer_id = getattr(customer, "unique_id", None)
            collection_date = getattr(waste, "collection_date", None)
            for img in capture_images_for_customer(customer_id, collection_date, request):
                if img["url"] not in seen:
                    seen.add(img["url"])
                    images.append(img)
        return images

    def get_waste_type_breakdown(self, obj):
        assignment = obj.trip_assignment_id
        if not assignment:
            return []
        rows = bulk_waste_type_rows_for_trip_assignments([assignment.unique_id], source="all")
        return [
            {
                "waste_type_name": row["waste_type_name"],
                "collected_weight_kg": str(row["weight_kg"]),
            }
            for row in rows
        ]

    def get_panchayat(self, obj):
        assignment = obj.trip_assignment_id
        trip_plan = getattr(assignment, "trip_plan_id", None)
        p = obj.panchayat_id or getattr(assignment, "panchayat_id", None) or getattr(trip_plan, "panchayat_id", None)
        return None if not p else {"unique_id": p.unique_id, "panchayat_name": p.panchayat_name}

    def get_zone(self, obj):
        assignment = obj.trip_assignment_id
        trip_plan = getattr(assignment, "trip_plan_id", None)
        z = obj.zone_id or getattr(trip_plan, "zone_id", None)
        return None if not z else {"unique_id": z.unique_id, "zone_name": z.zone_name}

    def get_ward(self, obj):
        assignment = obj.trip_assignment_id
        if not assignment:
            return None
        wards = assignment.wards.all()
        return [{"unique_id": w.unique_id, "ward_name": w.ward_name} for w in wards] or None

    def get_location(self, obj):
        assignment = obj.trip_assignment_id
        trip_plan = getattr(assignment, "trip_plan_id", None)
        district = getattr(trip_plan, "district_id", None)
        city = getattr(trip_plan, "city_id", None)
        panchayat = obj.panchayat_id or getattr(assignment, "panchayat_id", None) or getattr(trip_plan, "panchayat_id", None)
        zone = obj.zone_id or getattr(trip_plan, "zone_id", None)
        return {
            "district": getattr(district, "name", None),
            "city": getattr(city, "name", None),
            "panchayat": getattr(panchayat, "panchayat_name", None),
            "zone": getattr(zone, "zone_name", None),
            "local_body_name": getattr(panchayat, "panchayat_name", None) or getattr(zone, "zone_name", None),
            "local_body_level": "Panchayat" if panchayat else ("Zone" if zone else None),
        }

    def get_collection_point(self, obj):
        cp = obj.collection_point_id
        return None if not cp else {"unique_id": cp.unique_id, "cp_name": cp.cp_name}

    def get_waste_type(self, obj):
        wt = obj.waste_type_id
        return None if not wt else {"unique_id": wt.unique_id, "waste_type_name": wt.waste_type_name}

    def get_waste_types_detail(self, obj):
        """Every waste type this trip collects.

        Trip creation writes the selected waste types to the assignment's
        `waste_type_ids` JSON list, while other flows fill the `waste_types`
        M2M, so reading either one alone drops types the trip really carries.
        `_assignment_waste_type_ids` is the same union the operator-mobile bin
        scan validates against, which keeps the log consistent with what the
        app accepts.
        """
        from app.models.user_creations.waste_collection_bluetooth import WasteType
        from app.viewsets.operator_mobile.helpers import _assignment_waste_type_ids

        assignment = obj.trip_assignment_id
        if not assignment:
            return []
        ids = _assignment_waste_type_ids(assignment)
        if not ids:
            return []
        # Preserve the order the trip declared them in, then append any that
        # only the M2M/trip-plan knows about.
        ordered = [str(v) for v in (assignment.waste_type_ids or []) if str(v) in ids]
        ordered += sorted(ids - set(ordered))
        by_id = {
            wt.unique_id: wt
            for wt in WasteType.objects.filter(unique_id__in=ids, is_deleted=False)
        }
        return [
            {
                "unique_id": waste_type_id,
                "waste_type_name": by_id[waste_type_id].waste_type_name,
            }
            for waste_type_id in ordered
            if waste_type_id in by_id
        ]

    def _staff_dict(self, staff):
        if not staff:
            return None
        return {
            "staff_unique_id": staff.staff_unique_id,
            "unique_id": staff.staff_unique_id,
            "employee_name": staff.employee_name,
        }

    def get_driver(self, obj):
        return self._staff_dict(obj.driver_id)

    def get_operator(self, obj):
        return self._staff_dict(obj.operator_id)

    def get_extra_operators(self, obj):
        return [self._staff_dict(staff) for staff in obj.extra_operator_ids.all()]

    def get_vehicle(self, obj):
        vehicle = obj.vehicle_id
        if not vehicle:
            return None
        return {
            "unique_id": vehicle.unique_id,
            "vehicle_no": vehicle.vehicle_no,
            "capacity": str(vehicle.capacity) if vehicle.capacity is not None else None,
        }

    def get_bins(self, obj):
        return [
            {
                "unique_id": bin_obj.unique_id,
                "bin_name": bin_obj.bin_name,
                "bin_status": getattr(bin_obj, "bin_status", None),
            }
            for bin_obj in obj.bin_ids.all()
        ]

    def get_verified_by_name(self, obj):
        account = obj.verified_by
        staff = getattr(account, "staff", None)
        user = getattr(account, "user", None)
        return getattr(staff, "employee_name", None) or getattr(user, "username", None)

    def validate(self, attrs):
        instance = getattr(self, "instance", None)
        if instance and instance.log_status == DailyTripLog.LOG_STATUS_VERIFIED:
            raise serializers.ValidationError("Verified trip logs are read-only.")

        assignment = attrs.get(
            "trip_assignment_id",
            getattr(instance, "trip_assignment_id", None),
        )
        if assignment and assignment.status == DailyTripAssignment.STATUS_CANCELLED:
            raise serializers.ValidationError("Cannot create a log for a cancelled trip.")

        if assignment and not instance:
            if DailyTripLog.objects.filter(trip_assignment_id=assignment, is_deleted=False).exists():
                raise serializers.ValidationError("A log already exists for this trip assignment.")

        start_time = attrs.get("actual_start_time", getattr(instance, "actual_start_time", None))
        end_time = attrs.get("actual_end_time", getattr(instance, "actual_end_time", None))
        if start_time and end_time and end_time <= start_time:
            raise serializers.ValidationError("actual_end_time must be after actual_start_time.")

        return attrs


class DailyTripLogVerifySerializer(serializers.Serializer):
    remarks = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        instance = self.context.get("instance")
        if instance and instance.log_status == DailyTripLog.LOG_STATUS_VERIFIED:
            raise serializers.ValidationError("Trip log is already verified.")
        if instance and not instance.actual_end_time:
            raise serializers.ValidationError(
                "This trip hasn't ended yet — actual end time is required before it can be verified."
            )
        return attrs

    def save(self, **kwargs):
        instance = self.context["instance"]
        account = self.context.get("account")
        remarks = self.validated_data.get("remarks")
        now = timezone.now()

        update_fields = {
            "log_status": DailyTripLog.LOG_STATUS_VERIFIED,
            "verified_by_id": account.pk if account else None,
            "verified_at": now,
            "updated_at": now,
        }
        if remarks:
            update_fields["remarks"] = remarks

        DailyTripLog.objects.filter(pk=instance.pk).update(**update_fields)
        instance.refresh_from_db()
        return instance
