from django.conf import settings

from rest_framework import serializers

from app.models.schedule_masters.daily_trip_assignment import DailyTripAssignment
from app.models.schedule_masters.daily_trip_collection_point import (
    DailyTripCollectionPoint,
)


class _PanchayatBriefSerializer(serializers.Serializer):
    unique_id = serializers.CharField()
    name = serializers.CharField(source="panchayat_name")
    latitude = serializers.DecimalField(max_digits=9, decimal_places=6, allow_null=True)
    longitude = serializers.DecimalField(max_digits=9, decimal_places=6, allow_null=True)


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


class _TripPlanBriefSerializer(serializers.Serializer):
    unique_id = serializers.CharField()
    display_code = serializers.CharField()


class _CollectionPointBriefSerializer(serializers.Serializer):
    unique_id = serializers.CharField()
    name = serializers.CharField(source="cp_name")
    latitude = serializers.DecimalField(max_digits=9, decimal_places=6, allow_null=True)
    longitude = serializers.DecimalField(max_digits=9, decimal_places=6, allow_null=True)


class _BinBriefSerializer(serializers.Serializer):
    unique_id = serializers.CharField()
    bin_name = serializers.CharField()
    bin_qr = serializers.CharField()
    bin_capacity = serializers.IntegerField()


class TripCollectionPointSerializer(serializers.Serializer):
    unique_id = serializers.CharField()
    sequence = serializers.IntegerField()
    is_collected = serializers.BooleanField()
    status = serializers.CharField()
    status_reason = serializers.CharField(allow_null=True)
    collected_at = serializers.DateTimeField(allow_null=True)
    collected_weight_kg = serializers.DecimalField(
        max_digits=10, decimal_places=2, allow_null=True
    )
    collection_point = _CollectionPointBriefSerializer(source="collection_point_id")
    bin = _BinBriefSerializer(source="bin_id")


class _HouseholdCustomerBriefSerializer(serializers.Serializer):
    """Adapted (not a straight ModelSerializer): the app reads a nested
    `customer` dict off each household stop, built from the related
    CustomerCreation's address fields."""

    unique_id = serializers.SerializerMethodField()
    name = serializers.SerializerMethodField()
    contact_no = serializers.SerializerMethodField()
    address = serializers.SerializerMethodField()
    latitude = serializers.SerializerMethodField()
    longitude = serializers.SerializerMethodField()

    def get_unique_id(self, customer):
        return customer.unique_id

    def get_name(self, customer):
        return customer.customer_name

    def get_contact_no(self, customer):
        return customer.contact_no

    def get_address(self, customer):
        parts = [
            customer.building_no, customer.street, customer.area,
            getattr(customer.city, "name", None),
        ]
        return ", ".join(p for p in parts if p) or None

    def get_latitude(self, customer):
        return customer.latitude

    def get_longitude(self, customer):
        return customer.longitude


class HouseholdCollectionSerializer(serializers.Serializer):
    unique_id = serializers.CharField()
    sequence = serializers.IntegerField()
    is_collected = serializers.BooleanField()
    status = serializers.CharField()
    status_reason = serializers.CharField(allow_null=True)
    collected_at = serializers.DateTimeField(allow_null=True)
    collected_weight_kg = serializers.DecimalField(
        max_digits=10, decimal_places=2, allow_null=True
    )
    customer = serializers.SerializerMethodField()

    def get_customer(self, obj):
        if not obj.customer_id_id:
            return None
        return _HouseholdCustomerBriefSerializer(obj.customer_id).data


class _CrewMemberSerializer(serializers.Serializer):
    """A driver/operator/extra-operator entry in the `crew` block. Built from
    a Staffcreation instance (or None), not a plain ModelSerializer, since the
    role label and attendance status aren't columns on that model."""

    unique_id = serializers.SerializerMethodField()
    name = serializers.SerializerMethodField()
    emp_id = serializers.SerializerMethodField()
    role = serializers.SerializerMethodField()
    phone = serializers.SerializerMethodField()
    photo_url = serializers.SerializerMethodField()

    def get_unique_id(self, staff):
        return staff.staff_unique_id

    def get_name(self, staff):
        return staff.employee_name

    def get_emp_id(self, staff):
        return staff.emp_id

    def get_role(self, staff):
        return getattr(staff.staffusertype_id, "name", None)

    def get_phone(self, staff):
        personal = getattr(staff, "personal_details", None)
        return getattr(personal, "contact_mobile", None)

    def get_photo_url(self, staff):
        request = self.context.get("request")
        if not request:
            return None

        # Prefer the face registered for attendance (Employee.image_path),
        # falling back to the admin-uploaded staff photo — same resolution
        # the staff-profile endpoint uses, so the circle matches the header.
        emp = getattr(staff, "attendance_profile", None)
        image_path = getattr(emp, "image_path", None)
        if image_path and not isinstance(image_path, (bytes, bytearray, memoryview)):
            return request.build_absolute_uri(settings.MEDIA_URL + image_path.lstrip("/"))

        if staff.photo:
            return request.build_absolute_uri(staff.photo.url)
        return None


class _RetripRequestBriefSerializer(serializers.Serializer):
    unique_id = serializers.CharField()
    status = serializers.CharField()
    reason = serializers.CharField(allow_null=True)
    pending_bin_count = serializers.IntegerField()
    pending_household_count = serializers.IntegerField()
    created_at = serializers.DateTimeField()


class MyTripTodaySerializer(serializers.Serializer):
    assignment_unique_id = serializers.CharField(source="unique_id")
    trip_date = serializers.DateField()
    status = serializers.CharField()
    collection_type = serializers.SerializerMethodField()
    scheduled_time = serializers.TimeField()
    actual_start_time = serializers.TimeField(allow_null=True)
    actual_end_time = serializers.TimeField(allow_null=True)
    # Precise start/end timestamps — `isStarted`/`isFinished` on the app side
    # key off these rather than the wall-clock-only *_time fields, matching
    # what `require_trip_started`/`mark_started`/`mark_ended` actually set.
    actual_start_at = serializers.DateTimeField(allow_null=True)
    actual_end_at = serializers.DateTimeField(allow_null=True)
    panchayat = serializers.SerializerMethodField()
    ward = serializers.SerializerMethodField()
    waste_type = _WasteTypeBriefSerializer(source="primary_waste_type", allow_null=True)
    vehicle = _VehicleBriefSerializer(source="vehicle_id", allow_null=True)
    trip_plan = serializers.SerializerMethodField()
    progress = serializers.SerializerMethodField()
    collection_points = serializers.SerializerMethodField()
    household_collections = serializers.SerializerMethodField()
    crew = serializers.SerializerMethodField()
    # The Re-Trip request awaiting supervisor review, if any — lets the
    # driver's home screen keep showing "awaiting approval" after a refresh,
    # not just in the direct response to the `end` action that created it.
    retrip_request = serializers.SerializerMethodField()

    def get_retrip_request(self, obj):
        pending = obj.retrip_requests.filter(status="Pending").first()
        if not pending:
            return None
        return _RetripRequestBriefSerializer(pending).data

    def get_collection_type(self, obj):
        return getattr(obj.trip_plan_id, "collection_type", None)

    def get_panchayat(self, obj):
        if not obj.panchayat_id_id:
            return None
        return _PanchayatBriefSerializer(obj.panchayat_id).data

    def get_ward(self, obj):
        # An assignment can carry several wards; the trip header only needs
        # a single area label, so the first is authoritative here.
        ward = obj.wards.first()
        if not ward:
            return None
        return _WardBriefSerializer(ward).data

    def get_trip_plan(self, obj):
        if not obj.trip_plan_id_id:
            return None
        return _TripPlanBriefSerializer(obj.trip_plan_id).data

    def get_progress(self, obj):
        bin_children = list(obj.trip_collection_points.filter(is_deleted=False))
        household_children = list(
            obj.trip_household_collections.filter(is_deleted=False)
        )
        children = bin_children + household_children
        total = len(children)
        collected = sum(1 for c in children if c.is_collected)
        resolved = sum(
            1 for c in children
            if c.is_collected or c.status not in ("Pending",)
        )
        return {
            "collected": collected,
            "total": total,
            "resolved": resolved,
            "completed": total > 0 and collected == total,
        }

    def get_collection_points(self, obj):
        children = (
            obj.trip_collection_points
            .filter(is_deleted=False)
            .select_related("collection_point_id", "bin_id")
            .order_by("sequence")
        )
        return TripCollectionPointSerializer(children, many=True).data

    def get_household_collections(self, obj):
        children = (
            obj.trip_household_collections
            .filter(is_deleted=False)
            .select_related("customer_id", "customer_id__city")
            .order_by("sequence")
        )
        return HouseholdCollectionSerializer(children, many=True).data

    def get_crew(self, obj):
        template = obj.staff_template_id
        if template is None:
            return None
        driver = getattr(template, "driver_id", None)
        operator = getattr(template, "operator_id", None)
        extra_ids = getattr(template, "extra_operator_id", None) or []

        extra_operators = []
        if extra_ids:
            from app.models.user_creations.staffcreation import Staffcreation
            extra_operators = list(
                Staffcreation.objects.filter(
                    staff_unique_id__in=extra_ids, is_deleted=False
                ).select_related("staffusertype_id", "personal_details")
            )

        context = self.context
        return {
            "driver": _CrewMemberSerializer(driver, context=context).data if driver else None,
            "operator": _CrewMemberSerializer(operator, context=context).data if operator else None,
            "extra_operators": _CrewMemberSerializer(
                extra_operators, many=True, context=context
            ).data,
            "is_alt_active": bool(obj.alt_staff_template_id_id),
            "template_code": getattr(template, "unique_id", None),
            "alt_template_code": getattr(obj.alt_staff_template_id, "unique_id", None),
        }
