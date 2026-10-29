from rest_framework import serializers
from app.serializers.company_projects.tenancy import TenancyReadSerializerMixin
from app.models.masters.waste_masters.subproperty import SubProperty
from app.models.masters.waste_masters.property import Property
from app.utils.name_or_id_field import NameOrUniqueIdField
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project
from app.utils.related_prefetch import prefetching_list_serializer, related
from app.validators.unique_name_validator import unique_name_validator

RELATED_LOOKUPS = {
    "company": (Company, "company_id"),
    "project": (Project, "project_id"),
}


class SubPropertySerializer(TenancyReadSerializerMixin, serializers.ModelSerializer):
    created_by = serializers.CharField(source="created_by_id", read_only=True)
    updated_by = serializers.CharField(source="updated_by_id", read_only=True)

    # dropdown filtered only to active and not-deleted properties
    property_id = NameOrUniqueIdField(
        name_field="property_name",
        queryset=Property.objects.filter(is_active=True, is_deleted=False),
    )

    property_name = serializers.CharField(
        source="property_id.property_name",
        read_only=True
    )

    class Meta:
        model = SubProperty
        fields = [
            "unique_id",
            "company_id",
            "company_name",
            "project_id",
            "project_name",
            "property_id",
            "property_name",
            "sub_property_name",
            "is_active",
            "is_deleted",
            "created_by",
            "updated_by",
        ]
        read_only_fields = ["unique_id"]
        validators = []
        list_serializer_class = prefetching_list_serializer(RELATED_LOOKUPS)

    def get_company_name(self, obj):
        return getattr(related(obj, "company"), "name", None)

    def get_project_name(self, obj):
        return getattr(related(obj, "project"), "name", None)

    def validate(self, attrs):
        request = self.context.get("request")
        instance = self.instance

        if "company_id" not in attrs or attrs.get("company_id") is None:
            if instance:
                attrs["company_id"] = instance.company_id
            elif request:
                attrs["company_id"] = getattr(request.user, "company_id", None)

        if "project_id" not in attrs or attrs.get("project_id") is None:
            if instance:
                attrs["project_id"] = instance.project_id

        return unique_name_validator(
            Model=SubProperty,
            name_field="sub_property_name",
            scope_fields=["company_id", "project_id", "property_id"],
        )(self, attrs)
