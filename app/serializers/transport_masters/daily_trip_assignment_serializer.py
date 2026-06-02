from django.utils import timezone
from rest_framework import serializers

from app.serializers.company_projects.tenancy import TenancyReadSerializerMixin
from app.serializers.user_creations.user_serializer import UniqueIdOrPkField

from app.models.transport_masters.daily_trip_assignment import DailyTripAssignment
from app.models.transport_masters.trip_definition import TripDefinition
from app.models.user_creations.stafftemplate import StaffTemplate
from app.models.user_creations.alternative_staff_template import AlternativeStaffTemplate
from app.models.masters.panchayat import Panchayat
from app.models.assets.collection_point import Collection_point
from app.models.user_creations.waste_collection_bluetooth import WasteType


# ==========================================================
# MAIN SERIALIZER
# ==========================================================

class DailyTripAssignmentSerializer(TenancyReadSerializerMixin, serializers.ModelSerializer):

    # ----------------------------------------------------------
    # WRITE-ONLY FK INPUTS
    # ----------------------------------------------------------
    trip_definition_id = UniqueIdOrPkField(
        slug_field="unique_id",
        queryset=TripDefinition.objects.filter(status="ACTIVE"),
        write_only=True,
    )
    staff_template_id = UniqueIdOrPkField(
        slug_field="unique_id",
        queryset=StaffTemplate.objects.filter(is_deleted=False),
        write_only=True,
    )
    panchayat_id = UniqueIdOrPkField(
        slug_field="unique_id",
        queryset=Panchayat.objects.filter(is_deleted=False),
        write_only=True,
    )
    collection_point_id = UniqueIdOrPkField(
        slug_field="unique_id",
        queryset=Collection_point.objects.filter(is_deleted=False),
        write_only=True,
    )
    waste_type_id = UniqueIdOrPkField(
        slug_field="unique_id",
        queryset=WasteType.objects.filter(is_deleted=False),
        write_only=True,
    )

    # ----------------------------------------------------------
    # READ-ONLY EXPANDED FIELDS
    # ----------------------------------------------------------
    trip_definition = serializers.SerializerMethodField(read_only=True)
    staff_template = serializers.SerializerMethodField(read_only=True)
    effective_staff = serializers.SerializerMethodField(read_only=True)
    panchayat = serializers.SerializerMethodField(read_only=True)
    collection_point = serializers.SerializerMethodField(read_only=True)
    waste_type = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = DailyTripAssignment
        fields = [
            "unique_id",
            "company_id",
            "company_name",
            "project_id",
            "project_name",

            # write-only inputs
            "trip_definition_id",
            "staff_template_id",
            "panchayat_id",
            "collection_point_id",
            "waste_type_id",

            # read-only expanded
            "trip_definition",
            "staff_template",
            "effective_staff",
            "panchayat",
            "collection_point",
            "waste_type",

            # scheduling
            "trip_date",
            "scheduled_time",
            "actual_start_time",
            "actual_end_time",

            # workflow
            "status",
            "approval_status",
            "remarks",

            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "unique_id",
            "actual_start_time",
            "actual_end_time",
            "created_at",
            "updated_at",
        ]

    # ----------------------------------------------------------
    # EXPANDED READ METHODS
    # ----------------------------------------------------------

    def get_trip_definition(self, obj):
        td = obj.trip_definition_id
        if not td:
            return None
        rp = getattr(td, "routeplan_id", None)
        vehicle = getattr(rp, "vehicle_id", None)
        return {
            "unique_id": td.unique_id,
            "vehicle_no": getattr(vehicle, "vehicle_no", None),
            "vehicle_capacity_kg": float(vehicle.capacity) if vehicle and vehicle.capacity is not None else None,
            "display_code": getattr(rp, "display_code", None),
            "approval_status": td.approval_status,
            "status": td.status,
        }

    def get_staff_template(self, obj):
        st = obj.staff_template_id
        if not st:
            return None
        return {
            "unique_id": st.unique_id,
            "display_code": st.display_code,
            "driver": getattr(getattr(st, "driver_id", None), "employee_name", None),
            "operator": getattr(getattr(st, "operator_id", None), "employee_name", None),
        }

    def get_effective_staff(self, obj):
        """Returns the alt template if active for trip_date, otherwise the base template."""
        alt = obj.alt_staff_template_id
        if alt:
            return {
                "source": "alternative",
                "unique_id": alt.unique_id,
                "display_code": alt.display_code,
                "driver": getattr(getattr(alt, "driver_id", None), "employee_name", None),
                "operator": getattr(getattr(alt, "operator_id", None), "employee_name", None),
                "from_date": str(alt.from_date),
                "to_date": str(alt.to_date),
            }
        st = obj.staff_template_id
        if not st:
            return None
        return {
            "source": "base",
            "unique_id": st.unique_id,
            "display_code": st.display_code,
            "driver": getattr(getattr(st, "driver_id", None), "employee_name", None),
            "operator": getattr(getattr(st, "operator_id", None), "employee_name", None),
        }

    def get_panchayat(self, obj):
        p = obj.panchayat_id
        if not p:
            return None
        return {"unique_id": p.unique_id, "panchayat_name": p.panchayat_name}

    def get_collection_point(self, obj):
        cp = obj.collection_point_id
        if not cp:
            return None
        return {"unique_id": cp.unique_id, "cp_name": cp.cp_name}

    def get_waste_type(self, obj):
        wt = obj.waste_type_id
        if not wt:
            return None
        return {
            "unique_id": wt.unique_id,
            "waste_type_name": getattr(wt, "waste_type_name", None),
        }

    # ----------------------------------------------------------
    # VALIDATION
    # ----------------------------------------------------------

    def validate(self, attrs):
        instance = getattr(self, "instance", None)

        trip_definition = attrs.get(
            "trip_definition_id", getattr(instance, "trip_definition_id", None)
        )
        trip_date = attrs.get("trip_date", getattr(instance, "trip_date", None))
        scheduled_time = attrs.get(
            "scheduled_time", getattr(instance, "scheduled_time", None)
        )
        staff_template = attrs.get(
            "staff_template_id", getattr(instance, "staff_template_id", None)
        )

        # ----------------------------------------------------------
        # CONFLICT CHECK: same vehicle + date + time
        # ----------------------------------------------------------
        if trip_definition and trip_date and scheduled_time:
            conflict_qs = DailyTripAssignment.objects.filter(
                trip_definition_id=trip_definition,
                trip_date=trip_date,
                scheduled_time=scheduled_time,
                is_deleted=False,
            ).exclude(status=DailyTripAssignment.STATUS_CANCELLED)

            if instance:
                conflict_qs = conflict_qs.exclude(pk=instance.pk)

            if conflict_qs.exists():
                raise serializers.ValidationError(
                    "Vehicle already assigned for this date and time."
                )

        # ----------------------------------------------------------
        # STAFF RESOLUTION: auto-populate alt_staff_template_id
        # ----------------------------------------------------------
        if staff_template and trip_date:
            alt = AlternativeStaffTemplate.objects.filter(
                staff_template=staff_template,
                from_date__lte=trip_date,
                to_date__gte=trip_date,
            ).first()
            attrs["alt_staff_template_id"] = alt

        return attrs


# ==========================================================
# STATUS UPDATE SERIALIZER
# ==========================================================

class DailyTripAssignmentStatusSerializer(serializers.Serializer):

    VALID_TRANSITIONS = {
        DailyTripAssignment.STATUS_SCHEDULED: [DailyTripAssignment.STATUS_IN_PROGRESS],
        DailyTripAssignment.STATUS_IN_PROGRESS: [DailyTripAssignment.STATUS_COMPLETED],
    }
    # Any status → Cancelled is handled separately

    status = serializers.ChoiceField(choices=DailyTripAssignment.STATUS_CHOICES)

    def validate_status(self, value):
        instance = self.context.get("instance")
        if not instance:
            return value

        current = instance.status
        new = value

        # Cancellation is always allowed
        if new == DailyTripAssignment.STATUS_CANCELLED:
            return value

        allowed_next = self.VALID_TRANSITIONS.get(current, [])
        if new not in allowed_next:
            raise serializers.ValidationError(
                f"Cannot transition from '{current}' to '{new}'. "
                f"Allowed: {allowed_next or ['Cancelled']}."
            )

        # Moving to In Progress requires Approved
        if (
            new == DailyTripAssignment.STATUS_IN_PROGRESS
            and instance.approval_status != DailyTripAssignment.APPROVAL_APPROVED
        ):
            raise serializers.ValidationError(
                "Trip must be Approved before it can be started."
            )

        return value


# ==========================================================
# APPROVAL UPDATE SERIALIZER
# ==========================================================

class DailyTripAssignmentApprovalSerializer(serializers.Serializer):

    approval_status = serializers.ChoiceField(
        choices=DailyTripAssignment.APPROVAL_CHOICES
    )

    def validate_approval_status(self, value):
        instance = self.context.get("instance")
        if not instance:
            return value

        current = instance.approval_status

        if current != DailyTripAssignment.APPROVAL_PENDING:
            raise serializers.ValidationError(
                f"Only Pending assignments can be approved or rejected. "
                f"Current status: '{current}'."
            )

        if value not in (
            DailyTripAssignment.APPROVAL_APPROVED,
            DailyTripAssignment.APPROVAL_REJECTED,
        ):
            raise serializers.ValidationError(
                "approval_status must be 'Approved' or 'Rejected'."
            )

        return value
