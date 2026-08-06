from rest_framework import serializers
from app.serializers.company_projects.tenancy import TenancyReadSerializerMixin
from app.models.waste_types.property import Property
from app.validators.unique_name_validator import unique_name_validator

class PropertySerializer(TenancyReadSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = Property
        fields = [
            "unique_id",
            "company_id",
            "company_name",
            "project_id",
            "project_name",
            "property_name",
            "is_active",
            "is_deleted",
            "created_by",
            "updated_by",
        ]
        read_only_fields = ["unique_id"]
        validators = []

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
            Model=Property,
            name_field="property_name",
            scope_fields=["company_id", "project_id"],
        )(self, attrs)
