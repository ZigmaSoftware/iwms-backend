"""Master serializers for the ticketed complaint workflow.

Ported unchanged from the government backend's
`serializers/core_modules/complaint_management/master_serializers.py`
(import paths adapted to this project's model layout).
"""

from django.db.models import Max
from rest_framework import serializers

from app.models.superadmin.staff_management.department import Department

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
from app.utils.related_prefetch import prefetching_list_serializer, related

CATEGORY_LOOKUPS = {
    "default_priority": (ComplaintPriority, "default_priority_id"),
    "default_department": (Department, "default_department_id"),
    "module": (ComplaintModule, "module_id"),
}
SUBCATEGORY_LOOKUPS = {
    "category": (ComplaintCategory, "category_id"),
}
SLA_RULE_LOOKUPS = {
    "category": (ComplaintCategory, "category_id"),
    "subcategory": (ComplaintSubcategory, "subcategory_id"),
    "priority": (ComplaintPriority, "priority_id"),
    "source": (ComplaintSource, "source_id"),
}


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
        return getattr(related(obj, "default_priority"), "priority_code", None)

    def get_default_department_name(self, obj):
        return getattr(related(obj, "default_department"), "department_name", None)

    def get_module_code(self, obj):
        return getattr(related(obj, "module"), "module_code", None)

    def get_module_name(self, obj):
        return getattr(related(obj, "module"), "module_name", None)

    class Meta:
        model = ComplaintCategory
        fields = "__all__"
        list_serializer_class = prefetching_list_serializer(CATEGORY_LOOKUPS)
        read_only_fields = ["unique_id", "sort_order"]


class ComplaintSubcategorySerializer(AutoSortOrderSerializerMixin, serializers.ModelSerializer):
    category_name = serializers.SerializerMethodField()
    category_code = serializers.SerializerMethodField()

    def get_category_name(self, obj):
        return getattr(related(obj, "category"), "category_name", None)

    def get_category_code(self, obj):
        return getattr(related(obj, "category"), "category_code", None)

    class Meta:
        model = ComplaintSubcategory
        fields = "__all__"
        list_serializer_class = prefetching_list_serializer(SUBCATEGORY_LOOKUPS)
        read_only_fields = ["unique_id", "sort_order"]


class ComplaintSlaEscalationLevelListSerializer(serializers.ListSerializer):
    def get_attribute(self, instance):
        # Batched by ComplaintSlaRuleListSerializer; else the rule's property.
        cached = getattr(instance, "_escalation_levels", None)
        return cached if cached is not None else super().get_attribute(instance)


class ComplaintSlaEscalationLevelSerializer(serializers.ModelSerializer):
    class Meta:
        model = ComplaintSlaEscalationLevel
        fields = ["unique_id", "level", "resolve_within_minutes"]
        list_serializer_class = ComplaintSlaEscalationLevelListSerializer
        read_only_fields = ["unique_id"]

    def validate_resolve_within_minutes(self, value):
        if value is None or value <= 0:
            raise serializers.ValidationError("Must be greater than 0.")
        return value


class ComplaintSlaRuleListSerializer(prefetching_list_serializer(SLA_RULE_LOOKUPS)):
    def to_representation(self, data):
        instances = list(data.all() if hasattr(data, "all") else data)
        # Same filter/order as ComplaintSlaRule.escalation_levels.
        levels = {}
        for row in ComplaintSlaEscalationLevel.objects.filter(
            sla_rule_id__in=[obj.unique_id for obj in instances], is_deleted=False
        ).order_by("level"):
            levels.setdefault(row.sla_rule_id, []).append(row)
        for obj in instances:
            obj._escalation_levels = levels.get(obj.unique_id, [])
        return super().to_representation(instances)


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
        return getattr(related(obj, "category"), "category_code", None)

    def get_category_name(self, obj):
        return getattr(related(obj, "category"), "category_name", None)

    def get_subcategory_code(self, obj):
        return getattr(related(obj, "subcategory"), "subcategory_code", None)

    def get_subcategory_name(self, obj):
        return getattr(related(obj, "subcategory"), "subcategory_name", None)

    def get_priority_code(self, obj):
        return getattr(related(obj, "priority"), "priority_code", None)

    def get_source_code(self, obj):
        return getattr(related(obj, "source"), "source_code", None)
    # Resolve window per escalation-enabled level of the project's staff
    # hierarchy (which levels take part is set on ProjectStaffHierarchy, not
    # here). Written wholesale on every save: the incoming list replaces
    # whatever rows existed before, same as how the ticket serializer's
    # `extra_details` are handled.
    escalation_levels = ComplaintSlaEscalationLevelSerializer(many=True, required=False)

    class Meta:
        model = ComplaintSlaRule
        fields = "__all__"
        list_serializer_class = ComplaintSlaRuleListSerializer
        read_only_fields = ["unique_id"]

    def validate(self, attrs):
        # A rule only ever matches tickets of its own project, so its
        # category/subcategory must be that project's rows too — otherwise
        # it saves fine and then silently never applies.
        instance = getattr(self, "instance", None)

        def current(field):
            if field in attrs:
                return attrs[field]
            return getattr(instance, field, None)

        company_id = current("company_id")
        project_id = current("project_id")
        category_id = current("category_id")
        subcategory_id = current("subcategory_id")

        def out_of_scope(row):
            return row is not None and (
                (company_id and row.company_id != company_id)
                or (project_id and row.project_id != project_id)
            )

        if category_id:
            category = ComplaintCategory.objects.filter(unique_id=category_id).first()
            if out_of_scope(category):
                raise serializers.ValidationError(
                    {"category_id": "This category belongs to a different company/project."}
                )
        if subcategory_id:
            subcategory = ComplaintSubcategory.objects.filter(unique_id=subcategory_id).first()
            if out_of_scope(subcategory):
                raise serializers.ValidationError(
                    {"subcategory_id": "This sub-category belongs to a different company/project."}
                )
            if subcategory and category_id and subcategory.category_id != category_id:
                raise serializers.ValidationError(
                    {"subcategory_id": "This sub-category does not belong to the selected category."}
                )
        return attrs

    def validate_escalation_levels(self, value):
        levels = [row["level"] for row in value]
        if len(levels) != len(set(levels)):
            raise serializers.ValidationError("Each hierarchy level can appear only once.")
        return value

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
                resolve_within_minutes=row["resolve_within_minutes"],
            )
