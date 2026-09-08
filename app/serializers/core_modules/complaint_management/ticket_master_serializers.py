"""Master serializers for the ticketed complaint workflow.

Ported unchanged from the government backend's
`serializers/core_modules/complaint_management/master_serializers.py`
(import paths adapted to this project's model layout).
"""

from django.db.models import Max
from rest_framework import serializers

from app.models.complaint_management import (
    ComplaintCategory,
    ComplaintLanguage,
    ComplaintModule,
    ComplaintPriority,
    ComplaintSlaEscalationLevel,
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


class ComplaintSlaEscalationLevelSerializer(serializers.ModelSerializer):
    class Meta:
        model = ComplaintSlaEscalationLevel
        fields = ["unique_id", "level", "is_enabled", "resolve_within_minutes"]
        read_only_fields = ["unique_id"]


class ComplaintSlaRuleSerializer(serializers.ModelSerializer):
    category_code = serializers.CharField(source="category.category_code", read_only=True)
    category_name = serializers.CharField(source="category.category_name", read_only=True)
    # A rule may target one sub-category or the whole category ("any"), so
    # these are nullable — the SLA list renders a blank as "All".
    subcategory_code = serializers.CharField(source="subcategory.subcategory_code", read_only=True)
    subcategory_name = serializers.CharField(source="subcategory.subcategory_name", read_only=True)
    priority_code = serializers.CharField(source="priority.priority_code", read_only=True)
    source_code = serializers.CharField(source="source.source_code", read_only=True)
    # Per-hierarchy-level resolve windows (level 0 = first assignee, level 1 =
    # one hop up, ...). Written wholesale on every save: the incoming list
    # replaces whatever rows existed before, same as how the ticket
    # serializer's `extra_details` are handled.
    escalation_levels = ComplaintSlaEscalationLevelSerializer(many=True, required=False)

    class Meta:
        model = ComplaintSlaRule
        fields = "__all__"
        read_only_fields = ["unique_id"]

    def create(self, validated_data):
        levels = validated_data.pop("escalation_levels", None)
        rule = super().create(validated_data)
        self._save_escalation_levels(rule, levels)
        return rule

    def update(self, instance, validated_data):
        levels = validated_data.pop("escalation_levels", None)
        rule = super().update(instance, validated_data)
        self._save_escalation_levels(rule, levels)
        return rule

    def _save_escalation_levels(self, rule, levels):
        if levels is None:
            return
        rule.escalation_levels.filter(is_deleted=False).update(is_deleted=True, is_active=False)
        for row in levels:
            ComplaintSlaEscalationLevel.objects.create(
                sla_rule=rule,
                level=row["level"],
                is_enabled=row.get("is_enabled", True),
                resolve_within_minutes=row["resolve_within_minutes"],
            )
