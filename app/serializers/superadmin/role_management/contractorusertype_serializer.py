from rest_framework import serializers
from app.serializers.company_projects.tenancy import TenancyReadSerializerMixin
from app.models.role_assigns.contractorUserType import ContractorUserType
from app.models.role_assigns.userType import UserType
from app.utils.name_or_id_field import NameOrUniqueIdField
from app.validators.unique_name_validator import unique_name_validator


def _resolve_usertype(value):
    if not value:
        return None
    if hasattr(value, "unique_id"):
        return value
    return (
        UserType.objects.filter(unique_id=value).first()
        or UserType.objects.filter(name__iexact=str(value).strip()).first()
    )


class ContractorUserTypeSerializer(TenancyReadSerializerMixin, serializers.ModelSerializer):
    usertype_id = NameOrUniqueIdField(
        queryset=UserType.objects.filter(is_deleted=False),
        name_field="name",
        required=False,
        allow_null=True,
    )
    usertype_name = serializers.SerializerMethodField()

    class Meta:
        model = ContractorUserType
        fields = "__all__"
        read_only_fields = ["unique_id"]
        validators = []

    def get_usertype_name(self, obj):
        usertype = _resolve_usertype(obj.usertype_id)
        return usertype.name if usertype else None

    def validate_usertype_id(self, usertype_id):
        """Only allow ContractorUserType if UserType is 'contractor'."""
        usertype_obj = _resolve_usertype(usertype_id)

        if not usertype_obj:
            raise serializers.ValidationError("Invalid UserType.")

        if usertype_obj.is_deleted:
            raise serializers.ValidationError("Selected UserType is deleted.")

        if not usertype_obj.is_active:
            raise serializers.ValidationError("Selected UserType is inactive.")

        if usertype_obj.name.lower().strip() != "contractor":
            raise serializers.ValidationError(
                "Contractor User Types can only be mapped to UserType = 'contractor'."
            )

        return usertype_obj.unique_id

    def to_representation(self, instance):
        data = super().to_representation(instance)
        usertype = _resolve_usertype(instance.usertype_id)
        if usertype:
            data["usertype_id"] = usertype.unique_id
            data["usertype_name"] = usertype.name
        data["name"] = instance.get_name_display()
        return data

    def validate(self, attrs):
        if self.instance and "name" not in attrs:
            return attrs

        return unique_name_validator(
            Model=ContractorUserType,
            name_field="name",
        )(self, attrs)
