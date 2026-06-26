from rest_framework import serializers

from app.models.masters.panchayat import Panchayat
from app.models.masters.ward import Ward
from app.models.schedule_masters.daily_trip_assignment import DailyTripAssignment
from app.models.schedule_masters.daily_trip_collection_point import DailyTripCollectionPoint
from app.models.schedule_masters.trip_plan import TripPlan
from app.models.schedule_masters.collection_point import Collection_point
from app.models.assets.bins import Bins
from app.models.transport_masters.vehicleCreation import VehicleCreation
from app.models.schedule_masters.alternative_staff_template import AlternativeStaffTemplate
from app.models.schedule_masters.staff_template import StaffTemplate
from app.models.user_creations.staffcreation import Staffcreation
from app.models.user_creations.waste_collection_bluetooth import WasteType
from app.services.daily_trip_generation import ensure_assignment_collection_points
from app.serializers.company_projects.tenancy import TenancyReadSerializerMixin
from app.serializers.user_creations.user_serializer import UniqueIdOrPkField


class DailyTripCollectionPointInlineSerializer(serializers.ModelSerializer):
    collection_point = serializers.SerializerMethodField(read_only=True)
    bin = serializers.SerializerMethodField(read_only=True)
    collected_by_staff = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = DailyTripCollectionPoint
        fields = [
            "unique_id",
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
        ]

    def get_collection_point(self, obj):
        cp = obj.collection_point_id
        if not cp:
            return None
        return {
            "unique_id": cp.unique_id,
            "cp_name": cp.cp_name,
            "latitude": cp.latitude,
            "longitude": cp.longitude,
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

    def get_collected_by_staff(self, obj):
        staff = obj.collected_by
        if not staff:
            return None
        return {
            "unique_id": staff.staff_unique_id,
            "employee_name": staff.employee_name,
        }


class DailyTripAssignmentSerializer(TenancyReadSerializerMixin, serializers.ModelSerializer):
    company_id_input = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
        allow_null=True,
    )
    project_id_input = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
        allow_null=True,
    )
    trip_plan_id = UniqueIdOrPkField(
        slug_field="unique_id",
        queryset=TripPlan.objects.filter(is_deleted=False, status="ACTIVE"),
        write_only=True,
    )
    staff_template_id = UniqueIdOrPkField(
        slug_field="unique_id",
        queryset=StaffTemplate.objects.filter(is_deleted=False),
        write_only=True,
        required=False,
        allow_null=True,
    )
    panchayat_id = UniqueIdOrPkField(
        slug_field="unique_id",
        queryset=Panchayat.objects.filter(is_deleted=False),
        write_only=True,
        required=False,
        allow_null=True,
    )
    ward_ids = serializers.ListField(
        child=serializers.CharField(),
        write_only=True,
        required=False,
        allow_empty=True,
    )
    waste_type_ids = serializers.ListField(
        child=serializers.CharField(),
        write_only=True,
        required=False,
        allow_empty=False,
    )
    household_waste_type_ids = serializers.SlugRelatedField(
        slug_field="unique_id",
        queryset=WasteType.objects.filter(is_deleted=False),
        many=True,
        required=False,
    )
    household_waste_types = serializers.SerializerMethodField(read_only=True)
    vehicle_id = UniqueIdOrPkField(
        slug_field="unique_id",
        queryset=VehicleCreation.objects.filter(is_deleted=False),
        write_only=True,
        required=False,
        allow_null=True,
    )
    alt_staff_template_id = UniqueIdOrPkField(
        slug_field="unique_id",
        queryset=AlternativeStaffTemplate.objects.all(),
        write_only=True,
        required=False,
        allow_null=True,
    )

    trip_plan = serializers.SerializerMethodField(read_only=True)
    staff_template = serializers.SerializerMethodField(read_only=True)
    alt_staff_template = serializers.SerializerMethodField(read_only=True)
    effective_staff = serializers.SerializerMethodField(read_only=True)
    panchayat = serializers.SerializerMethodField(read_only=True)
    wards = serializers.SerializerMethodField(read_only=True)
    zone = serializers.SerializerMethodField(read_only=True)
    waste_types = serializers.SerializerMethodField(read_only=True)
    vehicle = serializers.SerializerMethodField(read_only=True)
    collection_types = serializers.SerializerMethodField(read_only=True)
    collection_points = serializers.SerializerMethodField(read_only=True)
    start_time = serializers.SerializerMethodField(read_only=True)
    collection_points_input = serializers.ListField(
        child=serializers.DictField(),
        write_only=True,
        required=False,
    )

    class Meta:
        model = DailyTripAssignment
        fields = [
            "unique_id",
            "company_id",
            "company_name",
            "project_id",
            "project_name",
            "company_id_input",
            "project_id_input",
            "trip_plan_id",
            "staff_template_id",
            "panchayat_id",
            "ward_ids",
            "waste_type_ids",
            "household_waste_type_ids",
            "household_waste_types",
            "vehicle_id",
            "alt_staff_template_id",
            "trip_plan",
            "staff_template",
            "alt_staff_template",
            "effective_staff",
            "panchayat",
            "wards",
            "zone",
            "waste_types",
            "vehicle",
            "collection_types",
            "collection_points",
            "start_time",
            "collection_points_input",
            "trip_date",
            "scheduled_time",
            "actual_start_time",
            "actual_end_time",
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
            "approval_status",
            "created_at",
            "updated_at",
        ]

    def get_trip_plan(self, obj):
        from app.models.schedule_masters.trip_plan_collection_point import TripPlanCollectionPoint
        plan = obj.trip_plan_id
        if not plan:
            return None
        stop_types = list(
            plan.plan_collection_points.filter(is_deleted=False).values_list("collection_type", flat=True)
        )
        return {
            "unique_id": plan.unique_id,
            "display_code": plan.display_code,
            "staff_template_id": getattr(getattr(plan, "staff_template_id", None), "unique_id", None),
            "staff_template": self._staff_template_payload(getattr(plan, "staff_template_id", None)),
            "scheduled_time": plan.scheduled_time,
            "zone": self._zone_payload(getattr(plan, "zone_id", None)),
            "panchayat": self._panchayat_payload(getattr(plan, "panchayat_id", None)),
            "wards": [self._ward_payload(w) for w in plan.wards.select_related("zone_id").all()],
            "vehicle_no": getattr(getattr(plan, "vehicle_id", None), "vehicle_no", None),
            "waste_type_name": getattr(getattr(plan, "waste_type_id", None), "waste_type_name", None),
            "waste_type_ids": plan.waste_type_ids or ([plan.waste_type_id_id] if plan.waste_type_id_id else []),
            "has_bin": TripPlanCollectionPoint.COLLECTION_TYPE_BIN in stop_types,
            "has_household": TripPlanCollectionPoint.COLLECTION_TYPE_HOUSEHOLD in stop_types,
        }

    def get_staff_template(self, obj):
        return self._staff_template_payload(obj.staff_template_id)

    def _staff_template_payload(self, staff_template):
        if not staff_template:
            return None
        return {
            "unique_id": staff_template.unique_id,
            "display_code": staff_template.display_code,
            "driver": getattr(getattr(staff_template, "driver_id", None), "employee_name", None),
            "operator": getattr(getattr(staff_template, "operator_id", None), "employee_name", None),
        }

    def get_alt_staff_template(self, obj):
        alt = obj.alt_staff_template_id
        if not alt:
            return None
        return {
            "unique_id": alt.unique_id,
            "display_code": alt.display_code,
            "driver": getattr(getattr(alt, "driver_id", None), "employee_name", None),
            "operator": getattr(getattr(alt, "operator_id", None), "employee_name", None),
            "from_date": str(alt.from_date),
            "to_date": str(alt.to_date),
        }

    def get_effective_staff(self, obj):
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
        return self._panchayat_payload(obj.panchayat_id)

    def get_wards(self, obj):
        return [self._ward_payload(w) for w in obj.wards.select_related("zone_id").all()]

    def get_zone(self, obj):
        plan_zone = getattr(getattr(obj, "trip_plan_id", None), "zone_id", None)
        if plan_zone:
            return self._zone_payload(plan_zone)
        # Fall back to zone from this assignment's own wards
        first_ward = obj.wards.select_related("zone_id").first()
        if first_ward:
            return self._zone_payload(getattr(first_ward, "zone_id", None))
        # Fall back to zone from the trip plan's wards
        plan = getattr(obj, "trip_plan_id", None)
        if plan:
            first_plan_ward = plan.wards.select_related("zone_id").first()
            if first_plan_ward:
                return self._zone_payload(getattr(first_plan_ward, "zone_id", None))
        return None

    def _panchayat_payload(self, panchayat):
        if not panchayat:
            return None
        return {"unique_id": panchayat.unique_id, "panchayat_name": panchayat.panchayat_name}

    def _ward_payload(self, ward):
        if not ward:
            return None
        zone = getattr(ward, "zone_id", None)
        return {
            "unique_id": ward.unique_id,
            "ward_name": ward.ward_name,
            "zone_id": getattr(zone, "unique_id", None),
            "zone_name": getattr(zone, "zone_name", None),
        }

    def _zone_payload(self, zone):
        if not zone:
            return None
        return {"unique_id": zone.unique_id, "zone_name": zone.zone_name}

    def get_waste_types(self, obj):
        ids = obj.waste_type_ids or []
        waste_types = WasteType.objects.filter(unique_id__in=ids, is_deleted=False)
        by_id = {item.unique_id: item for item in waste_types}
        return [
            {"unique_id": waste_type_id, "waste_type_name": getattr(by_id[waste_type_id], "waste_type_name", None)}
            for waste_type_id in ids
            if waste_type_id in by_id
        ]

    def get_vehicle(self, obj):
        vehicle = obj.vehicle_id
        if not vehicle:
            return None
        return {"unique_id": vehicle.unique_id, "vehicle_no": vehicle.vehicle_no}

    def get_household_waste_types(self, obj):
        return [
            {"unique_id": wt.unique_id, "waste_type_name": getattr(wt, "waste_type_name", None)}
            for wt in obj.household_waste_type_ids.all()
        ]

    def get_collection_types(self, obj):
        from app.models.schedule_masters.trip_plan_collection_point import TripPlanCollectionPoint
        plan = obj.trip_plan_id
        if not plan:
            return {"has_bin": False, "has_household": False}
        stops = plan.plan_collection_points.filter(is_deleted=False).values_list("collection_type", flat=True)
        return {
            "has_bin": TripPlanCollectionPoint.COLLECTION_TYPE_BIN in stops,
            "has_household": TripPlanCollectionPoint.COLLECTION_TYPE_HOUSEHOLD in stops,
        }

    def get_collection_points(self, obj):
        stops = obj.trip_collection_points.filter(is_deleted=False).select_related(
            "collection_point_id",
            "bin_id",
            "collected_by",
            "zone_id",
            "ward_id",
            "panchayat_id",
        ).order_by("sequence")
        return DailyTripCollectionPointInlineSerializer(stops, many=True).data

    def get_start_time(self, obj):
        return str(obj.scheduled_time) if obj.scheduled_time else None

    def _resolve_by_unique_id(self, model, value, field="unique_id"):
        if not value:
            return None
        return model.objects.get(**{field: value})

    def _sync_collection_points(self, assignment, points):
        if points is None:
            ensure_assignment_collection_points(
                assignment,
                created_by=getattr(self.context.get("request"), "user", None),
            )
            return

        for item in points:
            unique_id = item.get("unique_id")
            instance = None
            if unique_id:
                instance = DailyTripCollectionPoint.objects.filter(
                    unique_id=unique_id,
                    trip_assignment_id=assignment,
                    is_deleted=False,
                ).first()
            if not instance:
                collection_point_id = item.get("collection_point_id")
                if not collection_point_id:
                    continue
                instance = DailyTripCollectionPoint(
                    trip_assignment_id=assignment,
                    collection_point_id=self._resolve_by_unique_id(
                        Collection_point,
                        collection_point_id,
                    ),
                )

            for field in [
                "sequence",
                "is_collected",
                "collected_at",
                "collected_weight_kg",
                "status",
            ]:
                if field in item:
                    setattr(instance, field, item.get(field))

            if "collection_point_id" in item and item.get("collection_point_id"):
                instance.collection_point_id = self._resolve_by_unique_id(
                    Collection_point,
                    item.get("collection_point_id"),
                )
            if "bin_id" in item and item.get("bin_id"):
                instance.bin_id = self._resolve_by_unique_id(Bins, item.get("bin_id"))
            if "collected_by" in item:
                instance.collected_by = self._resolve_by_unique_id(
                    Staffcreation,
                    item.get("collected_by"),
                    field="staff_unique_id",
                )
            if item.get("is_collected") or item.get("collected_at"):
                instance.is_collected = True
                instance.status = DailyTripCollectionPoint.STATUS_COLLECTED
            instance.save()

        ensure_assignment_collection_points(
            assignment,
            created_by=getattr(self.context.get("request"), "user", None),
        )

    def _sync_wards(self, assignment, ward_ids):
        if ward_ids is None:
            return
        wards = Ward.objects.filter(unique_id__in=ward_ids, is_deleted=False)
        assignment.wards.set(wards)

    def create(self, validated_data):
        collection_points = validated_data.pop("collection_points_input", None)
        ward_ids = validated_data.pop("ward_ids", None)
        assignment = super().create(validated_data)
        self._sync_wards(assignment, ward_ids)
        self._sync_collection_points(assignment, collection_points)
        return assignment

    def update(self, instance, validated_data):
        collection_points = validated_data.pop("collection_points_input", None)
        ward_ids = validated_data.pop("ward_ids", None)
        assignment = super().update(instance, validated_data)
        self._sync_wards(assignment, ward_ids)
        self._sync_collection_points(assignment, collection_points)
        return assignment

    def validate(self, attrs):
        attrs.pop("company_id_input", None)
        attrs.pop("project_id_input", None)

        instance = getattr(self, "instance", None)
        trip_plan = attrs.get("trip_plan_id", getattr(instance, "trip_plan_id", None))
        trip_date = attrs.get("trip_date", getattr(instance, "trip_date", None))
        scheduled_time = attrs.get(
            "scheduled_time",
            getattr(instance, "scheduled_time", None),
        )

        if trip_plan:
            attrs.setdefault("staff_template_id", trip_plan.staff_template_id)
            attrs.setdefault("vehicle_id", trip_plan.vehicle_id)
            attrs.setdefault("panchayat_id", trip_plan.panchayat_id)
            if "ward_ids" not in attrs:
                plan_ward_ids = list(trip_plan.wards.values_list("unique_id", flat=True))
                if plan_ward_ids:
                    attrs["ward_ids"] = plan_ward_ids
            attrs.setdefault("scheduled_time", trip_plan.scheduled_time)
            scheduled_time = attrs.get("scheduled_time", scheduled_time)

        waste_type_ids = attrs.get("waste_type_ids")
        if waste_type_ids is not None:
            normalized_waste_type_ids = [
                str(waste_type_id)
                for waste_type_id in waste_type_ids
                if str(waste_type_id)
            ]
            if len(normalized_waste_type_ids) != len(set(normalized_waste_type_ids)):
                raise serializers.ValidationError(
                    {"waste_type_ids": "Waste types must be unique."}
                )
            valid_count = WasteType.objects.filter(
                unique_id__in=normalized_waste_type_ids,
                is_deleted=False,
            ).count()
            if valid_count != len(normalized_waste_type_ids):
                raise serializers.ValidationError(
                    {"waste_type_ids": "Invalid waste type selected."}
                )
            attrs["waste_type_ids"] = normalized_waste_type_ids
        elif trip_plan and not getattr(instance, "waste_type_ids", None):
            plan_waste_type_ids = [
                waste_type_id
                for waste_type_id in (trip_plan.waste_type_ids or [trip_plan.waste_type_id_id])
                if waste_type_id
            ]
            attrs.setdefault(
                "waste_type_ids",
                plan_waste_type_ids,
            )

        ward_ids = attrs.get("ward_ids")
        existing_wards = instance.wards.exists() if instance else False
        if not ward_ids and not existing_wards:
            raise serializers.ValidationError(
                {"ward_ids": "At least one ward is required for the daily trip assignment."}
            )

        if trip_plan and trip_date and scheduled_time:
            conflict_qs = DailyTripAssignment.objects.filter(
                trip_plan_id=trip_plan,
                trip_date=trip_date,
                is_deleted=False,
            ).exclude(status=DailyTripAssignment.STATUS_CANCELLED)
            if instance:
                conflict_qs = conflict_qs.exclude(pk=instance.pk)
            if conflict_qs.exists():
                raise serializers.ValidationError(
                    "Trip plan already assigned for this date and time."
                )

        staff_template = attrs.get(
            "staff_template_id",
            getattr(instance, "staff_template_id", None),
        )
        if staff_template and trip_date and "alt_staff_template_id" not in attrs:
            attrs["alt_staff_template_id"] = AlternativeStaffTemplate.objects.filter(
                staff_template=staff_template,
                from_date__lte=trip_date,
                to_date__gte=trip_date,
            ).first()

        return attrs


class DailyTripAssignmentStatusSerializer(serializers.Serializer):
    VALID_TRANSITIONS = {
        DailyTripAssignment.STATUS_SCHEDULED: [DailyTripAssignment.STATUS_IN_PROGRESS],
        DailyTripAssignment.STATUS_IN_PROGRESS: [DailyTripAssignment.STATUS_COMPLETED],
    }

    status = serializers.ChoiceField(choices=DailyTripAssignment.STATUS_CHOICES)

    def validate_status(self, value):
        instance = self.context.get("instance")
        if not instance:
            return value

        current = instance.status
        new = value
        if new == DailyTripAssignment.STATUS_CANCELLED:
            return value

        allowed_next = self.VALID_TRANSITIONS.get(current, [])
        if new not in allowed_next:
            raise serializers.ValidationError(
                f"Cannot transition from '{current}' to '{new}'. "
                f"Allowed: {allowed_next or ['Cancelled']}."
            )

        if (
            new == DailyTripAssignment.STATUS_IN_PROGRESS
            and instance.approval_status != DailyTripAssignment.APPROVAL_APPROVED
        ):
            raise serializers.ValidationError(
                "Trip must be Approved before it can be started."
            )

        return value


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
