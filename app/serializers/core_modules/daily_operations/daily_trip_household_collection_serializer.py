from rest_framework import serializers

from app.models.masters.customer_masters.customercreation import CustomerCreation
from app.models.core_modules.daily_operations.daily_trip_assignment import DailyTripAssignment
from app.models.core_modules.daily_operations.daily_trip_household_collection import (
    DailyTripHouseholdCollection,
)
from app.serializers.company_projects.tenancy import TenancyReadSerializerMixin
from app.serializers.superadmin.staff_management.user_serializer import UniqueIdOrPkField
from app.serializers.evidence_image import EvidenceImageField, absolute_image_url
from app.utils.related_prefetch import prefetch_related_rows, related


def _household_lookups():
    from app.models.core_modules.daily_operations.wastecollection import WasteCollection
    from app.models.masters.panchayat import Panchayat
    from app.models.masters.ward import Ward
    from app.models.superadmin_masters.company import Company
    from app.models.superadmin_masters.project import Project

    return {
        "company": (Company, "company_id"),
        "project": (Project, "project_id"),
        "trip_assignment": (DailyTripAssignment, "trip_assignment_id"),
        "customer": (CustomerCreation, "customer_id"),
        "panchayat": (Panchayat, "panchayat_id"),
        "ward": (Ward, "ward_id"),
        "waste_collection": (WasteCollection, "waste_collection_id"),
    }


class DailyTripHouseholdCollectionListSerializer(serializers.ListSerializer):
    """One query per related table for the page (plus the assignments'
    trip plans), instead of ~6 per household row."""

    def to_representation(self, data):
        from app.models.core_modules.schedule_setup.trip_plan import TripPlan

        rows = list(data.all() if hasattr(data, "all") else data)
        related_rows = prefetch_related_rows(rows, _household_lookups())
        prefetch_related_rows(
            related_rows["trip_assignment"].values(), {"trip_plan": (TripPlan, "trip_plan_id")},
        )
        return super().to_representation(rows)


class DailyTripHouseholdCollectionSerializer(
    TenancyReadSerializerMixin,
    serializers.ModelSerializer,
):
    trip_assignment_id = UniqueIdOrPkField(
        slug_field="unique_id",
        queryset=DailyTripAssignment.objects.filter(is_deleted=False),
    )
    customer_id = UniqueIdOrPkField(
        slug_field="unique_id",
        queryset=CustomerCreation.objects.filter(is_deleted=False),
    )

    trip_assignment = serializers.SerializerMethodField()
    customer = serializers.SerializerMethodField()
    panchayat = serializers.SerializerMethodField()
    ward = serializers.SerializerMethodField()
    waste_breakdown = serializers.SerializerMethodField()
    status_evidence_image_url = serializers.SerializerMethodField()
    status_evidence_image = EvidenceImageField(
        required=False, allow_null=True, write_only=True
    )

    class Meta:
        model = DailyTripHouseholdCollection
        fields = [
            "unique_id",
            "company_id",
            "company_name",
            "project_id",
            "project_name",
            "trip_assignment_id",
            "trip_assignment",
            "customer_id",
            "customer",
            "collection_type",
            "waste_collection_id",
            "waste_breakdown",
            "zone_id",
            "ward_id",
            "ward",
            "panchayat_id",
            "panchayat",
            "sequence",
            "is_collected",
            "collected_at",
            "collected_weight_kg",
            "status",
            "status_reason",
            "status_latitude",
            "status_longitude",
            "status_evidence_image",
            "status_evidence_image_url",
            "customer_available_at",
            "customer_available_note",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "unique_id",
            # Set only by the citizen "I'm home now" action.
            "customer_available_at",
            "customer_available_note",
            "company_id",
            "company_name",
            "project_id",
            "project_name",
            "zone_id",
            "ward_id",
            "panchayat_id",
            "waste_collection_id",
            "trip_assignment_id",
            "customer_id",
            "created_at",
            "updated_at",
        ]
        list_serializer_class = DailyTripHouseholdCollectionListSerializer

    def get_company_name(self, obj):
        return getattr(related(obj, "company"), "name", None)

    def get_project_name(self, obj):
        return getattr(related(obj, "project"), "name", None)

    def get_trip_assignment(self, obj):
        assignment = related(obj, "trip_assignment")
        if not assignment:
            return None
        trip_plan = related(assignment, "trip_plan")
        return {
            "unique_id": assignment.unique_id,
            "trip_date": str(assignment.trip_date),
            "scheduled_time": str(assignment.scheduled_time),
            "status": assignment.status,
            "trip_plan_id": assignment.trip_plan_id,
            "trip_plan_display_code": getattr(trip_plan, "display_code", None),
        }

    def get_status_evidence_image_url(self, obj):
        return absolute_image_url(self, obj.status_evidence_image)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        status_value = attrs.get("status", getattr(self.instance, "status", None))
        existing_image = getattr(self.instance, "status_evidence_image", None)
        if status_value == DailyTripHouseholdCollection.STATUS_MISSED:
            errors = {}
            if not attrs.get("status_evidence_image") and not existing_image:
                errors["status_evidence_image"] = (
                    "A geotagged evidence image is required."
                )
            if attrs.get(
                "status_latitude", getattr(self.instance, "status_latitude", None)
            ) is None:
                errors["status_latitude"] = "Capture latitude is required."
            if attrs.get(
                "status_longitude", getattr(self.instance, "status_longitude", None)
            ) is None:
                errors["status_longitude"] = "Capture longitude is required."
            if errors:
                raise serializers.ValidationError(errors)
        return attrs

    def get_customer(self, obj):
        customer = related(obj, "customer")
        if not customer:
            return None
        return {
            "unique_id": customer.unique_id,
            "customer_name": getattr(customer, "customer_name", None),
            "building_no": getattr(customer, "building_no", None),
            "street": getattr(customer, "street", None),
        }

    def get_panchayat(self, obj):
        p = related(obj, "panchayat")
        return None if not p else {"unique_id": p.unique_id, "panchayat_name": p.panchayat_name}

    def get_ward(self, obj):
        w = related(obj, "ward")
        return None if not w else {"unique_id": w.unique_id, "ward_name": w.ward_name}

    def get_waste_breakdown(self, obj):
        wc = related(obj, "waste_collection")
        if not wc:
            return None
        return {
            "wet_waste": wc.wet_waste,
            "dry_waste": wc.dry_waste,
            "mixed_waste": wc.mixed_waste,
            "sanitary_waste": wc.sanitary_waste,
            "total_quantity": wc.total_quantity,
        }
