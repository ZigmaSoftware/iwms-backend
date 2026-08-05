from django.utils import timezone
from rest_framework import serializers

from app.models.schedule_masters.vehicle_breakdown import VehicleBreakdown
from app.models.schedule_masters.daily_trip_assignment import DailyTripAssignment
from app.models.transport_masters.vehicleCreation import VehicleCreation
from app.models.user_creations.staffcreation import Staffcreation


class VehicleBreakdownSerializer(serializers.ModelSerializer):

    # Tenancy write inputs (resolved by CompanyScopedViewSet.perform_create)
    company_id_input = serializers.CharField(
        write_only=True, required=False, allow_blank=True, allow_null=True
    )
    project_id_input = serializers.CharField(
        write_only=True, required=False, allow_blank=True, allow_null=True
    )

    # Write fields — accept unique_id strings
    trip_assignment_id = serializers.SlugRelatedField(
        slug_field="unique_id",
        queryset=DailyTripAssignment.objects.filter(is_deleted=False),
    )
    breakdown_vehicle_id = serializers.SlugRelatedField(
        slug_field="unique_id",
        queryset=VehicleCreation.objects.filter(is_deleted=False),
    )
    replacement_vehicle_id = serializers.SlugRelatedField(
        slug_field="unique_id",
        queryset=VehicleCreation.objects.filter(is_deleted=False),
    )
    replacement_driver_id = serializers.SlugRelatedField(
        slug_field="staff_unique_id",
        queryset=Staffcreation.objects.filter(is_deleted=False),
    )
    replacement_operator_id = serializers.SlugRelatedField(
        slug_field="staff_unique_id",
        queryset=Staffcreation.objects.filter(is_deleted=False),
    )

    # Read-only detail fields
    trip_assignment_detail = serializers.SerializerMethodField(read_only=True)
    breakdown_vehicle_detail = serializers.SerializerMethodField(read_only=True)
    replacement_vehicle_detail = serializers.SerializerMethodField(read_only=True)
    replacement_driver_detail = serializers.SerializerMethodField(read_only=True)
    replacement_operator_detail = serializers.SerializerMethodField(read_only=True)
    original_driver_detail = serializers.SerializerMethodField(read_only=True)
    original_operator_detail = serializers.SerializerMethodField(read_only=True)
    approved_by_detail = serializers.SerializerMethodField(read_only=True)
    photos = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = VehicleBreakdown
        fields = [
            "unique_id",
            "company_id",
            "project_id",
            "company_id_input",
            "project_id_input",
            "trip_assignment_id",
            "trip_assignment_detail",
            "breakdown_vehicle_id",
            "breakdown_vehicle_detail",
            "replacement_vehicle_id",
            "replacement_vehicle_detail",
            "replacement_driver_id",
            "replacement_driver_detail",
            "replacement_operator_id",
            "replacement_operator_detail",
            "original_driver_detail",
            "original_operator_detail",
            "alt_staff_template_id",
            "breakdown_time",
            "breakdown_lat",
            "breakdown_lng",
            "breakdown_location",
            "collected_weight_before_breakdown_kg",
            "breakdown_reason",
            "breakdown_remarks",
            "status",
            "approval_status",
            "approved_by",
            "approved_by_detail",
            "approved_at",
            "rejection_remarks",
            "photos",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "unique_id",
            "company_id",
            "project_id",
            "alt_staff_template_id",
            "status",
            "approval_status",
            "approved_by",
            "approved_at",
            "rejection_remarks",
            "created_at",
            "updated_at",
        ]

    # ── Validation ───────────────────────────────────────────────────

    def validate(self, attrs):
        attrs.pop("company_id_input", None)
        attrs.pop("project_id_input", None)

        assignment = attrs.get("trip_assignment_id")
        if assignment:
            if assignment.status in [
                DailyTripAssignment.STATUS_COMPLETED,
                DailyTripAssignment.STATUS_CANCELLED,
            ]:
                raise serializers.ValidationError(
                    {"trip_assignment_id": "Cannot log a breakdown for a completed or cancelled trip."}
                )

        repl = attrs.get("replacement_vehicle_id")
        orig = attrs.get("breakdown_vehicle_id")
        if repl and orig and repl.unique_id == orig.unique_id:
            raise serializers.ValidationError(
                {"replacement_vehicle_id": "Replacement vehicle must be different from the broken vehicle."}
            )

        if assignment and repl:
            conflict = DailyTripAssignment.objects.filter(
                vehicle_id=repl,
                trip_date=assignment.trip_date,
                status__in=[
                    DailyTripAssignment.STATUS_SCHEDULED,
                    DailyTripAssignment.STATUS_IN_PROGRESS,
                ],
                is_deleted=False,
            ).exclude(pk=assignment.pk).exists()
            if conflict:
                raise serializers.ValidationError(
                    {
                        "replacement_vehicle_id": (
                            f"Replacement vehicle is already assigned to another active trip on {assignment.trip_date}."
                        )
                    }
                )

        return attrs

    # ── Detail helpers ───────────────────────────────────────────────

    def _staff_dict(self, staff):
        if not staff:
            return None
        return {
            "unique_id": staff.staff_unique_id,
            "name": staff.employee_name,
        }

    def _vehicle_dict(self, vehicle):
        if not vehicle:
            return None
        return {
            "unique_id": vehicle.unique_id,
            "vehicle_no": vehicle.vehicle_no,
            "capacity": str(vehicle.capacity) if vehicle.capacity else None,
        }

    def get_trip_assignment_detail(self, obj):
        a = obj.trip_assignment_id
        if not a:
            return None
        panchayat = getattr(a, "panchayat_id", None)
        trip_plan = getattr(a, "trip_plan_id", None)
        return {
            "unique_id": a.unique_id,
            "trip_date": str(a.trip_date),
            "status": a.status,
            "scheduled_time": str(a.scheduled_time) if a.scheduled_time else None,
            "panchayat_name": panchayat.panchayat_name if panchayat else None,
            "trip_plan_display_code": trip_plan.display_code if trip_plan else None,
        }

    def get_breakdown_vehicle_detail(self, obj):
        return self._vehicle_dict(obj.breakdown_vehicle_id)

    def get_replacement_vehicle_detail(self, obj):
        return self._vehicle_dict(obj.replacement_vehicle_id)

    def get_replacement_driver_detail(self, obj):
        return self._staff_dict(obj.replacement_driver_id)

    def get_replacement_operator_detail(self, obj):
        return self._staff_dict(obj.replacement_operator_id)

    def get_original_driver_detail(self, obj):
        try:
            assignment = obj.trip_assignment_id
            template = assignment.alt_staff_template_id or assignment.staff_template_id
            if template:
                return self._staff_dict(template.driver_id)
        except Exception:
            pass
        return None

    def get_original_operator_detail(self, obj):
        try:
            assignment = obj.trip_assignment_id
            template = assignment.alt_staff_template_id or assignment.staff_template_id
            if template:
                return self._staff_dict(template.operator_id)
        except Exception:
            pass
        return None

    def get_approved_by_detail(self, obj):
        return self._staff_dict(obj.approved_by)

    def get_photos(self, obj):
        request = self.context.get("request")
        photos = []
        for photo in obj.photos.all():
            url = photo.photo.url if photo.photo else None
            if url and request is not None:
                url = request.build_absolute_uri(url)
            photos.append({"id": photo.pk, "photo": url, "uploaded_at": photo.uploaded_at})
        return photos


class VehicleBreakdownVerifySerializer(serializers.Serializer):
    """Used for PATCH /{id}/verify/ — approves the breakdown and wires the replacement."""
    remarks = serializers.CharField(required=False, allow_blank=True, default="")

    def save(self):
        instance = self.context["instance"]
        account = self.context.get("account")
        remarks = self.validated_data.get("remarks", "")
        now = timezone.now()

        if instance.approval_status == VehicleBreakdown.APPROVAL_APPROVED:
            raise serializers.ValidationError("Breakdown has already been approved.")
        if instance.approval_status == VehicleBreakdown.APPROVAL_REJECTED:
            raise serializers.ValidationError("Rejected breakdowns cannot be approved.")

        from django.db import transaction
        from app.models.schedule_masters.alternative_staff_template import AlternativeStaffTemplate

        with transaction.atomic():
            assignment = instance.trip_assignment_id

            # Create or update AlternativeStaffTemplate for replacement crew.
            # The model has a UniqueConstraint on staff_template, so use
            # update_or_create to handle cases where one already exists.
            alt_template, _ = AlternativeStaffTemplate.objects.update_or_create(
                staff_template=assignment.staff_template_id,
                defaults=dict(
                    driver_id=instance.replacement_driver_id,
                    operator_id=instance.replacement_operator_id,
                    company_id=instance.company_id,
                    project_id=instance.project_id,
                    change_reason="Vehicle Breakdown",
                    change_remarks=remarks or instance.breakdown_remarks or "",
                ),
            )

            # Update DailyTripAssignment: replacement vehicle, alt staff template, and
            # advance status to In Progress (breakdown proves the trip was underway).
            update_fields = ["vehicle_id", "alt_staff_template_id", "updated_at"]
            assignment.vehicle_id = instance.replacement_vehicle_id
            assignment.alt_staff_template_id = alt_template
            if assignment.status == DailyTripAssignment.STATUS_SCHEDULED:
                assignment.status = DailyTripAssignment.STATUS_IN_PROGRESS
                update_fields.append("status")
            assignment.save(update_fields=update_fields)

            # Update the breakdown record
            approved_by_staff = None
            if account:
                try:
                    from app.models.user_creations.staffcreation import Staffcreation
                    approved_by_staff = Staffcreation.objects.filter(
                        account=account
                    ).first()
                except Exception:
                    pass

            VehicleBreakdown.objects.filter(pk=instance.pk).update(
                alt_staff_template_id=alt_template,
                status=VehicleBreakdown.STATUS_REPLACEMENT_ARRANGED,
                approval_status=VehicleBreakdown.APPROVAL_APPROVED,
                approved_by=approved_by_staff,
                approved_at=now,
                updated_at=now,
            )
            instance.refresh_from_db()

            from app.models.schedule_masters.bin_collection_event import BinCollectionEvent

            BinCollectionEvent.objects.filter(
                trip_assignment_id=assignment,
                is_deleted=False,
            ).update(
                vehicle_breakdown_id=instance,
                updated_at=now,
            )

        from app.models.notifications.staff_notification import StaffNotification
        from app.services.staff_notification_service import notify_staff

        driver = instance.replacement_driver_id
        if driver is not None:
            notify_staff(
                driver,
                StaffNotification.TYPE_VEHICLE_REPLACEMENT_APPROVED,
                title="Vehicle replaced",
                body=(
                    f"Your vehicle on trip {instance.trip_assignment_id.unique_id} "
                    f"has been replaced with {getattr(instance.replacement_vehicle_id, 'vehicle_no', 'a new vehicle')}."
                ),
                data={
                    "vehicle_breakdown_id": instance.unique_id,
                    "trip_assignment_id": instance.trip_assignment_id.unique_id,
                },
            )

        return instance


class VehicleBreakdownRejectSerializer(serializers.Serializer):
    """Used for PATCH /{id}/reject/ — rejects the breakdown request."""
    rejection_remarks = serializers.CharField(required=True)

    def save(self):
        instance = self.context["instance"]
        now = timezone.now()

        if instance.approval_status != VehicleBreakdown.APPROVAL_PENDING:
            raise serializers.ValidationError(
                "Only pending breakdowns can be rejected."
            )

        VehicleBreakdown.objects.filter(pk=instance.pk).update(
            status=VehicleBreakdown.STATUS_REJECTED,
            approval_status=VehicleBreakdown.APPROVAL_REJECTED,
            rejection_remarks=self.validated_data["rejection_remarks"],
            updated_at=now,
        )
        instance.refresh_from_db()

        from app.models.notifications.staff_notification import StaffNotification
        from app.services.staff_notification_service import notify_staff

        # Notify the assignment's current driver — the replacement request
        # never went through, so the original vehicle/crew stands.
        assignment = instance.trip_assignment_id
        template = assignment.alt_staff_template_id or assignment.staff_template_id
        driver = getattr(template, "driver_id", None)
        if driver is not None:
            notify_staff(
                driver,
                StaffNotification.TYPE_VEHICLE_REPLACEMENT_REJECTED,
                title="Vehicle replacement rejected",
                body=(
                    f"Your vehicle replacement request on trip "
                    f"{assignment.unique_id} was rejected"
                    f"{': ' + instance.rejection_remarks if instance.rejection_remarks else '.'}"
                ),
                data={
                    "vehicle_breakdown_id": instance.unique_id,
                    "trip_assignment_id": assignment.unique_id,
                },
            )

        return instance
