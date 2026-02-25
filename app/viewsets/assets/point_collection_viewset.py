from rest_framework.viewsets import ModelViewSet
from app.models.assets.point_collection import PointCollection
from app.serializers.assets.point_collection_serializer import PointCollectionSerializer
from app.viewsets.superadminmasters.company_scoped_viewset import CompanyScopedViewSet
from datetime import date
from django.db.models import Sum
from rest_framework.response import Response
from app.models.assets.panchayat_wise_collection import PanchayatCollection
from django.db import transaction
from django.db.models import F
from app.models.assets.ward_wise_collection import WardCollection
from app.utils.audit_mixin import AuditViewSetMixin


class PointCollectionViewSet(AuditViewSetMixin,CompanyScopedViewSet):

    serializer_class = PointCollectionSerializer
    lookup_field = "unique_id"

    AUDIT_MODULE = "bp-palakkad"
    AUDIT_ENDPOINT ="point-collection"

    def get_queryset(self):
        return PointCollection.objects.filter(
            
            is_deleted=False
            )

    def perform_destroy(self, instance):
        instance.is_deleted = True
        instance.save()

    @transaction.atomic
    def perform_create(self, serializer):

        super().perform_create(serializer)

        instance = serializer.instance

        if not instance.is_collected:
            return

        # ----------------------------------
        # 🌾 Panchayat Logic
        # ----------------------------------
        panchayat = instance.collection_point_id.panchayat_id

        if panchayat:
            panchayat_collection, created = PanchayatCollection.objects.get_or_create(
                panchayat_id=panchayat,
                waste_type_id=instance.waste_type_id,
                collection_date=instance.collection_date,
                trip_id=instance.trip_id,
                company_id=instance.company_id,
                project_id=instance.project_id,
                defaults={
                    "panchayat_total_weight": instance.point_collection_weight,
                    "created_by": self.request.user,
                    "updated_by": self.request.user
                }
            )

            if not created:
                PanchayatCollection.objects.filter(
                    unique_id=panchayat_collection.unique_id
                ).update(
                    panchayat_total_weight=F("panchayat_total_weight") + instance.point_collection_weight,
                    updated_by=self.request.user
                )

        # ----------------------------------
        # 🏙 Ward Logic
        # ----------------------------------
        ward = instance.collection_point_id.ward_id

        if ward:
            ward_collection, created = WardCollection.objects.get_or_create(
                ward_id=ward,
                waste_type_id=instance.waste_type_id,
                collection_date=instance.collection_date,
                trip_id=instance.trip_id,
                company_id=instance.company_id,
                project_id=instance.project_id,
                defaults={
                    "ward_total_weight": instance.point_collection_weight,
                    "created_by": self.request.user,
                    "updated_by": self.request.user
                }
            )

            if not created:
                WardCollection.objects.filter(
                    unique_id=ward_collection.unique_id
                ).update(
                    ward_total_weight=F("ward_total_weight") + instance.point_collection_weight,
                    updated_by=self.request.user
                )

    def list(self, request, *args, **kwargs):

        queryset = self.get_queryset()

        collection_point_id = request.query_params.get("collection_point_id")
        if collection_point_id:
            queryset = queryset.filter(collection_point_id=collection_point_id)

        serializer = self.get_serializer(queryset, many=True)

        today = date.today()

        daily_total = queryset.filter(
            collection_date=today
        ).aggregate(
            total=Sum("point_collection_weight")
        )

        overall_total = queryset.aggregate(
            total=Sum("point_collection_weight")
        )

        return Response({
            "date": today,
            "daily_total_weight": daily_total["total"] or 0,
            "overall_total_weight": overall_total["total"] or 0,
            "collections": serializer.data
        })