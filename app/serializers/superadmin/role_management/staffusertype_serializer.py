from rest_framework import serializers
from app.serializers.company_projects.tenancy import TenancyReadSerializerMixin
from app.models.superadmin.role_management.staffUserType import StaffUserType
from app.models.superadmin.role_management.userType import UserType
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project
from app.utils.name_or_id_field import NameOrUniqueIdField
from app.validators.unique_name_validator import unique_name_validator
from app.utils.related_prefetch import prefetching_list_serializer, related

RELATED_LOOKUPS = {
    "company": (Company, "company_id"),
    "project": (Project, "project_id"),
    "usertype": (UserType, "usertype_id"),
}


def _resolve_usertype(value):
    if not value:
        return None
    if hasattr(value, "unique_id"):
        return value
    return (
        UserType.objects.filter(unique_id=value).first()
        or UserType.objects.filter(name__iexact=str(value).strip()).first()
    )


class StaffUserTypeSerializer(TenancyReadSerializerMixin, serializers.ModelSerializer):
    usertype_id = NameOrUniqueIdField(
        queryset=UserType.objects.filter(is_deleted=False),
        name_field="name",
        required=False,
        allow_null=True,
    )
    usertype_name = serializers.SerializerMethodField()

    class Meta:
        model = StaffUserType
        fields = "__all__"
        read_only_fields = ["unique_id"]
        validators = []
        list_serializer_class = prefetching_list_serializer(RELATED_LOOKUPS)

    def get_company_name(self, obj):
        return getattr(related(obj, "company"), "name", None)

    def get_project_name(self, obj):
        return getattr(related(obj, "project"), "name", None)

    def _usertype(self, obj):
        # Prefetched by unique_id when listed; otherwise (or on a miss) the
        # unique_id-then-name lookup. Memoized: both readers below need it.
        cache = getattr(obj, "_related_cache", None)
        if cache is None:
            cache = obj._related_cache = {}
        if cache.get("usertype") is None:
            cache["usertype"] = _resolve_usertype(obj.usertype_id)
        return cache["usertype"]

    def get_usertype_name(self, obj):
        usertype = self._usertype(obj)
        return usertype.name if usertype else None

    def to_representation(self, instance):
        data = super().to_representation(instance)
        usertype = self._usertype(instance)
        if usertype:
            data["usertype_id"] = usertype.unique_id
            data["usertype_name"] = usertype.name
        return data

    def validate_usertype_id(self, usertype_id):
        """Only allow StaffUserType if UserType is 'staff'."""
        usertype_obj = _resolve_usertype(usertype_id)

        if not usertype_obj:
            raise serializers.ValidationError("Invalid UserType.")

        if usertype_obj.is_deleted:
            raise serializers.ValidationError("Selected UserType is deleted.")

        if not usertype_obj.is_active:
            raise serializers.ValidationError("Selected UserType is inactive.")

        if usertype_obj.name.lower().strip() != "staff":
            raise serializers.ValidationError(
                "Staff User Types can only be mapped to UserType = 'staff'."
            )

        return usertype_obj.unique_id
    

    def validate(self, attrs):
        if self.instance and "name" not in attrs:
            return attrs

        return unique_name_validator(
            Model=StaffUserType,
            name_field="name",
        )(self, attrs)
