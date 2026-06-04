from django.db import transaction
from django.db.models import Count, Sum
from django.utils import timezone

from app.models.schedule_masters.bin_collection_event import BinCollectionEvent
from app.serializers.schedule_masters.bin_collection_event_serializer import (
    BinCollectionEventSerializer,
)
from app.utils.audit_mixin import AuditViewSetMixin
from app.viewsets.superadminmasters.company_scoped_viewset import CompanyScopedViewSet


class BinCollectionEventViewSet(AuditViewSetMixin, CompanyScopedViewSet):
    serializer_class = BinCollectionEventSerializer
    lookup_field = "unique_id"
    permission_resource = "BinCollectionEvent"

    AUDIT_MODULE = "transport-masters"
    AUDIT_ENDPOINT = "bin-collection-event"

    def get_queryset(self):
        queryset = (
            BinCollectionEvent.objects.select_related(
                "company_id",
                "project_id",
                "trip_assignment_id",
                "trip_assignment_id__trip_plan_id",
                "trip_assignment_id__trip_plan_id__vehicle_id",
                "trip_assignment_id__vehicle_id",
                "trip_assignment_id__staff_template_id",
                "trip_assignment_id__staff_template_id__driver_id",
                "trip_assignment_id__staff_template_id__operator_id",
                "trip_assignment_id__alt_staff_template_id",
                "trip_assignment_id__alt_staff_template_id__driver_id",
                "trip_assignment_id__alt_staff_template_id__operator_id",
                "trip_assignment_id__alt_staff_template_id__approved_by",
                "trip_collection_point_id",
                "collection_point_id",
                "bin_id",
                "bin_id__wastetype_id",
                "panchayat_id",
                "ward_id",
                "ward_id__zone_id",
                "collection_point_id",
            )
            .filter(is_deleted=False)
        )

        params = self.request.query_params
        trip_assignment = params.get("trip_assignment_id")
        trip_collection_point = params.get("trip_collection_point_id")
        bin_id = params.get("bin_id")
        panchayat = params.get("panchayat_id")

        if trip_assignment:
            queryset = queryset.filter(trip_assignment_id=trip_assignment)
        if trip_collection_point:
            queryset = queryset.filter(trip_collection_point_id=trip_collection_point)
        if bin_id:
            queryset = queryset.filter(bin_id=bin_id)
        if panchayat:
            queryset = queryset.filter(panchayat_id=panchayat)

        return queryset

    # -------------------------------------------------
    # COLLECTION SYNC HELPERS
    # -------------------------------------------------

    def _account(self):
        return self._get_account()

    def _event_context(self, instance):
        collection_point = getattr(instance, "collection_point_id", None)
        assignment = getattr(instance, "trip_assignment_id", None)
        bin_obj = getattr(instance, "bin_id", None)
        ward = getattr(collection_point, "ward_id", None)
        return {
            "company": getattr(instance, "company_id", None),
            "project": getattr(instance, "project_id", None),
            "panchayat": getattr(instance, "panchayat_id", None)
            or getattr(collection_point, "panchayat_id", None),
            "ward": ward,
            "zone": getattr(ward, "zone_id", None),
            "waste_type": getattr(bin_obj, "wastetype_id", None),
            "trip": getattr(assignment, "trip_plan_id", None),
            "event": instance,
            "weight": getattr(instance, "collected_weight_kg", 0) or 0,
            "collection_date": (
                instance.created_at.date()
                if getattr(instance, "created_at", None)
                else timezone.localdate()
            ),
        }

    def _same_sync_context(self, left, right):
        if not left or not right:
            return False
        keys = ("panchayat", "ward", "waste_type", "trip", "collection_date")
        return all(left.get(key) == right.get(key) for key in keys)

    def _upsert_first_or_create(self, queryset, defaults, create_kwargs):
        account = self._account()
        defaults = dict(defaults)
        create_kwargs = dict(create_kwargs)
        if account:
            defaults["updated_by"] = account

        instance = queryset.first()
        if instance:
            queryset.exclude(pk=instance.pk).delete()
            for field, value in defaults.items():
                setattr(instance, field, value)
            instance.save(update_fields=[*defaults.keys(), "updated_at"])
            return instance

        if account:
            create_kwargs["created_by"] = account
            create_kwargs["updated_by"] = account
        create_values = {**defaults, **create_kwargs}
        return queryset.model.objects.create(**create_values)


    def _sync_collections(self, ctx):
        if not ctx:
            return
        self._sync_panchayat_collection(ctx)
        self._sync_ward_collection(ctx)
        self._sync_zone_collection(ctx)


    # -------------------------------------------------
    # CREATE / UPDATE / DELETE
    # -------------------------------------------------

    @transaction.atomic
    def perform_create(self, serializer):
        super().perform_create(serializer)
        self._sync_collections(self._event_context(serializer.instance))

    @transaction.atomic
    def perform_update(self, serializer):
        previous_ctx = self._event_context(serializer.instance)
        super().perform_update(serializer)
        instance = serializer.instance
        current_ctx = self._event_context(instance)

        if not self._same_sync_context(previous_ctx, current_ctx):
            self._sync_zone_collection(previous_ctx)
        self._sync_collections(current_ctx)

    @transaction.atomic
    def perform_destroy(self, instance):
        ctx = self._event_context(instance)
        previous_data = self._serialize_instance(instance)
        instance.is_deleted = True
        instance.is_active = False
        instance.save(update_fields=["is_deleted", "is_active", "updated_at"])
        self._soft_delete_collection_rows(instance)
        self.log_audit(
            self.request,
            instance=instance,
            previous_data=previous_data,
            new_data=self._serialize_instance(instance),
        )
        self._sync_zone_collection(ctx)
