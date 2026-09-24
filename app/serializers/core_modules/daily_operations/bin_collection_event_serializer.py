from rest_framework import serializers

from app.models.assets.bins import Bins
from app.models.schedule_masters.bin_collection_event import BinCollectionEvent
from app.models.schedule_masters.daily_trip_assignment import DailyTripAssignment
from app.models.schedule_masters.daily_trip_collection_point import (
    DailyTripCollectionPoint,
)
from app.models.schedule_masters.vehicle_breakdown import VehicleBreakdown
from app.serializers.masters.waste_masters.bins_serializer import BinsSerializer
from app.serializers.company_projects.tenancy import TenancyReadSerializerMixin
from app.serializers.masters.transport_masters.vehicleCreation_serializer import (
    VehicleCreationSerializer,
)
from app.serializers.core_modules.schedule_setup.alternative_staff_template_serializer import (
    AlternativeStaffTemplateSerializer,
)
from app.serializers.core_modules.schedule_setup.staff_template_serializer import StaffTemplateSerializer
from app.serializers.superadmin.staff_management.user_serializer import UniqueIdOrPkField
from app.serializers.waste_collection_bluetooth.waste_type_serializer import (
    WasteTypeSerializer,
)


class BinCollectionEventSerializer(TenancyReadSerializerMixin, serializers.ModelSerializer):
    created_by = serializers.CharField(source="created_by_id", read_only=True)
    updated_by = serializers.CharField(source="updated_by_id", read_only=True)

    trip_assignment_id = UniqueIdOrPkField(
        slug_field="unique_id",
        queryset=DailyTripAssignment.objects.filter(is_deleted=False),
    )
    trip_collection_point_id = UniqueIdOrPkField(
        slug_field="unique_id",
        queryset=DailyTripCollectionPoint.objects.filter(is_deleted=False),
    )
    bin_id = UniqueIdOrPkField(
        slug_field="unique_id",
        queryset=Bins.objects.filter(is_deleted=False),
        required=False,
        allow_null=True,
    )
    # NOTE: trip_assignment_id / trip_collection_point_id / bin_id are plain
    # unique_id CharFields on the model now (no DB relation). validate()
    # below resolves the related row objects explicitly wherever it needs
    # to traverse further (e.g. trip_cp.trip_assignment_id).

    bin = serializers.SerializerMethodField()
    waste_type = serializers.SerializerMethodField()
    trip_plan = serializers.SerializerMethodField()
    vehicle = serializers.SerializerMethodField()
    staff_template = serializers.SerializerMethodField()
    alternative_staff_template = serializers.SerializerMethodField()
    effective_staff_template = serializers.SerializerMethodField()
    from_date = serializers.SerializerMethodField()
    to_date = serializers.SerializerMethodField()
    extra_operator_id = serializers.SerializerMethodField()
    change_reason = serializers.SerializerMethodField()
    approved_by = serializers.SerializerMethodField()
    approval_status = serializers.SerializerMethodField()
    display_code = serializers.SerializerMethodField()
    panchayat_name = serializers.SerializerMethodField()
    ward_name = serializers.SerializerMethodField()
    zone_name = serializers.SerializerMethodField()
    collection_point = serializers.SerializerMethodField()
    breakdown_info = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = BinCollectionEvent
        fields = [
            "unique_id",
            "company_id",
            "company_name",
            "project_id",
            "project_name",
            "trip_assignment_id",
            "trip_collection_point_id",
            "collection_point_id",
            "bin_id",
            "panchayat_id",
            "bin",
            "waste_type",
            "trip_plan",
            "vehicle",
            "vehicle_breakdown_id",
            "staff_template",
            "alternative_staff_template",
            "effective_staff_template",
            "from_date",
            "to_date",
            "extra_operator_id",
            "change_reason",
            "approved_by",
            "approval_status",
            "display_code",
            "collection_date",
            "collected_weight_kg",
            "status",
            "status_reason",
            "driver_latitude",
            "driver_longitude",
            "notes",
            "panchayat_name",
            "ward_name",
            "zone_name",
            "collection_point",
            "breakdown_info",
            "created_by",
            "updated_by",
            "is_active",
            "is_deleted",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "unique_id",
            "collection_point_id",
            "panchayat_id",
            "vehicle_breakdown_id",
            "breakdown_info",
            "created_at",
            "updated_at",
        ]
        # ward_id/zone_id are SerializerMethodFields on the serializer (return
        # nested data) but also real FKs on the model — they are set in
        # validate() from the assignment (or the model's own save() as a
        # fallback), so they must NOT appear in writable fields.

    def validate(self, attrs):
        # trip_assignment_id / trip_collection_point_id / bin_id in attrs are
        # plain unique_id strings (UniqueIdOrPkField.to_internal_value already
        # normalises them). Resolve the actual rows here whenever we need to
        # traverse further.
        trip_cp_id = attrs.get(
            "trip_collection_point_id",
            getattr(self.instance, "trip_collection_point_id", None),
        )
        assignment_id = attrs.get(
            "trip_assignment_id",
            getattr(self.instance, "trip_assignment_id", None),
        )
        bin_id = attrs.get("bin_id", getattr(self.instance, "bin_id", None))

        trip_cp = (
            DailyTripCollectionPoint.objects.filter(unique_id=trip_cp_id).first()
            if trip_cp_id else None
        )

        if trip_cp:
            assignment_id = trip_cp.trip_assignment_id
            bin_id = trip_cp.bin_id
            attrs["trip_assignment_id"] = assignment_id
            attrs["bin_id"] = bin_id
            attrs["collection_point_id"] = trip_cp.collection_point_id

        assignment = (
            DailyTripAssignment.objects.filter(unique_id=assignment_id).first()
            if assignment_id else None
        )

        if not assignment_id:
            raise serializers.ValidationError(
                {"trip_assignment_id": "trip_assignment_id is required."}
            )
        if not bin_id:
            raise serializers.ValidationError({"bin_id": "bin_id is required."})

        if trip_cp and trip_cp.trip_assignment_id != assignment_id:
            raise serializers.ValidationError(
                "Trip collection point does not belong to the selected assignment."
            )

        # Set location from assignment — panchayat/ward/zone are now plain
        # unique_id CharFields; ward/zone are resolved from the assignment's
        # ward_ids when it carries exactly one ward (same rule as
        # BinCollectionEvent.save()).
        attrs["panchayat_id"] = getattr(assignment, "panchayat_id", None)
        if assignment:
            from app.models.masters.ward import Ward
            ward_ids = assignment.get_ward_ids()
            if len(ward_ids) == 1:
                ward = Ward.objects.filter(unique_id=ward_ids[0]).first()
                if ward:
                    attrs["ward_id"] = ward.unique_id
                    attrs["zone_id"] = ward.zone_id
        attrs["collection_date"] = (
            attrs.get("collection_date")
            or getattr(assignment, "trip_date", None)
        )

        status_value = attrs.get(
            "status",
            getattr(self.instance, "status", BinCollectionEvent.STATUS_COLLECTED),
        )
        weight = attrs.get("collected_weight_kg", getattr(self.instance, "collected_weight_kg", None))
        if status_value == BinCollectionEvent.STATUS_COLLECTED and weight in (None, ""):
            raise serializers.ValidationError(
                {"collected_weight_kg": "Collected weight is required when status is Collected."}
            )
        if status_value in {BinCollectionEvent.STATUS_NOT_COLLECTED, BinCollectionEvent.STATUS_COLLECT_LATER}:
            attrs["collected_weight_kg"] = None

        # These are intentionally not serializer fields. They are derived only
        # to satisfy the current model while the API exposes nested objects.
        bin_obj = Bins.objects.filter(unique_id=bin_id).first() if bin_id else None
        if hasattr(BinCollectionEvent, "waste_type_id"):
            attrs["waste_type_id"] = getattr(bin_obj, "wastetype_id", None)
        if hasattr(BinCollectionEvent, "vehicle_id"):
            attrs["vehicle_id"] = self._resolve_vehicle(assignment)
        if hasattr(BinCollectionEvent, "vehicle_breakdown_id"):
            breakdown = self._resolve_approved_breakdown(assignment)
            attrs["vehicle_breakdown_id"] = getattr(breakdown, "unique_id", None)

        return attrs

    def _resolve_vehicle(self, assignment):
        """Returns the vehicle unique_id, not the object."""
        if not assignment:
            return None
        return assignment.vehicle_id or getattr(assignment.trip_plan, "vehicle_id", None)

    def _resolve_effective_staff_template_id(self, assignment):
        """Returns the effective staff-template/alt-staff-template unique_id."""
        if not assignment:
            return None
        return assignment.alt_staff_template_id or assignment.staff_template_id

    def _resolve_approved_breakdown(self, assignment):
        if not assignment:
            return None
        breakdown = getattr(assignment, "vehicle_breakdown", None)
        if not breakdown:
            return None
        if breakdown.approval_status != VehicleBreakdown.APPROVAL_APPROVED:
            return None
        return breakdown

    def _resolve_alternative_staff_template(self, obj):
        assignment = obj.trip_assignment
        return getattr(assignment, "alt_staff_template", None)

    def get_bin(self, obj):
        bin_obj = obj.bin
        if not bin_obj:
            return None
        return BinsSerializer(bin_obj, context=self.context).data

    def get_waste_type(self, obj):
        waste_type = getattr(obj.bin, "wastetype", None)
        if not waste_type:
            return None
        return WasteTypeSerializer(waste_type, context=self.context).data

    def get_trip_plan(self, obj):
        trip_plan = getattr(obj.trip_assignment, "trip_plan", None)
        if not trip_plan:
            return None
        return {
            "unique_id": trip_plan.unique_id,
            "display_code": trip_plan.display_code,
        }

    def get_vehicle(self, obj):
        vehicle_id = self._resolve_vehicle(obj.trip_assignment)
        if not vehicle_id:
            return None
        from app.models.transport_masters.vehicleCreation import VehicleCreation
        vehicle = VehicleCreation.objects.filter(unique_id=vehicle_id).first()
        if not vehicle:
            return None
        return VehicleCreationSerializer(vehicle, context=self.context).data

    def get_staff_template(self, obj):
        staff_template = getattr(obj.trip_assignment, "staff_template", None)
        if not staff_template:
            return None
        return StaffTemplateSerializer(staff_template, context=self.context).data

    def get_alternative_staff_template(self, obj):
        alt_template = self._resolve_alternative_staff_template(obj)
        if not alt_template:
            return None
        return AlternativeStaffTemplateSerializer(
            alt_template,
            context=self.context,
        ).data

    def get_effective_staff_template(self, obj):
        assignment = obj.trip_assignment
        if not assignment:
            return None

        if assignment.alt_staff_template_id:
            alt_template = assignment.alt_staff_template
            if not alt_template:
                return None
            return AlternativeStaffTemplateSerializer(
                alt_template,
                context=self.context,
            ).data

        staff_template = assignment.staff_template
        if not staff_template:
            return None
        return StaffTemplateSerializer(staff_template, context=self.context).data

    def get_from_date(self, obj):
        alt_template = self._resolve_alternative_staff_template(obj)
        return alt_template.from_date if alt_template else None

    def get_to_date(self, obj):
        alt_template = self._resolve_alternative_staff_template(obj)
        return alt_template.to_date if alt_template else None

    def get_extra_operator_id(self, obj):
        alt_template = self._resolve_alternative_staff_template(obj)
        return getattr(alt_template, "extra_operator_id", None) or []

    def get_change_reason(self, obj):
        alt_template = self._resolve_alternative_staff_template(obj)
        return getattr(alt_template, "change_reason", None) if alt_template else None

    def get_approved_by(self, obj):
        alt_template = self._resolve_alternative_staff_template(obj)
        approved_by = getattr(alt_template, "approved_by_user", None)
        if not approved_by:
            return None
        return {
            "unique_id": approved_by.staff_unique_id,
            "employee_name": approved_by.employee_name,
        }

    def get_approval_status(self, obj):
        alt_template = self._resolve_alternative_staff_template(obj)
        return getattr(alt_template, "approval_status", None) if alt_template else None

    def get_display_code(self, obj):
        alt_template = self._resolve_alternative_staff_template(obj)
        return getattr(alt_template, "display_code", None) if alt_template else None

    def get_panchayat_name(self, obj):
        panchayat = obj.panchayat
        return getattr(panchayat, "panchayat_name", None)

    def get_ward_name(self, obj):
        # Read from the model's own ward_id (set in validate from assignment)
        ward = obj.ward
        return getattr(ward, "ward_name", None)

    def get_zone_name(self, obj):
        ward = obj.ward
        zone = getattr(ward, "zone", None) if ward else None
        return getattr(zone, "zone_name", None)

    def get_collection_point(self, obj):
        cp = obj.collection_point
        if not cp:
            return None
        return {"unique_id": getattr(cp, "unique_id", None), "cp_name": getattr(cp, "cp_name", None)}

    def get_breakdown_info(self, obj):
        bd = getattr(obj, "vehicle_breakdown", None)
        if not bd:
            bd = self._resolve_approved_breakdown(obj.trip_assignment)
        if not bd:
            return None
        return {
            "unique_id": bd.unique_id,
            "status": bd.status,
            "approval_status": bd.approval_status,
            "breakdown_reason": bd.breakdown_reason,
            "breakdown_time": str(bd.breakdown_time) if bd.breakdown_time else None,
            "breakdown_location": bd.breakdown_location,
            "breakdown_vehicle_no": getattr(bd.breakdown_vehicle_id, "vehicle_no", None),
            "replacement_vehicle_no": getattr(bd.replacement_vehicle_id, "vehicle_no", None),
            "replacement_driver": getattr(bd.replacement_driver_id, "employee_name", None),
            "replacement_operator": getattr(bd.replacement_operator_id, "employee_name", None),
        }
