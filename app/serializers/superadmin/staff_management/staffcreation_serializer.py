import re

from rest_framework import serializers
from app.models.superadmin.role_management.staffUserType import StaffUserType
from app.models.superadmin.role_management.contractorUserType import ContractorUserType
from app.models.superadmin.staff_management.department import Department
from app.models.superadmin.staff_management.designation import Designation
from app.models.superadmin_masters.project import Project
from app.serializers.company_projects.tenancy import TenancyReadSerializerMixin
from app.models.superadmin_masters.company import Company
from app.utils.name_or_id_field import NameOrUniqueIdField
from app.utils.related_prefetch import prefetching_list_serializer, related
from app.models.superadmin.screen_management.app_module import AppModule
from app.models.superadmin.staff_management.staff_access_configuration import StaffAccessConfiguration

from app.models.superadmin.staff_management.staffcreation import Staffcreation, StaffPersonalDetails

from app.utils.password_encryption import encrypt_password, decrypt_password


RELATED_LOOKUPS = {
    "company": (Company, "company_id"),
    "project": (Project, "project_id"),
    "staffusertype": (StaffUserType, "staffusertype_id"),
    "contractorusertype": (ContractorUserType, "contractorusertype_id"),
    "department_obj": (Department, "department_id"),
    "designation_obj": (Designation, "designation_id"),
}


class StaffcreationListSerializer(prefetching_list_serializer(RELATED_LOOKUPS)):
    """Also batches the `app_module` property (active access config -> its
    AppModule's surface_key), which is one query per row otherwise."""

    def to_representation(self, data):
        instances = list(data.all() if hasattr(data, "all") else data)
        staff_ids = {obj.staff_unique_id for obj in instances if obj.staff_unique_id}
        configs = {}
        if staff_ids:
            # Same filter/ordering as the property; keep the first per staff.
            for config in StaffAccessConfiguration.objects.filter(
                staff_id__in=staff_ids, is_active=True, is_deleted=False,
            ):
                configs.setdefault(config.staff_id, config)
        module_ids = {c.app_module_id for c in configs.values() if c.app_module_id}
        modules = (
            {m.unique_id: m for m in AppModule.objects.filter(unique_id__in=module_ids)}
            if module_ids else {}
        )
        for obj in instances:
            if not obj.staff_unique_id:
                continue
            config = configs.get(obj.staff_unique_id)
            module = modules.get(config.app_module_id) if config and config.app_module_id else None
            obj._app_module = (
                module.surface_key if module and module.is_active and not module.is_deleted else None
            )
        return super().to_representation(instances)


class StaffApprovalActionSerializer(serializers.Serializer):
    rejected_reason = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
    )


class StaffcreationSerializer(TenancyReadSerializerMixin, serializers.ModelSerializer):
    # --------------------------------------------------
    # Core identifiers
    # --------------------------------------------------
    unique_id = serializers.CharField(source="staff_unique_id",read_only=True)
    emp_id = serializers.CharField(read_only=True)
    app_module = serializers.SerializerMethodField()
    staffusertype_id = NameOrUniqueIdField(
    name_field="name",
    queryset=StaffUserType.objects.all(),
    required=False,
    allow_null=True
)
    password = serializers.CharField(
    required=False,
    allow_blank=True,
    allow_null=True,
)

    staffusertype_name = serializers.SerializerMethodField()

    contractorusertype_id = NameOrUniqueIdField(
        name_field="name",
        queryset=ContractorUserType.objects.all(),
        required=False,
        allow_null=True,
    )
    contractorusertype_name = serializers.SerializerMethodField()
    department_id = NameOrUniqueIdField(
        name_field="department_name",
        queryset=Department.objects.filter(is_deleted=False),
        required=False,
        allow_null=True,
    )
    designation_id = NameOrUniqueIdField(
        name_field="designation_name",
        queryset=Designation.objects.filter(is_deleted=False),
        scope_fields=["department_id"],
        required=False,
        allow_null=True,
    )
    project_id = NameOrUniqueIdField(
        name_field="name",
        queryset=Project.objects.filter(is_deleted=False),
        required=False,
        allow_null=True,
    )
    department_name = serializers.SerializerMethodField()
    department_code = serializers.SerializerMethodField()
    designation_name = serializers.SerializerMethodField()
    designation_group = serializers.SerializerMethodField()

    def get_staffusertype_name(self, obj):
        staffusertype = related(obj, "staffusertype")
        return staffusertype.name if staffusertype else None

    def get_contractorusertype_name(self, obj):
        contractorusertype = related(obj, "contractorusertype")
        return contractorusertype.name if contractorusertype else None

    def get_department_name(self, obj):
        department = related(obj, "department_obj")
        return department.department_name if department else None

    def get_department_code(self, obj):
        department = related(obj, "department_obj")
        return department.department_code if department else None

    def get_designation_name(self, obj):
        designation = related(obj, "designation_obj")
        return designation.designation_name if designation else None

    def get_designation_group(self, obj):
        designation = related(obj, "designation_obj")
        return designation.designation_group if designation else None

    # --------------------------------------------------
    #  Office-level: Driving licence
    # --------------------------------------------------
    driving_licence_no = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
    )
    driving_licence_file = serializers.FileField(
        required=False,
        allow_null=True,
    )

    # --------------------------------------------------
    # Personal details (flattened from StaffPersonalDetails)
    # --------------------------------------------------
    marital_status = serializers.CharField(
        source="personal_details.marital_status",
        required=False,
        allow_blank=True,
        allow_null=True,
    )
    dob = serializers.DateField(
        source="personal_details.dob",
        required=False,
        allow_null=True,
    )
    age = serializers.IntegerField(
        source="personal_details.age",
        required=False,
        allow_null=True,
        min_value=18,
        max_value=120,
    )
    blood_group = serializers.CharField(
        source="personal_details.blood_group",
        required=False,
        allow_blank=True,
        allow_null=True,
    )
    gender = serializers.CharField(
        source="personal_details.gender",
        required=False,
        allow_blank=True,
        allow_null=True,
    )
    physically_challenged = serializers.CharField(
        source="personal_details.physically_challenged",
        required=False,
        allow_blank=True,
        allow_null=True,
    )
    present_address = serializers.JSONField(
        source="personal_details.present_address",
        required=False,
        allow_null=True,
    )
    permanent_address = serializers.JSONField(
        source="personal_details.permanent_address",
        required=False,
        allow_null=True,
    )
    contact_mobile = serializers.CharField(
        source="personal_details.contact_mobile",
        required=False,
        allow_blank=True,
        allow_null=True,
    )
    contact_email = serializers.EmailField(
        source="personal_details.contact_email",
        required=False,
        allow_blank=True,
        allow_null=True,
    )

    username = serializers.CharField(
    required=False,
    allow_blank=True,
    allow_null=True
)

    def to_internal_value(self, data):
        # For multipart/form-data, empty string for nullable FK means "clear to null".
        # QueryDict is immutable so we work on a copy. Note: QueryDict.copy()
        # deep-copies values, which crashes on uploaded files (BufferedRandom
        # is not picklable) — so build a shallow clone that reuses the same
        # file objects instead. request.data itself is left untouched.
        nullable_fk_fields = ('project_id',)
        if hasattr(data, '_mutable'):
            if any(data.get(field) == '' for field in nullable_fk_fields):
                from django.http import QueryDict
                clone = QueryDict(mutable=True)
                for key, values in data.lists():
                    clone.setlist(key, list(values))
                for field in nullable_fk_fields:
                    if clone.get(field) == '':
                        clone[field] = None
                data = clone
        return super().to_internal_value(data)

    def validate_username(self, value):
        if not value:
            return value
        username_clean = value.strip()
        if not username_clean:
            return value
        qs = Staffcreation.objects.filter(username__iexact=username_clean, is_deleted=False)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("A staff member with this username already exists.")
        return username_clean

    def validate_contact_email(self, value):
        # Soft-delete aware: allow reuse of email from deleted staff.
        # StaffPersonalDetails has no is_deleted flag itself, so scope
        # through the parent staff row (staff__is_deleted=False).
        if not value:
            return value
        email_clean = value.strip()
        if not email_clean:
            return value
        qs = StaffPersonalDetails.objects.filter(
            contact_email__iexact=email_clean,
            staff__is_deleted=False,
        )
        if self.instance:
            qs = qs.exclude(staff__pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("A staff member with this email already exists.")
        return email_clean

    def validate_contact_mobile(self, value):
        # Soft-delete aware: allow reuse of mobile number from deleted staff.
        if not value:
            return value
        mobile_clean = value.strip()
        if not mobile_clean:
            return value
        qs = StaffPersonalDetails.objects.filter(
            contact_mobile=mobile_clean,
            staff__is_deleted=False,
        )
        if self.instance:
            qs = qs.exclude(staff__pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("A staff member with this mobile number already exists.")
        return mobile_clean

    def _validate_address_pincode(self, value):
        if not value:
            return value
        pincode = value.get("pincode") if isinstance(value, dict) else None
        if pincode not in (None, "") and not re.match(r"^\d{6}$", str(pincode)):
            raise serializers.ValidationError({"pincode": "Enter a valid 6-digit pincode."})
        return value

    def validate_present_address(self, value):
        return self._validate_address_pincode(value)

    def validate_permanent_address(self, value):
        return self._validate_address_pincode(value)

    user_type_id = serializers.SerializerMethodField()

    def get_user_type_id(self, obj):
        staffusertype = related(obj, "staffusertype")
        return staffusertype.usertype_id if staffusertype else None

    

    # --------------------------------------------------
    # Internal mapping for personal table
    # --------------------------------------------------
    personal_field_names = [
        "marital_status",
        "dob",
        "age",
        "blood_group",
        "gender",
        "physically_challenged",
        "present_address",
        "permanent_address",
        "contact_mobile",
        "contact_email",
    ]

    class Meta:
        model = Staffcreation
        fields = [
            "unique_id",
            "staff_id",
            "company_id",
            "company_name",
            "project_id",
            "project_name",
            "emp_id",
            "username",
            "password",
            # Which mobile app this staff member lands in. Read-only here:
            # the app is selected once, on the Staff Access Configuration,
            # and this reads back through it (see the `app_module` property
            # on StaffcreationOfficeDetails). Keeping a writable copy on the
            # staff record let the two disagree and strand the user in an
            # app they had no screens for.
            "app_module",
            "qr_code",

            # Office details
            "employee_name",
            "doj",
            "department",
            "designation",
            "department_id",
            "designation_id",
            "department_name",
            "department_code",
            "designation_name",
            "designation_group",
            "staff_head_id",
            "grade",
            "site_name",
            "staff_head",
            "employee_known",
            "photo",

            #  Driving licence
            "driving_licence_no",
            "driving_licence_expiry_date",
            "driving_licence_file",

            "active_status",
            "salary_type",

            # Personal details (flattened)
            "marital_status",
            "dob",
            "age",
            "blood_group",
            "gender",
            "physically_challenged",
            "present_address",
            "permanent_address",
            "contact_mobile",
            "contact_email",
            "user_type_id",
            "staffusertype_id",
            "staffusertype_name",
            "contractorusertype_id",
            "contractorusertype_name",
            "approval_status",
            "login_enabled",
            "approved_by",
            "approved_at",
            "rejected_reason",
            "failed_login_attempts",
            "last_login_at",
            "last_login_ip",

            "password_crt_date",
            "created_at",
            "updated_at",
            "is_active",
            "is_deleted",
        ]

        read_only_fields = [
            "unique_id",
            "staff_id",
            "app_module",
            "qr_code",
            "approval_status",
            "approved_by",
            "approved_at",
            "rejected_reason",
            "failed_login_attempts",
            "last_login_at",
            "last_login_ip",
            "password_crt_date",
            "created_at",
            "updated_at",
        ]
        list_serializer_class = StaffcreationListSerializer

    def get_app_module(self, obj):
        if hasattr(obj, "_app_module"):
            return obj._app_module
        return obj.app_module

    def get_company_name(self, obj):
        return getattr(related(obj, "company"), "name", None)

    def get_project_name(self, obj):
        return getattr(related(obj, "project"), "name", None)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['password'] = decrypt_password(instance.password or "")
        return data

    # --------------------------------------------------
    # Helpers
    # --------------------------------------------------
    def _pop_personal_data(self, validated_data):
        """
        Extract personal detail payload for StaffPersonalDetails
        """
        personal_data = validated_data.pop("personal_details", {})
        return {
            field: personal_data[field]
            for field in self.personal_field_names
            if field in personal_data
        }

    def _sync_user_type_id(self, validated_data):
        staffusertype_id = validated_data.get("staffusertype_id")
        if staffusertype_id:
            staffusertype = StaffUserType.objects.filter(unique_id=staffusertype_id).first()
            if staffusertype and staffusertype.usertype_id:
                validated_data["user_type_id"] = staffusertype.usertype_id

        contractorusertype_id = validated_data.get("contractorusertype_id")
        if contractorusertype_id:
            contractorusertype = ContractorUserType.objects.filter(unique_id=contractorusertype_id).first()
            if contractorusertype and contractorusertype.usertype_id:
                validated_data["user_type_id"] = contractorusertype.usertype_id

    # --------------------------------------------------
    # Create
    # --------------------------------------------------
    def create(self, validated_data):
        personal_data = self._pop_personal_data(validated_data)

        password = validated_data.get("password")
        if password:
            validated_data["password"] = encrypt_password(password)

        validated_data["is_active"] = True

        # When login_enabled is explicitly requested on creation, auto-approve so
        # the staff member can sign in immediately — the creator (a Company Admin
        # or superadmin) is the implicit approver.
        if validated_data.get("login_enabled"):
            validated_data.setdefault("approval_status", Staffcreation.APPROVAL_APPROVED)

        self._sync_user_type_id(validated_data)

        staff = Staffcreation.objects.create(**validated_data)

        StaffPersonalDetails.objects.create(
            staff=staff,
            staff_unique_id=staff.staff_unique_id,
            company_id=staff.company_id,
            project_id=staff.project_id,
            **personal_data,
        )

        return staff

    # --------------------------------------------------
    # Update
    # --------------------------------------------------
    def update(self, instance, validated_data):
        personal_data = self._pop_personal_data(validated_data)

        password = validated_data.get("password")
        if password:
            validated_data["password"] = encrypt_password(password)

        # Same rule as create(): turning login on for a still-PENDING staff
        # member auto-approves them — the editor is the implicit approver.
        # Without this, staff created with login off and enabled later stayed
        # PENDING forever, and PENDING staff are skipped by complaint
        # routing/escalation. Rejected/suspended staff are left as they are.
        if (
            validated_data.get("login_enabled")
            and instance.approval_status == Staffcreation.APPROVAL_PENDING
            and "approval_status" not in validated_data
        ):
            validated_data["approval_status"] = Staffcreation.APPROVAL_APPROVED

        self._sync_user_type_id(validated_data)

        staff = super().update(instance, validated_data)

        if personal_data:
            personal_instance, _ = StaffPersonalDetails.objects.get_or_create(
                staff=staff,
                defaults={
                    "staff_unique_id": staff.staff_unique_id,
                    "company_id": staff.company_id,
                    "project_id": staff.project_id,
                },
            )
            if not getattr(personal_instance, "company_id", None):
                personal_instance.company_id = staff.company_id
            if not getattr(personal_instance, "project_id", None):
                personal_instance.project_id = staff.project_id
            for attr, value in personal_data.items():
                setattr(personal_instance, attr, value)

            personal_instance.staff_unique_id = staff.staff_unique_id
            personal_instance.save()
        else:
            if hasattr(staff, "personal_details"):
                personal_details = staff.personal_details
                if personal_details.staff_unique_id != staff.staff_unique_id:
                    personal_details.staff_unique_id = staff.staff_unique_id
                    personal_details.save()

        return staff
