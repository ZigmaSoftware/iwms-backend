
import csv
import io

from django.db import transaction
from django.db.models import Exists, OuterRef, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from app.utils.bulk_upload_mixin import bulk_upload_response

from app.viewsets.superadmin_masters.company_scoped_viewset import CompanyScopedViewSet
from app.models.masters.transport_masters.vehicleCreation import (
    VehicleCreation,
    VehicleDocumentHistory,
)
from app.models.masters.transport_masters.vehicleTypeCreation import VehicleTypeCreation
from app.models.masters.transport_masters.fuel import Fuel
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project
from app.models.core_modules.daily_operations.daily_trip_assignment import DailyTripAssignment
from app.serializers.masters.transport_masters.vehicleCreation_serializer import (
    VehicleCreationSerializer,
    VehicleDocumentHistorySerializer,
)
from app.utils.audit_mixin import AuditViewSetMixin
from app.utils.audit_context import resolve_actor
from app.utils.filters import (
    ModelFieldQueryFilter,
    ModelFieldSearchFilter,
    SerializerOrderingFilter,
)
from app.utils.pagination import LimitOffsetWithPage

class VehicleCreationViewSet(AuditViewSetMixin,CompanyScopedViewSet):
    serializer_class = VehicleCreationSerializer
    lookup_field = "unique_id"
    filter_backends = [
        ModelFieldQueryFilter,
        ModelFieldSearchFilter,
        SerializerOrderingFilter,
    ]
    pagination_class = LimitOffsetWithPage
    ordering_fields = ["vehicle_no", "is_active"]

    AUDIT_MODULE = "transport-masters"
    AUDIT_ENDPOINT = "vehicles"

    def get_queryset(self):
        busy_today = DailyTripAssignment.objects.filter(
            vehicle_id=OuterRef("unique_id"),
            trip_date=timezone.localdate(),
            is_deleted=False,
        ).exclude(
            status__in=[
                DailyTripAssignment.STATUS_CANCELLED,
                DailyTripAssignment.STATUS_COMPLETED,
            ]
        )

        qs = VehicleCreation.objects.filter(is_deleted=False).annotate(
            is_assigned_today=Exists(busy_today)
        )

        if self._is_supervisor_user():
            qs = qs.filter(
                Q(supervisor_id=getattr(self.request.user, "staff_unique_id", None))
                | Q(supervisor_id=getattr(self.request.user, "unique_id", None))
            ).distinct()

        return qs

    def get_object(self):
        lookup_field = self.lookup_field
        lookup_url_kwarg = self.lookup_url_kwarg or lookup_field
        lookup_value = self.kwargs.get(lookup_url_kwarg)
        queryset = self.filter_queryset(self.get_queryset())

        obj = get_object_or_404(queryset, **{lookup_field: lookup_value})

        self.check_object_permissions(self.request, obj)
        return obj

    def perform_update(self, serializer):
        previous_documents = self._document_snapshot(serializer.instance)
        with transaction.atomic():
            super().perform_update(serializer)
            self._record_document_history(
                previous_documents,
                self._document_snapshot(serializer.instance),
            )

    # -------------------------------------------------------------
    # RC / insurance document history
    # -------------------------------------------------------------

    @staticmethod
    def _file_name(value):
        return getattr(value, "name", None) or str(value or "") or None

    def _document_snapshot(self, vehicle):
        return {
            "vehicle_id": vehicle.unique_id,
            "vehicle_no": vehicle.vehicle_no,
            "rc": {
                "document_number": vehicle.vehicle_no,
                "expiry_date": vehicle.rc_expiry_date,
                "file": self._file_name(vehicle.rc_upload),
            },
            "insurance": {
                "document_number": vehicle.vehicle_insurance,
                "expiry_date": vehicle.insurance_expiry_date,
                "file": self._file_name(vehicle.vehicle_insurance_file),
            },
        }

    @staticmethod
    def _document_changed(previous, current, *, include_document_number=True):
        if include_document_number and previous["document_number"] != current["document_number"]:
            return True
        return previous["expiry_date"] != current["expiry_date"] or previous["file"] != current["file"]

    @staticmethod
    def _has_document_data(snapshot):
        return bool(
            snapshot["document_number"]
            or snapshot["expiry_date"]
            or snapshot["file"]
        )

    def _record_document_history(self, previous, current):
        actor_id, actor_name, actor_type = resolve_actor(getattr(self.request, "user", None))
        rows = []
        # RC's "number" is the vehicle_no itself, so a plate edit alone is
        # not an RC renewal — only its expiry/file count for RC.
        document_map = (
            ("rc", VehicleDocumentHistory.DocumentType.RC, False),
            ("insurance", VehicleDocumentHistory.DocumentType.INSURANCE, True),
        )

        for key, document_type, include_document_number in document_map:
            previous_doc = previous[key]
            current_doc = current[key]
            if not self._document_changed(
                previous_doc,
                current_doc,
                include_document_number=include_document_number,
            ):
                continue
            if not (self._has_document_data(previous_doc) or self._has_document_data(current_doc)):
                continue

            rows.append(
                VehicleDocumentHistory(
                    vehicle_id=current["vehicle_id"],
                    vehicle_no=current["vehicle_no"],
                    document_type=document_type,
                    previous_document_number=previous_doc["document_number"],
                    new_document_number=current_doc["document_number"],
                    previous_expiry_date=previous_doc["expiry_date"],
                    new_expiry_date=current_doc["expiry_date"],
                    previous_file=previous_doc["file"],
                    new_file=current_doc["file"],
                    changed_by_id=actor_id,
                    changed_by_name=actor_name,
                    changed_by_type=actor_type,
                )
            )

        if rows:
            VehicleDocumentHistory.objects.bulk_create(rows)

    @action(detail=True, methods=["get"], url_path="document-history")
    def document_history(self, request, unique_id=None):
        vehicle = self.get_object()
        queryset = VehicleDocumentHistory.objects.filter(vehicle_id=vehicle.unique_id)
        document_type = request.query_params.get("document_type")
        if document_type:
            queryset = queryset.filter(document_type=document_type.upper())
        serializer = VehicleDocumentHistorySerializer(queryset, many=True)
        return Response(serializer.data)

    # -------------------------------------------------------------
    # Bulk vehicle creation helpers
    # -------------------------------------------------------------

    def _find_vehicle_type(self, raw_value: str | None) -> VehicleTypeCreation | None:
        if not raw_value:
            return None

        value = str(raw_value).strip()
        return VehicleTypeCreation.objects.filter(
            is_deleted=False
        ).filter(
            Q(unique_id__iexact=value) | Q(vehicleType__iexact=value)
        ).first()

    def _find_fuel(self, raw_value: str | None) -> Fuel | None:
        if not raw_value:
            return None

        value = str(raw_value).strip()
        return Fuel.objects.filter(
            is_deleted=False
        ).filter(
            Q(unique_id__iexact=value) | Q(fuel_type__iexact=value)
        ).first()

    def _find_company(self, raw_value: str | None) -> Company | None:
        if not raw_value:
            return None

        value = str(raw_value).strip()
        return Company.objects.filter(
            is_deleted=False
        ).filter(
            Q(unique_id__iexact=value) | Q(name__iexact=value)
        ).first()

    def _find_project(self, company, raw_value: str | None) -> Project | None:
        if not raw_value:
            return None

        value = str(raw_value).strip()
        # company may be a model instance (superadmin branch) or a plain
        # uid string (company-user branch via self._company()).
        company_uid = company if isinstance(company, str) else getattr(company, "unique_id", company)
        return Project.objects.filter(
            is_deleted=False,
            company_id=company_uid
        ).filter(
            Q(unique_id__iexact=value) | Q(name__iexact=value)
        ).first()

    def _resolve_project_value(self, row: dict[str, str | None]) -> str | None:
        candidates = [
            row.get("project_id"),
            row.get("project_id_input"),
            row.get("project_unique_id"),
            self.request.headers.get(self.project_header),
            self.request.query_params.get("project"),
            self.request.data.get("project_id_input"),
            self.request.data.get("project_id"),
            self.request.data.get("project_unique_id"),
        ]

        for value in candidates:
            if value is None:
                continue

            trimmed = str(value).strip()
            if trimmed:
                return trimmed

        return None

    # =========================================================
    # ✅ BULK UPLOAD – VEHICLE CREATION
    # =========================================================

    @action(detail=False, methods=["post"], url_path="bulk-upload")
    def bulk_upload(self, request):
        file = request.FILES.get("file")

        if not file:
            return Response({"error": "CSV file is required"}, status=400)

        decoded_file = None
        try:
            decoded_file = file.read().decode("utf-8")
        except Exception as exc:
            return Response({"error": "Unable to decode CSV file", "detail": str(exc)}, status=400)

        io_string = io.StringIO(decoded_file)
        reader = csv.DictReader(io_string)
        rows = list(reader)

        success_count = 0
        errors: list[dict[str, object]] = []

        company_override = self.request.data.get("company_id") or self.request.data.get("company_id_input")
        project_override = self.request.data.get("project_id") or self.request.data.get("project_id_input")

        for index, row in enumerate(rows, start=1):
            vehicle_no = (row.get("vehicle_no") or "").strip()

            if not vehicle_no:
                errors.append({"row": index, "error": "vehicle_no is required"})
                continue

            vehicle_type = self._find_vehicle_type(row.get("vehicle_type"))
            if row.get("vehicle_type") and not vehicle_type:
                errors.append({"row": index, "error": f"Invalid vehicle_type: {row.get('vehicle_type')}"})
                continue

            fuel = self._find_fuel(row.get("fuel_type"))
            if row.get("fuel_type") and not fuel:
                errors.append({"row": index, "error": f"Invalid fuel_type: {row.get('fuel_type')}"})
                continue

            company_id_value = (row.get("company_id") or row.get("company_id_input") or company_override or "").strip()
            project_id_value = (row.get("project_id") or row.get("project_id_input") or project_override or "").strip()

            company = None
            if self._is_platform_super_admin():
                if not company_id_value:
                    errors.append({"row": index, "error": "company_id is required for superadmin"})
                    continue

                company = self._find_company(company_id_value)
                if not company:
                    errors.append({"row": index, "error": f"Invalid company_id: {company_id_value}"})
                    continue
            else:
                company = self._company()
                if not company:
                    errors.append({"row": index, "error": "Failed to resolve company context"})
                    continue

            project_unique_value = project_id_value or self._resolve_project_value(row)
            project = None
            if project_unique_value:
                project = self._find_project(company, project_unique_value)
                if not project:
                    errors.append({"row": index, "error": f"Invalid project_id: {project_unique_value}"})
                    continue
            else:
                if self._is_platform_super_admin():
                    errors.append({"row": index, "error": "project_id is required for superadmin"})
                    continue
                try:
                    project = self._project()
                except ValidationError as exc:
                    errors.append({"row": index, "error": exc.detail})
                    continue

            condition_value = (row.get("vehicle_condition") or "").strip().upper()
            if condition_value and condition_value not in VehicleCreation.ConditionChoices.values:
                allowed = ", ".join(VehicleCreation.ConditionChoices.values)
                errors.append({"row": index, "error": f"vehicle_condition must be one of: {allowed}"})
                continue

            payload = {
                "vehicle_no": vehicle_no,
                "vehicle_type_id": vehicle_type.unique_id if vehicle_type else None,
                "fuel_type_id": fuel.unique_id if fuel else None,
                "capacity": row.get("capacity") or None,
                "mileage_per_liter": row.get("mileage_per_liter") or None,
                "service_record": row.get("service_record") or None,
                "vehicle_insurance": row.get("vehicle_insurance") or None,
                "insurance_expiry_date": row.get("insurance_expiry_date") or None,
                "vehicle_condition": condition_value or None,
                "fuel_tank_capacity": row.get("fuel_tank_capacity") or None,
            }
            is_active_value = (row.get("is_active") or "").strip().lower()
            if is_active_value:
                payload["is_active"] = is_active_value in {"true", "1", "yes", "y"}

            # company/project may be model instances (superadmin branch) or
            # plain uid strings (company-user branch) — normalize to strings
            # for the CharField columns below.
            company_uid = company if isinstance(company, str) else getattr(company, "unique_id", company)
            project_uid = project if isinstance(project, str) else getattr(project, "unique_id", project)

            payload["company_id_input"] = company_uid
            if project_uid:
                payload["project_id_input"] = project_uid

            serializer = self.get_serializer(data=payload)

            if serializer.is_valid():
                serializer.save(company_id=company_uid, project_id=project_uid)
                success_count += 1
            else:
                errors.append({"row": index, "error": serializer.errors})

        return Response(bulk_upload_response(
            "Vehicle bulk upload completed",
            success_count,
            errors,
            file_name=getattr(file, "name", None),
            rows=rows,
        ))
