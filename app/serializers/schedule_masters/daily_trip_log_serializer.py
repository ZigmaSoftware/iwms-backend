from django.utils import timezone
from rest_framework import serializers

from app.models.assets.bin import Bin
from app.models.schedule_masters.daily_trip_assignment import DailyTripAssignment
from app.models.schedule_masters.daily_trip_log import DailyTripLog
from app.models.user_creations.staffcreation import Staffcreation
from app.serializers.company_projects.tenancy import TenancyReadSerializerMixin
from app.serializers.user_creations.user_serializer import UniqueIdOrPkField


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
        queryset=Bin.objects.filter(is_deleted=False),
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
    collection_point = serializers.SerializerMethodField(read_only=True)
    collection_points = serializers.SerializerMethodField(read_only=True)
    waste_type = serializers.SerializerMethodField(read_only=True)
    driver = serializers.SerializerMethodField(read_only=True)
    operator = serializers.SerializerMethodField(read_only=True)
    extra_operators = serializers.SerializerMethodField(read_only=True)
    vehicle = serializers.SerializerMethodField(read_only=True)
    bins = serializers.SerializerMethodField(read_only=True)
    verified_by_name = serializers.SerializerMethodField(read_only=True)

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
            "collection_point_id",
            "collection_point",
            "collection_points",
            "waste_type_id",
            "waste_type",
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
            "vehicle_id",
            "vehicle",
            "bin_ids",
            "bins",
            "remarks",
            "log_status",
            "verified_by",
            "verified_by_name",
            "verified_at",
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
        return {
            "unique_id": assignment.unique_id,
            "status": assignment.status,
            "approval_status": assignment.approval_status,
            "trip_date": str(assignment.trip_date),
            "scheduled_time": str(assignment.scheduled_time),
            "display_code": getattr(trip_plan, "display_code", assignment.unique_id),
        }

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
        assignment = obj.trip_assignment_id
        if not assignment:
            return []
        cps = (
            assignment.trip_collection_points
            .filter(is_deleted=False)
            .select_related("collection_point_id")
            .order_by("sequence")
        )
        return [
            {
                "unique_id": tcp.collection_point_id.unique_id,
                "cp_name": tcp.collection_point_id.cp_name,
                "sequence": tcp.sequence,
                "is_collected": tcp.is_collected,
            }
            for tcp in cps
            if tcp.collection_point_id
        ]

    def get_panchayat(self, obj):
        p = obj.panchayat_id
        return None if not p else {"unique_id": p.unique_id, "panchayat_name": p.panchayat_name}

    def get_collection_point(self, obj):
        cp = obj.collection_point_id
        return None if not cp else {"unique_id": cp.unique_id, "cp_name": cp.cp_name}

    def get_waste_type(self, obj):
        wt = obj.waste_type_id
        return None if not wt else {"unique_id": wt.unique_id, "waste_type_name": wt.waste_type_name}

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
                "bin_status": bin_obj.bin_status,
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
        return attrs

    def save(self, **kwargs):
        instance = self.context["instance"]
        account = self.context.get("account")
        remarks = self.validated_data.get("remarks")
        if remarks:
            instance.remarks = remarks
        instance.verified_by = account
        instance.verified_at = timezone.now()
        instance.log_status = DailyTripLog.LOG_STATUS_VERIFIED
        instance.save()
        return instance
