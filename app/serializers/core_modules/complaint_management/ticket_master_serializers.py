"""Master serializers for the ticketed complaint workflow.

Ported unchanged from the government backend's
`serializers/core_modules/complaint_management/master_serializers.py`
(import paths adapted to this project's model layout).
"""

from django.db.models import Max
from rest_framework import serializers

from app.models.complaint_management import (
    ComplaintCategory,
    ComplaintDepartmentMember,
    ComplaintLanguage,
    ComplaintModule,
    ComplaintPriority,
    ComplaintSlaRule,
    ComplaintSource,
    ComplaintStatus,
    ComplaintSubcategory,
)


class AutoSortOrderSerializerMixin:
    def create(self, validated_data):
        if "sort_order" not in validated_data:
            max_order = self.Meta.model.objects.aggregate(max_order=Max("sort_order"))["max_order"] or 0
            validated_data["sort_order"] = max_order + 1
        return super().create(validated_data)


class ComplaintSourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = ComplaintSource
        fields = "__all__"
        read_only_fields = ["unique_id"]


class ComplaintLanguageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ComplaintLanguage
        fields = "__all__"
        read_only_fields = ["unique_id"]


class ComplaintPrioritySerializer(AutoSortOrderSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = ComplaintPriority
        fields = "__all__"
        read_only_fields = ["unique_id", "sort_order"]


class ComplaintStatusSerializer(AutoSortOrderSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = ComplaintStatus
        fields = "__all__"
        read_only_fields = ["unique_id", "sort_order"]


class ComplaintDepartmentMemberSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source="department.department_name", read_only=True)
    staff_name = serializers.CharField(source="staff.employee_name", read_only=True)
    open_ticket_count = serializers.SerializerMethodField()

    class Meta:
        model = ComplaintDepartmentMember
        fields = "__all__"
        read_only_fields = ["unique_id"]

    def get_open_ticket_count(self, obj):
        from app.services.complaint_ticket_routing import CLOSED_STATUS_CODES

        return (
            obj.staff.assigned_complaint_tickets_staff.filter(is_deleted=False)
            .exclude(status__status_code__in=CLOSED_STATUS_CODES)
            .count()
        )


class ComplaintModuleSerializer(AutoSortOrderSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = ComplaintModule
        fields = "__all__"
        read_only_fields = ["unique_id", "sort_order"]


class ComplaintCategorySerializer(AutoSortOrderSerializerMixin, serializers.ModelSerializer):
    default_priority_code = serializers.CharField(source="default_priority.priority_code", read_only=True)
    default_department_name = serializers.CharField(source="default_department.department_name", read_only=True)
    module_code = serializers.CharField(source="module.module_code", read_only=True)
    module_name = serializers.CharField(source="module.module_name", read_only=True)

    class Meta:
        model = ComplaintCategory
        fields = "__all__"
        read_only_fields = ["unique_id", "sort_order"]


class ComplaintSubcategorySerializer(AutoSortOrderSerializerMixin, serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.category_name", read_only=True)
    category_code = serializers.CharField(source="category.category_code", read_only=True)

    class Meta:
        model = ComplaintSubcategory
        fields = "__all__"
        read_only_fields = ["unique_id", "sort_order"]


class ComplaintSlaRuleSerializer(serializers.ModelSerializer):
    category_code = serializers.CharField(source="category.category_code", read_only=True)
    category_name = serializers.CharField(source="category.category_name", read_only=True)
    # A rule may target one sub-category or the whole category ("any"), so
    # these are nullable — the SLA list renders a blank as "All".
    subcategory_code = serializers.CharField(source="subcategory.subcategory_code", read_only=True)
    subcategory_name = serializers.CharField(source="subcategory.subcategory_name", read_only=True)
    priority_code = serializers.CharField(source="priority.priority_code", read_only=True)
    source_code = serializers.CharField(source="source.source_code", read_only=True)

    class Meta:
        model = ComplaintSlaRule
        fields = "__all__"
        read_only_fields = ["unique_id"]
