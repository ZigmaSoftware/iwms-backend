import re

from django.db import models
from rest_framework.filters import BaseFilterBackend, OrderingFilter, SearchFilter


RESERVED_QUERY_PARAMETERS = {
    "page",
    "limit",
    "offset",
    "page_size",
    "search",
    "ordering",
    "format",
    "company_id",
    "company_unique_id",
    "project_id",
    "project_unique_id",
    "project",
}


def _snake_case(value):
    return re.sub(r"(?<!^)(?=[A-Z])", "_", value).lower()


class ModelFieldQueryFilter(BaseFilterBackend):
    """Apply safe column filters sent by lazy data tables."""

    def filter_queryset(self, request, queryset, view):
        model_fields = {
            field.name: field for field in queryset.model._meta.concrete_fields
        }
        serializer_fields = view.get_serializer().fields

        for raw_name, value in request.query_params.items():
            if raw_name in RESERVED_QUERY_PARAMETERS or value in ("", None):
                continue

            name = _snake_case(raw_name)
            serializer_field = serializer_fields.get(raw_name) or serializer_fields.get(
                name
            )
            source = getattr(serializer_field, "source", None)
            if source and source != "*" and "." not in source:
                name = source

            field = model_fields.get(name)
            if field is None:
                continue

            if isinstance(field, (models.CharField, models.TextField)):
                queryset = queryset.filter(**{f"{name}__icontains": value})
            elif isinstance(field, models.BooleanField):
                normalized = str(value).strip().lower()
                if normalized in {"true", "1", "yes"}:
                    queryset = queryset.filter(**{name: True})
                elif normalized in {"false", "0", "no"}:
                    queryset = queryset.filter(**{name: False})
            else:
                queryset = queryset.filter(**{name: value})

        return queryset


class ModelFieldSearchFilter(SearchFilter):
    """Use declared search fields, or infer safe text fields from the model."""

    def get_search_fields(self, view, request):
        declared_fields = super().get_search_fields(view, request)
        if declared_fields:
            return declared_fields

        queryset = view.get_queryset()
        return [
            field.name
            for field in queryset.model._meta.concrete_fields
            if isinstance(field, (models.CharField, models.TextField))
        ]


class SerializerOrderingFilter(OrderingFilter):
    """DRF ordering with serializer fields as the safe default allow-list."""
