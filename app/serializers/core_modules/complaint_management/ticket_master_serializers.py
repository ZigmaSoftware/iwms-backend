"""Master serializers for the ticketed complaint workflow.

Ported unchanged from the government backend's
`serializers/core_modules/complaint_management/master_serializers.py`
(import paths adapted to this project's model layout).
"""

from django.db.models import Max
from rest_framework import serializers

from app.models.core_modules.complaint_management import (
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
    default_priority_code = serializers.SerializerMethodField()
    default_department_name = serializers.SerializerMethodField()
    module_code = serializers.SerializerMethodField()
    module_name = serializers.SerializerMethodField()

    def get_default_priority_code(self, obj):
        return getattr(obj.default_priority, "priority_code", None)

    def get_default_department_name(self, obj):
        return getattr(obj.default_department, "department_name", None)

    def get_module_code(self, obj):
        return getattr(obj.module, "module_code", None)

    def get_module_name(self, obj):
        return getattr(obj.module, "module_name", None)

    class Meta:
        model = ComplaintCategory
        fields = "__all__"
        read_only_fields = ["unique_id", "sort_order"]


class ComplaintSubcategorySerializer(AutoSortOrderSerializerMixin, serializers.ModelSerializer):
    category_name = serializers.SerializerMethodField()
    category_code = serializers.SerializerMethodField()

    def get_category_name(self, obj):
        return getattr(obj.category, "category_name", None)

    def get_category_code(self, obj):
        return getattr(obj.category, "category_code", None)

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
    category_code = serializers.SerializerMethodField()
    category_name = serializers.SerializerMethodField()
    # A rule may target one sub-category or the whole category ("any"), so
    # these are nullable — the SLA list renders a blank as "All".
    subcategory_code = serializers.SerializerMethodField()
    subcategory_name = serializers.SerializerMethodField()
    priority_code = serializers.SerializerMethodField()
    source_code = serializers.SerializerMethodField()

    def get_category_code(self, obj):
        return getattr(obj.category, "category_code", None)

    def get_category_name(self, obj):
        return getattr(obj.category, "category_name", None)

    def get_subcategory_code(self, obj):
        return getattr(obj.subcategory, "subcategory_code", None)

    def get_subcategory_name(self, obj):
        return getattr(obj.subcategory, "subcategory_name", None)

    def get_priority_code(self, obj):
        return getattr(obj.priority, "priority_code", None)

    def get_source_code(self, obj):
        return getattr(obj.source, "source_code", None)
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
                sla_rule_id=rule.unique_id,
                level=row["level"],
                is_enabled=row.get("is_enabled", True),
                resolve_within_minutes=row["resolve_within_minutes"],
            )
