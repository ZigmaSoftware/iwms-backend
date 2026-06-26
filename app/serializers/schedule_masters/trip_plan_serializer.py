from rest_framework import serializers
from django.db import transaction
from django.db.models import F, Max

from app.models.assets.bins import Bins
from app.models.customers.customercreation import CustomerCreation
from app.models.schedule_masters.collection_point import Collection_point
from app.models.masters.city import City
from app.models.masters.district import District
from app.models.masters.panchayat import Panchayat
from app.models.masters.ward import Ward
from app.models.masters.zone import Zone
from app.models.schedule_masters.trip_plan import TripPlan
from app.models.schedule_masters.trip_plan_collection_point import (
    TripPlanCollectionPoint,
)
from app.models.transport_masters.vehicleCreation import VehicleCreation
from app.models.user_creations.staffcreation import Staffcreation
from app.models.schedule_masters.staff_template import StaffTemplate
from app.models.user_creations.waste_collection_bluetooth import WasteType
from app.models.waste_types.property import Property
from app.models.waste_types.subproperty import SubProperty
from app.serializers.company_projects.tenancy import TenancyReadSerializerMixin
from app.serializers.user_creations.user_serializer import UniqueIdOrPkField


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
    ward_id = UniqueIdOrPkField(
        slug_field="unique_id",
        queryset=Ward.objects.filter(is_deleted=False),
        write_only=True,
        required=False,
        allow_null=True,
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
    ward = serializers.SerializerMethodField()
    staff_template = serializers.SerializerMethodField()
    vehicle = serializers.SerializerMethodField()
    supervisor = serializers.SerializerMethodField()
    property = serializers.SerializerMethodField()
    sub_property = serializers.SerializerMethodField()
    waste_type = serializers.SerializerMethodField()
    waste_types = serializers.SerializerMethodField()
    start_time = serializers.SerializerMethodField()
    plan_collection_points = serializers.SerializerMethodField()

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
            "ward_id",
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
            "ward",
            "staff_template",
            "vehicle",
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
            "collection_points",
            "plan_collection_points",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "unique_id",
            "display_code",
            "created_at",
            "updated_at",
        ]

    def _ref(self, obj, attr, label_attr="name"):
        value = getattr(obj, attr, None)
        if not value:
            return None
        return {
            "unique_id": getattr(value, "unique_id", None),
            label_attr: getattr(value, label_attr, None),
        }

    def get_district(self, obj):
        return self._ref(obj, "district_id")

    def get_city(self, obj):
        return self._ref(obj, "city_id")

    def get_zone(self, obj):
        return self._ref(obj, "zone_id")

    def get_panchayat(self, obj):
        return self._ref(obj, "panchayat_id", "panchayat_name")

    def get_ward(self, obj):
        return self._ref(obj, "ward_id", "ward_name")

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

    def get_vehicle(self, obj):
        vehicle = obj.vehicle_id
        if not vehicle:
            return None
        return {
            "unique_id": vehicle.unique_id,
            "vehicle_no": vehicle.vehicle_no,
            "capacity": vehicle.capacity,
        }

    def get_supervisor(self, obj):
        supervisor = obj.supervisor_id
        if not supervisor:
            return None
        return {
            "unique_id": supervisor.staff_unique_id,
            "employee_name": supervisor.employee_name,
        }

    def get_property(self, obj):
        return self._ref(obj, "property_id", "property_name")

    def get_sub_property(self, obj):
        return self._ref(obj, "sub_property_id", "sub_property_name")

    def get_waste_type(self, obj):
        return self._ref(obj, "waste_type_id", "waste_type_name")

    def get_waste_types(self, obj):
        ids = obj.waste_type_ids or []
        if not ids and obj.waste_type_id_id:
            ids = [obj.waste_type_id_id]
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
        stops = obj.plan_collection_points.filter(is_deleted=False).select_related(
            "collection_point_id",
            "bin_id",
            "customer_id",
        )
        result = []
        for stop in stops:
            cp = stop.collection_point_id
            bin_obj = stop.bin_id
            customer = stop.customer_id
            result.append({
                "unique_id": stop.unique_id,
                "collection_type": stop.collection_type,
                "collection_point_id": stop.collection_point_id_id,
                "collection_point": {
                    "unique_id": cp.unique_id,
                    "cp_name": cp.cp_name,
                } if cp else None,
                "bin_id": stop.bin_id_id,
                "bin": {
                    "unique_id": bin_obj.unique_id,
                    "bin_name": bin_obj.bin_name,
                } if bin_obj else None,
                "customer_id": stop.customer_id_id,
                "customer": {
                    "unique_id": customer.unique_id,
                    "customer_name": customer.customer_name,
                } if customer else None,
                "sequence": stop.sequence,
                "is_active": stop.is_active,
            })
        return result

    def validate(self, attrs):
        attrs.pop("company_id_input", None)
        attrs.pop("project_id_input", None)

        instance = getattr(self, "instance", None)
        panchayat = attrs.get("panchayat_id", getattr(instance, "panchayat_id", None))
        zone = attrs.get("zone_id", getattr(instance, "zone_id", None))
        ward = attrs.get("ward_id", getattr(instance, "ward_id", None))
        if not ward:
            raise serializers.ValidationError(
                {"ward_id": "Ward is required."}
            )
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
                attrs["waste_type_id"] = WasteType.objects.get(unique_id=normalized_waste_type_ids[0])
        elif not waste_type:
            raise serializers.ValidationError(
                {"waste_type_ids": "Select at least one waste type."}
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
            for stop in stops:
                collection_type = stop.get(
                    "collection_type",
                    TripPlanCollectionPoint.COLLECTION_TYPE_BIN,
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
                    if not bin_obj or bin_obj.collection_point_id != cp:
                        raise serializers.ValidationError(
                            {"collection_points": "Selected bin does not belong to the collection point."}
                        )
                elif collection_type == TripPlanCollectionPoint.COLLECTION_TYPE_HOUSEHOLD:
                    if not customer_id:
                        raise serializers.ValidationError(
                            {"collection_points": "Customer is required for household collection."}
                        )
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

        existing_stops = TripPlanCollectionPoint.objects.filter(trip_plan_id=trip_plan)
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
            zone = None
            ward = None
            panchayat = None

            if collection_type == TripPlanCollectionPoint.COLLECTION_TYPE_BIN:
                cp = Collection_point.objects.select_related(
                    "panchayat_id",
                ).get(unique_id=stop["collection_point_id"])
                bin_obj = Bins.objects.get(unique_id=stop["bin_id"])
                panchayat = cp.panchayat_id
                first_ward = cp.wards.select_related("zone_id").first()
                ward = first_ward
                zone = first_ward.zone_id if first_ward else None
            elif collection_type == TripPlanCollectionPoint.COLLECTION_TYPE_HOUSEHOLD:
                customer = CustomerCreation.objects.select_related(
                    "panchayat_id",
                    "ward",
                    "zone",
                ).get(unique_id=stop["customer_id"])
                panchayat = getattr(customer, "panchayat_id", None)
                ward = getattr(customer, "ward", None)
                zone = getattr(customer, "zone", None)

            new_stops.append(TripPlanCollectionPoint(
                company_id=trip_plan.company_id,
                project_id=trip_plan.project_id,
                trip_plan_id=trip_plan,
                collection_type=collection_type,
                collection_point_id=cp,
                bin_id=bin_obj,
                customer_id=customer,
                zone_id=zone,
                ward_id=ward,
                panchayat_id=panchayat,
                sequence=stop["sequence"],
                is_active=stop.get("is_active", True),
            ))

        TripPlanCollectionPoint.objects.bulk_create(new_stops)

    def create(self, validated_data):
        stops = validated_data.pop("collection_points", None)
        with transaction.atomic():
            trip_plan = super().create(validated_data)
            self._sync_stops(trip_plan, stops)
        return trip_plan

    def update(self, instance, validated_data):
        stops = validated_data.pop("collection_points", None)
        with transaction.atomic():
            trip_plan = super().update(instance, validated_data)
            self._sync_stops(trip_plan, stops)
        return trip_plan
