# from rest_framework import serializers
# from app.serializers.company_projects.tenancy import TenancyReadSerializerMixin

# from app.models.user_creations.stafftemplate import StaffTemplate
# from app.models.user_creations.staffcreation import Staffcreation
# from app.serializers.user_creations.user_serializer import UniqueIdOrPkField


# # =========================
# # HELPER FIELDS
# # =========================

# class CommaSeparatedListField(serializers.ListField):
#     def to_internal_value(self, data):
#         if isinstance(data, str):
#             data = [item.strip() for item in data.split(",") if item.strip()]
#         elif isinstance(data, (list, tuple)):
#             normalized = []
#             for item in data:
#                 if item in ("", None):
#                     continue
#                 if isinstance(item, str):
#                     normalized.extend([part.strip() for part in item.split(",") if part.strip()])
#                 else:
#                     normalized.append(item)
#             data = normalized
#         return super().to_internal_value(data)

#     def to_representation(self, value):
#         return value or []


# class BlankableUniqueIdField(UniqueIdOrPkField):
#     def to_internal_value(self, data):
#         if data in ("", None):
#             return None
#         return super().to_internal_value(data)


# # =========================
# # MAIN SERIALIZER
# # =========================

# class StaffTemplateSerializer(TenancyReadSerializerMixin, serializers.ModelSerializer):

#     # ================= IDs =================
#     driver_id = UniqueIdOrPkField(
#         slug_field="staff_unique_id",
#         queryset=Staffcreation.objects.filter(is_deleted=False),
#     )
#     operator_id = UniqueIdOrPkField(
#         slug_field="staff_unique_id",
#         queryset=Staffcreation.objects.filter(is_deleted=False),
#     )

#     created_by = BlankableUniqueIdField(
#         slug_field="staff_unique_id",
#         queryset=Staffcreation.objects.filter(is_deleted=False),
#         required=False,
#     )
#     updated_by = BlankableUniqueIdField(
#         slug_field="staff_unique_id",
#         queryset=Staffcreation.objects.filter(is_deleted=False),
#         required=False,
#     )
#     approved_by = BlankableUniqueIdField(
#         slug_field="staff_unique_id",
#         queryset=Staffcreation.objects.filter(is_deleted=False),
#         required=False,
#         allow_null=True,
#     )

#     # ================= NAMES (NO METHOD FIELD) =================
#     driver_name = serializers.CharField(
#         source="driver_id.employee_name",
#         read_only=True
#     )
#     operator_name = serializers.CharField(
#         source="operator_id.employee_name",
#         read_only=True
#     )
#     created_by_name = serializers.CharField(
#         source="created_by.employee_name",
#         read_only=True
#     )
#     updated_by_name = serializers.CharField(
#         source="updated_by.employee_name",
#         read_only=True
#     )
#     approved_by_name = serializers.CharField(
#         source="approved_by.employee_name",
#         read_only=True
#     )

#     # ================= ROLE =================
#     driver_role = serializers.CharField(
#         source="driver_id.staffusertype_id.name",
#         read_only=True
#     )
#     operator_role = serializers.CharField(
#         source="operator_id.staffusertype_id.name",
#         read_only=True
#     )

#     # ================= EXTRA =================
#     extra_operator_id = CommaSeparatedListField(
#         child=serializers.CharField(),
#         required=False,
#         allow_empty=True
#     )

#     display_code = serializers.CharField(read_only=True)

#     staffusertype_name = serializers.CharField(
#         source="staffusertype_id.name",
#         read_only=True
#     )

#     # ================= META =================
#     class Meta:
#         model = StaffTemplate
#         fields = [
#             "unique_id",
#             "company_id",
#             "company_name",
#             "project_id",
#             "project_name",

#             "display_code",

#             "driver_id",
#             "driver_name",
#             "driver_role",

#             "operator_id",
#             "operator_name",
#             "operator_role",

#             "extra_operator_id",

#             "staffusertype_name",

#             "created_by",
#             # "created_by_name",

#             "updated_by",
#             # "updated_by_name",

#             "approved_by",
#             "approved_by_name",

#             "status",
#             "approval_status",

#             "created_at",
#             "updated_at",
#         ]

#         read_only_fields = [
#             "unique_id",
#             "display_code",
#             "created_at",
#             "updated_at",
#             "driver_name",
#             "operator_name",
#             "driver_role",
#             "operator_role",
#             "created_by_name",
#             "updated_by_name",
#             "approved_by_name",
#         ]

#     # ================= VALIDATION =================
#     def validate(self, attrs):
#         instance = getattr(self, "instance", None)

#         def resolve(field):
#             if field in attrs:
#                 return attrs.get(field)
#             return getattr(instance, field) if instance else None

#         driver = resolve("driver_id")
#         operator = resolve("operator_id")

#         # ❌ same user
#         if driver and operator and driver.staff_unique_id == operator.staff_unique_id:
#             raise serializers.ValidationError({
#                 "operator_id": "Driver and operator must be different"
#             })

#         # ✅ role validation
#         def check_role(user, expected, field):
#             if not user or not user.staffusertype_id:
#                 return
#             actual = user.staffusertype_id.name.lower()
#             if actual != expected:
#                 raise serializers.ValidationError({
#                     field: f"Expected '{expected}', got '{actual}'"
#                 })

#         check_role(driver, "driver", "driver_id")
#         check_role(operator, "operator", "operator_id")

#         return attrs





from rest_framework import serializers
from app.serializers.company_projects.tenancy import TenancyReadSerializerMixin
from app.models.user_creations.stafftemplate import StaffTemplate
from app.models.user_creations.staffcreation import Staffcreation
from app.serializers.user_creations.user_serializer import UniqueIdOrPkField
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project


class CommaSeparatedListField(serializers.ListField):
    def to_internal_value(self, data):
        if isinstance(data, str):
            data = [x.strip() for x in data.split(",") if x.strip()]
        return super().to_internal_value(data)


class StaffTemplateSerializer(TenancyReadSerializerMixin, serializers.ModelSerializer):

    driver_id = UniqueIdOrPkField(
        slug_field="staff_unique_id",
        queryset=Staffcreation.objects.filter(is_deleted=False)
    )

    operator_id = UniqueIdOrPkField(
        slug_field="staff_unique_id",
        queryset=Staffcreation.objects.filter(is_deleted=False)
    )

    company_id = serializers.PrimaryKeyRelatedField(
        queryset=Company.objects.all()
    )

    project_id = serializers.PrimaryKeyRelatedField(
        queryset=Project.objects.all()
    )

    # ✅ FROM BASEMASTER (ACCOUNT)
    created_by = serializers.CharField(
        source="created_by.account_id",
        read_only=True
    )

    updated_by = serializers.CharField(
        source="updated_by.account_id",
        read_only=True
    )

    approved_by = UniqueIdOrPkField(
        slug_field="staff_unique_id",
        queryset=Staffcreation.objects.filter(is_deleted=False),
        required=False,
        allow_null=True
    )

    driver_name = serializers.CharField(source="driver_id.employee_name", read_only=True)
    operator_name = serializers.CharField(source="operator_id.employee_name", read_only=True)
    approved_by_name = serializers.CharField(source="approved_by.employee_name", read_only=True)

    extra_operator_id = CommaSeparatedListField(
        child=serializers.CharField(),
        required=False
    )

    staffusertype_name = serializers.CharField(
        source="staffusertype_id.name",
        read_only=True
    )

    class Meta:
        model = StaffTemplate
        fields = [
            "unique_id",
            "company_id",
            "company_name",
            "project_id",
            "project_name",

            "display_code",

            "driver_id",
            "driver_name",
            # "driver_role",

            "operator_id",
            "operator_name",
            # "operator_role",

            "extra_operator_id",

            "staffusertype_name",

            "created_by",
            

            "updated_by",
        

            "approved_by",
            "approved_by_name",

            "status",
            "approval_status",

            "created_at",
            "updated_at",
            "is_active",
            "is_deleted",
        ]

        read_only_fields = [
            "unique_id",
            "display_code",
            "created_at",
            "updated_at",
            "driver_name",
            "operator_name",
            "driver_role",
            "operator_role",
            "created_by_name",
            "updated_by_name",
            "approved_by_name",
        ]

    def validate_approved_by(self, value):
        if self.instance and self.instance.approved_by:
            raise serializers.ValidationError("Approved by cannot be modified")
        return value