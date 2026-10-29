from rest_framework import serializers
from django.db import transaction
from django.db.models import F, Max

from app.models.masters.waste_masters.bins import Bins
from app.models.masters.customer_masters.customercreation import CustomerCreation
from app.models.core_modules.schedule_setup.collection_point import Collection_point
from app.models.masters.city import City
from app.models.masters.district import District
from app.models.masters.panchayat import Panchayat
from app.models.masters.ward import Ward
from app.models.masters.zone import Zone
from app.models.core_modules.schedule_setup.trip_plan import TripPlan
from app.models.core_modules.schedule_setup.trip_plan_collection_point import (
    TripPlanCollectionPoint,
)
from app.models.core_modules.daily_operations.daily_trip_assignment import DailyTripAssignment
from app.models.masters.transport_masters.vehicleCreation import VehicleCreation
from app.models.superadmin.staff_management.staffcreation import Staffcreation
from app.models.core_modules.schedule_setup.staff_template import StaffTemplate
from app.models.waste_collection_bluetooth.waste_collection_bluetooth import WasteType
from app.models.masters.waste_masters.property import Property
from app.models.masters.waste_masters.subproperty import SubProperty
from app.signals.trip_plan_signals import (
    _customers_for_household_stop,
    sync_daily_assignment_stops_from_plan,
)
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project
from app.serializers.company_projects.tenancy import TenancyReadSerializerMixin
from app.serializers.superadmin.staff_management.user_serializer import UniqueIdOrPkField
from app.utils.related_prefetch import prefetch_related_rows, related

RELATED_LOOKUPS = {
    "company": (Company, "company_id"),
    "project": (Project, "project_id"),
    "district": (District, "district_id"),
    "city": (City, "city_id"),
    "zone": (Zone, "zone_id"),
    "panchayat": (Panchayat, "panchayat_id"),
    "staff_template": (StaffTemplate, "staff_template_id"),
    "vehicle": (VehicleCreation, "vehicle_id"),
    "supervisor": (Staffcreation, "supervisor_id", "staff_unique_id"),
    "property_obj": (Property, "property_id"),
    "sub_property_obj": (SubProperty, "sub_property_id"),
    "waste_type": (WasteType, "waste_type_id"),
}
STAFF_TEMPLATE_LOOKUPS = {
    "driver": (Staffcreation, "driver_id", "staff_unique_id"),
    "operator": (Staffcreation, "operator_id", "staff_unique_id"),
}
STOP_LOOKUPS = {
    "collection_point": (Collection_point, "collection_point_id"),
    "bin": (Bins, "bin_id"),
    "customer": (CustomerCreation, "customer_id"),
}


def _waste_type_ids(plan):
    ids = plan.waste_type_ids or []
    if not ids and plan.waste_type_id:
        ids = [plan.waste_type_id]
    return ids


class TripPlanListSerializer(serializers.ListSerializer):
    """Resolves each plan's relations, wards, waste types and stops in one
    query per table for the whole page, instead of ~25 queries per plan."""

    def to_representation(self, data):
        plans = list(data.all() if hasattr(data, "all") else data)

        rows = prefetch_related_rows(plans, RELATED_LOOKUPS)
        prefetch_related_rows(rows["staff_template"].values(), STAFF_TEMPLATE_LOOKUPS)

        ward_ids = {wid for plan in plans for wid in plan.get_ward_ids()}
        wards = list(Ward.objects.filter(unique_id__in=ward_ids)) if ward_ids else []

        waste_type_ids = {wid for plan in plans for wid in _waste_type_ids(plan)}
        waste_types = (
            {
                row.unique_id: row
                for row in WasteType.objects.filter(unique_id__in=waste_type_ids, is_deleted=False)
            }
            if waste_type_ids else {}
        )

        plan_ids = [plan.unique_id for plan in plans]
        stops = list(
            TripPlanCollectionPoint.objects.filter(trip_plan_id__in=plan_ids, is_deleted=False)
        ) if plan_ids else []
        prefetch_related_rows(stops, STOP_LOOKUPS)
        stops_by_plan = {}
        for stop in stops:
            stops_by_plan.setdefault(stop.trip_plan_id, []).append(stop)

        for plan in plans:
            # Keep the query's row order, as plan.wards would.
            own_wards = set(plan.get_ward_ids())
            plan._wards_cache = [ward for ward in wards if ward.unique_id in own_wards]
            plan._waste_types_cache = waste_types
            plan._stops_cache = stops_by_plan.get(plan.unique_id, [])

        return super().to_representation(plans)


class TripPlanStopInputSerializer(serializers.Serializer):
    collection_type = serializers.ChoiceField(
        choices=TripPlanCollectionPoint.COLLECTION_TYPE_CHOICES,
        default=TripPlanCollectionPoint.COLLECTION_TYPE_BIN,
        required=False,
    )
    collection_point_id = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
    )
    bin_id = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
    )
    customer_id = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
    )
    sequence = serializers.IntegerField(min_value=1)
    is_active = serializers.BooleanField(default=True)


# Sentinel row used for Household/Bulk trip plans: no explicit customer_id,
# meaning "every matching customer in the plan's ward/panchayat scope" —
# expanded server-side (see trip_plan_signals._customers_for_household_stop)
# rather than listed as individual stops. The frontend Collection Mode UI
# sends exactly one of these when auto-assign mode is Household or Bulk.
AUTO_ASSIGN_STOP_SEQUENCE = 1


class TripPlanSerializer(TenancyReadSerializerMixin, serializers.ModelSerializer):
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

    district_id = UniqueIdOrPkField(
        slug_field="unique_id",
        queryset=District.objects.filter(is_deleted=False),
        write_only=True,
    )
    city_id = UniqueIdOrPkField(
        slug_field="unique_id",
        queryset=City.objects.filter(is_deleted=False),
        write_only=True,
    )
    zone_id = UniqueIdOrPkField(
        slug_field="unique_id",
        queryset=Zone.objects.filter(is_deleted=False),
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
        default=list,
    )
    staff_template_id = UniqueIdOrPkField(
        slug_field="unique_id",
        queryset=StaffTemplate.objects.filter(is_deleted=False),
        write_only=True,
    )
    vehicle_id = UniqueIdOrPkField(
        slug_field="unique_id",
        queryset=VehicleCreation.objects.filter(is_deleted=False),
        write_only=True,
    )
    supervisor_id = UniqueIdOrPkField(
        slug_field="staff_unique_id",
        queryset=Staffcreation.objects.filter(is_deleted=False),
        write_only=True,
    )
    property_id = UniqueIdOrPkField(
        slug_field="unique_id",
        queryset=Property.objects.filter(is_deleted=False),
        write_only=True,
        required=False,
        allow_null=True,
    )
    sub_property_id = UniqueIdOrPkField(
        slug_field="unique_id",
        queryset=SubProperty.objects.filter(is_deleted=False),
        write_only=True,
        required=False,
        allow_null=True,
    )
    waste_type_id = UniqueIdOrPkField(
        slug_field="unique_id",
        queryset=WasteType.objects.filter(is_deleted=False),
        write_only=True,
        required=False,
    )
    waste_type_ids = serializers.ListField(
        child=serializers.CharField(),
        write_only=True,
        required=False,
        allow_empty=False,
    )

    collection_points = TripPlanStopInputSerializer(
        many=True,
        write_only=True,
        required=False,
    )

    collection_type = serializers.ChoiceField(
        choices=TripPlan.COLLECTION_TYPE_CHOICES,
        required=False,
        default=TripPlan.COLLECTION_TYPE_BIN,
        help_text="Collection Mode: bin_collection (manual stops) or "
        "household_collection/bulk_waste_collection (auto-assigned to every "
        "matching customer in the plan's ward/panchayat scope).",
    )

    is_auto_assign = serializers.BooleanField(required=False)
    repeat_days = serializers.ListField(
        child=serializers.IntegerField(min_value=0, max_value=6),
        required=False,
        allow_null=True,
    )

    district = serializers.SerializerMethodField()
    city = serializers.SerializerMethodField()
    zone = serializers.SerializerMethodField()
    panchayat = serializers.SerializerMethodField()
    wards = serializers.SerializerMethodField()
    staff_template = serializers.SerializerMethodField()
    vehicle = serializers.SerializerMethodField()
    vehicle_substitution = serializers.SerializerMethodField()
    supervisor = serializers.SerializerMethodField()
    property = serializers.SerializerMethodField()
    sub_property = serializers.SerializerMethodField()
    waste_type = serializers.SerializerMethodField()
    waste_types = serializers.SerializerMethodField()
    start_time = serializers.SerializerMethodField()
    plan_collection_points = serializers.SerializerMethodField()
    stop_count = serializers.SerializerMethodField()

    class Meta:
        model = TripPlan
        fields = [
            "unique_id",
            "display_code",
            "company_id",
            "company_name",
            "project_id",
            "project_name",
            "company_id_input",
            "project_id_input",
            "district_id",
            "city_id",
            "zone_id",
            "panchayat_id",
            "ward_ids",
            "staff_template_id",
            "vehicle_id",
            "supervisor_id",
            "property_id",
            "sub_property_id",
            "waste_type_id",
            "waste_type_ids",
            "district",
            "city",
            "zone",
            "panchayat",
            "wards",
            "staff_template",
            "vehicle",
            "vehicle_substitution",
            "supervisor",
            "property",
            "sub_property",
            "waste_type",
            "waste_types",
            "trip_trigger_weight_kg",
            "max_vehicle_capacity_kg",
            "start_time",
            "scheduled_time",
                "is_auto_assign",
                "repeat_days",
            "approval_status",
            "status",
            "collection_type",
            "collection_points",
            "plan_collection_points",
            "stop_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "unique_id",
            "display_code",
            "created_at",
            "updated_at",
        ]
        list_serializer_class = TripPlanListSerializer

    def get_company_name(self, obj):
        return getattr(related(obj, "company"), "name", None)

    def get_project_name(self, obj):
        return getattr(related(obj, "project"), "name", None)

    def _wards(self, obj):
        cached = getattr(obj, "_wards_cache", None)
        return cached if cached is not None else obj.wards

    def _stops(self, obj):
        cached = getattr(obj, "_stops_cache", None)
        if cached is not None:
            return cached
        return TripPlanCollectionPoint.objects.filter(
            trip_plan_id=obj.unique_id, is_deleted=False,
        )

    def _ref(self, obj, attr, label_attr="name"):
        value = related(obj, attr)
        if not value:
            return None
        return {
            "unique_id": getattr(value, "unique_id", None),
            label_attr: getattr(value, label_attr, None),
        }

    def get_district(self, obj):
        return self._ref(obj, "district")

    def get_city(self, obj):
        return self._ref(obj, "city")

    def get_zone(self, obj):
        return self._ref(obj, "zone")

    def get_panchayat(self, obj):
        return self._ref(obj, "panchayat", "panchayat_name")

    def get_wards(self, obj):
        return [
            {"unique_id": w.unique_id, "ward_name": w.ward_name}
            for w in self._wards(obj)
        ]

    def get_staff_template(self, obj):
        st = related(obj, "staff_template")
        if not st:
            return None
        return {
            "unique_id": st.unique_id,
            "display_code": st.display_code,
            "driver": getattr(related(st, "driver"), "employee_name", None),
            "operator": getattr(related(st, "operator"), "employee_name", None),
        }

    def get_vehicle(self, obj):
        vehicle = related(obj, "vehicle")
        if not vehicle:
            return None
        return {
            "unique_id": vehicle.unique_id,
            "vehicle_no": vehicle.vehicle_no,
            "capacity": vehicle.capacity,
            "operational_status": vehicle.operational_status,
        }

    def get_vehicle_substitution(self, obj):
        """The replacement vehicle this plan runs on while its own vehicle
        is under breakdown (see app/services/vehicle_substitution.py)."""
        from app.services.vehicle_substitution import active_substitutions

        substitution = (
            active_substitutions()
            .filter(trip_plan_id=obj.unique_id, original_vehicle_id=obj.vehicle_id)
            .order_by("-created_at")
            .first()
        )
        if substitution is None:
            return None
        replacement = VehicleCreation.objects.filter(
            unique_id=substitution.replacement_vehicle_id,
        ).first()
        return {
            "unique_id": substitution.unique_id,
            "replacement_vehicle_id": substitution.replacement_vehicle_id,
            "replacement_vehicle_no": getattr(replacement, "vehicle_no", None),
            "from_date": str(substitution.from_date),
            "to_date": str(substitution.to_date) if substitution.to_date else None,
            "vehicle_breakdown_id": substitution.vehicle_breakdown_id,
        }

    def get_supervisor(self, obj):
        supervisor = related(obj, "supervisor")
        if not supervisor:
            return None
        return {
            "unique_id": supervisor.staff_unique_id,
            "employee_name": supervisor.employee_name,
        }

    def get_property(self, obj):
        return self._ref(obj, "property_obj", "property_name")

    def get_sub_property(self, obj):
        return self._ref(obj, "sub_property_obj", "sub_property_name")

    def get_waste_type(self, obj):
        return self._ref(obj, "waste_type", "waste_type_name")

    def get_waste_types(self, obj):
        ids = _waste_type_ids(obj)
        by_id = getattr(obj, "_waste_types_cache", None)
        if by_id is None:
            waste_types = WasteType.objects.filter(
                unique_id__in=ids,
                is_deleted=False,
            )
            by_id = {item.unique_id: item for item in waste_types}
        return [
            {"unique_id": waste_type_id, "waste_type_name": by_id[waste_type_id].waste_type_name}
            for waste_type_id in ids
            if waste_type_id in by_id
        ]

    def get_start_time(self, obj):
        return str(obj.scheduled_time) if obj.scheduled_time else None

    def get_plan_collection_points(self, obj):
        result = []
        for stop in self._stops(obj):
            cp = related(stop, "collection_point")
            bin_obj = related(stop, "bin")
            customer = related(stop, "customer")
            result.append({
                "unique_id": stop.unique_id,
                "collection_type": stop.collection_type,
                "collection_point_id": stop.collection_point_id,
                "collection_point": {
                    "unique_id": cp.unique_id,
                    "cp_name": cp.cp_name,
                } if cp else None,
                "bin_id": stop.bin_id,
                "bin": {
                    "unique_id": bin_obj.unique_id,
                    "bin_name": bin_obj.bin_name,
                } if bin_obj else None,
                "customer_id": stop.customer_id,
                "customer": {
                    "unique_id": customer.unique_id,
                    "customer_name": customer.customer_name,
                } if customer else None,
                "sequence": stop.sequence,
                "is_active": stop.is_active,
            })
        return result

    def get_stop_count(self, obj):
        stops = [stop for stop in self._stops(obj) if stop.is_active]
        if obj.collection_type == TripPlan.COLLECTION_TYPE_BIN:
            return len(stops)

        ward_ids = [w.unique_id for w in self._wards(obj)]
        customer_ids = set()
        for stop in stops:
            if stop.collection_type not in {
                TripPlanCollectionPoint.COLLECTION_TYPE_HOUSEHOLD,
                TripPlanCollectionPoint.COLLECTION_TYPE_BULK,
            }:
                continue
            customer_ids.update(
                _customers_for_household_stop(stop, wards=ward_ids)
                .values_list("unique_id", flat=True)
            )
        return len(customer_ids)

    def validate(self, attrs):
        attrs.pop("company_id_input", None)
        attrs.pop("project_id_input", None)

        instance = getattr(self, "instance", None)
        panchayat = attrs.get("panchayat_id", getattr(instance, "panchayat_id", None))
        zone = attrs.get("zone_id", getattr(instance, "zone_id", None))

        # Validate ward_ids — must have at least one ward
        raw_ward_ids = attrs.get("ward_ids")
        if raw_ward_ids is not None:
            valid_ward_ids = [str(w) for w in raw_ward_ids if str(w)]
            if not valid_ward_ids:
                raise serializers.ValidationError({"ward_ids": "At least one ward is required."})
            existing = set(Ward.objects.filter(unique_id__in=valid_ward_ids, is_deleted=False).values_list("unique_id", flat=True))
            invalid = [w for w in valid_ward_ids if w not in existing]
            if invalid:
                raise serializers.ValidationError({"ward_ids": f"Invalid ward(s): {', '.join(invalid)}"})
            attrs["ward_ids"] = valid_ward_ids
        elif instance is None:
            raise serializers.ValidationError({"ward_ids": "At least one ward is required."})

        if bool(panchayat) == bool(zone):
            raise serializers.ValidationError(
                "Trip plan must belong to either a zone or a panchayat (not both, not neither)."
            )

        trigger = attrs.get(
            "trip_trigger_weight_kg",
            getattr(instance, "trip_trigger_weight_kg", None),
        )
        capacity = attrs.get(
            "max_vehicle_capacity_kg",
            getattr(instance, "max_vehicle_capacity_kg", None),
        )
        if trigger is not None and capacity is not None and trigger >= capacity:
            raise serializers.ValidationError(
                "Trigger weight must be less than vehicle capacity."
            )

        waste_type_ids = attrs.get("waste_type_ids")
        waste_type = attrs.get("waste_type_id", getattr(instance, "waste_type_id", None))
        if waste_type_ids is not None:
            normalized_waste_type_ids = [str(waste_type_id) for waste_type_id in waste_type_ids if str(waste_type_id)]
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
            if normalized_waste_type_ids:
                attrs["waste_type_id"] = normalized_waste_type_ids[0]
        elif not waste_type:
            raise serializers.ValidationError(
                {"waste_type_ids": "Select at least one waste type."}
            )

        plan_collection_type = attrs.get(
            "collection_type",
            getattr(instance, "collection_type", TripPlan.COLLECTION_TYPE_BIN),
        )

        stops = attrs.get("collection_points")
        if stops is not None:
            sequences = [stop["sequence"] for stop in stops]
            if len(sequences) != len(set(sequences)):
                raise serializers.ValidationError(
                    {"collection_points": "Stop sequences must be unique."}
                )

            bin_stop_keys = set()
            household_stop_keys = set()
            saw_auto_assign_stop = False
            for stop in stops:
                collection_type = stop.get(
                    "collection_type",
                    TripPlanCollectionPoint.COLLECTION_TYPE_BIN,
                )
                if collection_type != plan_collection_type:
                    raise serializers.ValidationError(
                        {"collection_points": "Stop type must match the trip plan's Collection Mode."}
                    )
                collection_point_id = stop.get("collection_point_id")
                bin_id = stop.get("bin_id")
                customer_id = stop.get("customer_id")

                if collection_type == TripPlanCollectionPoint.COLLECTION_TYPE_BIN:
                    if not collection_point_id:
                        raise serializers.ValidationError(
                            {"collection_points": "Collection point is required for bin collection."}
                        )
                    if not bin_id:
                        raise serializers.ValidationError(
                            {"collection_points": "Bin is required for bin collection."}
                        )

                    stop_key = (collection_point_id, bin_id)
                    if stop_key in bin_stop_keys:
                        raise serializers.ValidationError(
                            {"collection_points": "Collection point/bin rows must be unique per trip plan."}
                        )
                    bin_stop_keys.add(stop_key)

                    cp = Collection_point.objects.filter(
                        unique_id=collection_point_id,
                        is_deleted=False,
                    ).first()
                    bin_obj = Bins.objects.filter(
                        unique_id=bin_id,
                        is_deleted=False,
                    ).first()
                    if not cp:
                        raise serializers.ValidationError(
                            {"collection_points": "Invalid collection point."}
                        )
                    if not bin_obj or bin_obj.collection_point_id != cp.unique_id:
                        raise serializers.ValidationError(
                            {"collection_points": "Selected bin does not belong to the collection point."}
                        )
                    reserved_bins = TripPlanCollectionPoint.objects.filter(
                        bin_id=bin_obj.unique_id,
                        is_deleted=False,
                    )
                    if instance:
                        reserved_bins = reserved_bins.exclude(trip_plan_id=instance.unique_id)
                    if reserved_bins.exists():
                        raise serializers.ValidationError(
                            {"collection_points": "This bin is already assigned to another Trip Plan."}
                        )
                elif collection_type in (
                    TripPlanCollectionPoint.COLLECTION_TYPE_HOUSEHOLD,
                    TripPlanCollectionPoint.COLLECTION_TYPE_BULK,
                ):
                    if not customer_id:
                        # No customer_id = the auto-assign catch-all stop: every
                        # customer in the plan's ward/panchayat scope is expanded
                        # server-side (trip_plan_signals._customers_for_household_stop)
                        # rather than listed individually here. Only one such
                        # placeholder row is meaningful per plan.
                        if saw_auto_assign_stop:
                            raise serializers.ValidationError(
                                {"collection_points": "Only one auto-assign stop is allowed per trip plan."}
                            )
                        saw_auto_assign_stop = True
                        continue
                    if customer_id in household_stop_keys:
                        raise serializers.ValidationError(
                            {"collection_points": "Customer rows must be unique per trip plan."}
                        )
                    household_stop_keys.add(customer_id)
                    if not CustomerCreation.objects.filter(
                        unique_id=customer_id,
                        is_deleted=False,
                    ).exists():
                        raise serializers.ValidationError(
                            {"collection_points": "Invalid customer."}
                        )

        return attrs

    def _sync_stops(self, trip_plan, stops):
        if stops is None:
            return

        existing_stops = TripPlanCollectionPoint.objects.filter(trip_plan_id=trip_plan.unique_id)
        max_sequence = existing_stops.aggregate(max_sequence=Max("sequence")).get("max_sequence") or 0
        existing_stops.update(
            is_deleted=True,
            is_active=False,
            sequence=F("sequence") + max_sequence + len(stops) + 1000,
        )

        new_stops = []
        for stop in stops:
            collection_type = stop.get(
                "collection_type",
                TripPlanCollectionPoint.COLLECTION_TYPE_BIN,
            )
            cp = None
            bin_obj = None
            customer = None
            zone_id = None
            ward_id = None
            panchayat_id = None

            if collection_type == TripPlanCollectionPoint.COLLECTION_TYPE_BIN:
                cp = Collection_point.objects.get(unique_id=stop["collection_point_id"])
                bin_obj = Bins.objects.get(unique_id=stop["bin_id"])
                panchayat_id = cp.panchayat_id
                first_ward = Ward.objects.filter(unique_id__in=cp.get_ward_ids()).first()
                ward_id = first_ward.unique_id if first_ward else None
                zone_id = first_ward.zone_id if first_ward else None
            elif collection_type in (
                TripPlanCollectionPoint.COLLECTION_TYPE_HOUSEHOLD,
                TripPlanCollectionPoint.COLLECTION_TYPE_BULK,
            ):
                customer_id = stop.get("customer_id")
                if customer_id:
                    customer = CustomerCreation.objects.get(unique_id=customer_id)
                    panchayat_id = customer.panchayat_id
                    ward_id = customer.ward_id
                    zone_id = customer.zone_id
                else:
                    # The auto-assign catch-all stop: no single customer, so
                    # geo comes straight from the trip plan itself. bulk_create
                    # below bypasses TripPlanCollectionPoint.save() (and thus
                    # its copy_flat_geo(self, self.trip_plan_id) fallback), so
                    # copy it explicitly here. trip_plan_signals'
                    # _customers_for_household_stop() reads this same
                    # panchayat/zone (falling back to the plan's own geo) to
                    # expand this single row into one
                    # DailyTripHouseholdCollection per matching customer in
                    # scope at daily-trip-generation time (not here).
                    panchayat_id = trip_plan.panchayat_id
                    zone_id = trip_plan.zone_id
                    ward_id = None

            new_stops.append(TripPlanCollectionPoint(
                company_id=trip_plan.company_id,
                project_id=trip_plan.project_id,
                trip_plan_id=trip_plan.unique_id,
                collection_type=collection_type,
                collection_point_id=cp.unique_id if cp else None,
                bin_id=bin_obj.unique_id if bin_obj else None,
                customer_id=customer.unique_id if customer else None,
                zone_id=zone_id,
                ward_id=ward_id,
                panchayat_id=panchayat_id,
                sequence=stop["sequence"],
                is_active=stop.get("is_active", True),
            ))

        TripPlanCollectionPoint.objects.bulk_create(new_stops)

    def _sync_wards(self, trip_plan, ward_ids):
        if ward_ids is None:
            return
        valid_ids = list(
            Ward.objects.filter(unique_id__in=ward_ids, is_deleted=False).values_list("unique_id", flat=True)
        )
        trip_plan.ward_ids = ",".join(valid_ids)
        trip_plan.save(update_fields=["ward_ids"])

    def _resync_daily_assignments(self, trip_plan):
        assignments = DailyTripAssignment.objects.filter(
            trip_plan_id=trip_plan.unique_id,
            is_deleted=False,
        ).exclude(status=DailyTripAssignment.STATUS_CANCELLED)
        for assignment in assignments:
            sync_daily_assignment_stops_from_plan(assignment)

    def create(self, validated_data):
        stops = validated_data.pop("collection_points", None)
        ward_ids = validated_data.pop("ward_ids", [])
        with transaction.atomic():
            trip_plan = super().create(validated_data)
            self._sync_wards(trip_plan, ward_ids)
            self._sync_stops(trip_plan, stops)
        return trip_plan

    def update(self, instance, validated_data):
        stops = validated_data.pop("collection_points", None)
        ward_ids = validated_data.pop("ward_ids", None)
        old_vehicle_id = instance.vehicle_id
        old_template_id = instance.staff_template_id
        with transaction.atomic():
            trip_plan = super().update(instance, validated_data)
            vehicle_changed = trip_plan.vehicle_id != old_vehicle_id
            template_changed = trip_plan.staff_template_id != old_template_id
            if vehicle_changed or template_changed:
                trip_plan.display_code = trip_plan._generate_display_code()
                trip_plan.save(update_fields=["display_code"])
            if vehicle_changed:
                from app.services.vehicle_substitution import end_for_plan_vehicle_change

                # The plan's new vehicle takes over from any breakdown stand-in.
                end_for_plan_vehicle_change(trip_plan)
            self._sync_wards(trip_plan, ward_ids)
            self._sync_stops(trip_plan, stops)
            self._resync_daily_assignments(trip_plan)
        return trip_plan
