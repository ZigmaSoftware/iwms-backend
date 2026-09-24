from rest_framework import serializers

from app.models.superadmin.common_masters.country import Country
from app.models.superadmin.common_masters.state import State
from app.models.masters.customer_masters.customercreation import CustomerCreation
from app.models.masters.city import City
from app.models.masters.district import District
from app.models.masters.panchayat import Panchayat
from app.models.masters.ward import Ward
from app.models.masters.zone import Zone
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project
from app.models.masters.waste_masters.property import Property
from app.models.masters.waste_masters.subproperty import SubProperty
from app.models.waste_collection_bluetooth.waste_collection_bluetooth import WasteType
from app.serializers.company_projects.tenancy import TenancyReadSerializerMixin
from app.utils.name_or_id_field import NameOrUniqueIdField
from app.validators.unique_name_validator import unique_name_validator

from app.utils.password_encryption import encrypt_password, decrypt_password

RESIDENTIAL_WASTE_TYPE_KEYWORDS = ("dry", "wet", "mixed", "sanitary")
RESIDENTIAL_PROPERTY_KEYWORDS = ("residential", "residental")
RESIDENTIAL_SUB_PROPERTY_KEYWORDS = (
    "residential",
    "residental",
    "individual",
    "house",
    "apartment",
    "villa",
    "townhouse",
)


class CustomerCreationSerializer(TenancyReadSerializerMixin, serializers.ModelSerializer):
    company_id = NameOrUniqueIdField(
        queryset=Company.objects.all(),
        name_field="name",
        required=False,
        allow_null=True,
        )

    project_id = NameOrUniqueIdField(
        queryset=Project.objects.all(),
        name_field="name",
        scope_fields=["company_id"],
        required=False,
        allow_null=True,
    )
    ward_id = NameOrUniqueIdField(
        queryset=Ward.objects.all(),
        name_field="ward_name",
        required=False,
        allow_null=True,
    )
    zone_id = NameOrUniqueIdField(
        queryset=Zone.objects.all(),
        name_field="zone_name",
        required=False,
        allow_null=True,
    )
    city_id = NameOrUniqueIdField(
        queryset=City.objects.all(),
        name_field="name",
        required=False,
        allow_null=True,
    )
    district_id = NameOrUniqueIdField(
        queryset=District.objects.all(),
        name_field="name",
        required=False,
        allow_null=True,
    )
    state_id = NameOrUniqueIdField(
        queryset=State.objects.all(),
        name_field="name",
        required=False,
        allow_null=True,
    )
    country_id = NameOrUniqueIdField(
        queryset=Country.objects.all(),
        name_field="name",
        required=False,
        allow_null=True,
    )
    panchayat_id = NameOrUniqueIdField(
        queryset=Panchayat.objects.all(),
        name_field="panchayat_name",
        required=False,
        allow_null=True,
    )
    property_id = NameOrUniqueIdField(
        queryset=Property.objects.all(),
        name_field="property_name",
        required=False,
        allow_null=True,
    )
    sub_property_id = NameOrUniqueIdField(
        queryset=SubProperty.objects.all(),
        name_field="sub_property_name",
        scope_fields=["property_id"],
        required=False,
        allow_null=True,
    )
    waste_type_ids = NameOrUniqueIdField(
        queryset=WasteType.objects.filter(is_deleted=False),
        name_field="waste_type_name",
        scope_fields=["project_id", "company_id"],
        many=True,
        required=False,
        write_only=True,
    )
    waste_types = serializers.SerializerMethodField(read_only=True)
    # Local-body emblem for the project, printed on the customer QR sticker.
    project_logo = serializers.SerializerMethodField(read_only=True)
    panchayat_name = serializers.CharField(source="panchayat.panchayat_name", read_only=True, default=None)
    ward_name = serializers.CharField(source="ward.ward_name", read_only=True, default=None)
    zone_name = serializers.CharField(source="zone.zone_name", read_only=True, default=None)
    city_name = serializers.CharField(source="city.name", read_only=True, default=None)
    district_name = serializers.CharField(source="district.name", read_only=True, default=None)
    state_name = serializers.CharField(source="state.name", read_only=True, default=None)
    country_name = serializers.CharField(source="country.name", read_only=True, default=None)
    property_name = serializers.CharField(source="property_obj.property_name", read_only=True, default=None)
    sub_property_name = serializers.CharField(source="sub_property_obj.sub_property_name", read_only=True, default=None)

    apartment_name = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    block_no = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    flat_no = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    villa_no = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    industry_name = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    industry_type = serializers.CharField(required=False, allow_null=True, allow_blank=True)

    customer_name = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    contact_no = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    pincode = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    latitude = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    longitude = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    id_proof_type = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    id_no = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    street = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    area = serializers.CharField(required=False, allow_null=True, allow_blank=True)

    building_no = serializers.CharField()
    sqft = serializers.DecimalField(max_digits=10, decimal_places=2)

    group_qr_id = serializers.CharField(read_only=True)
    is_bulkwaste_generator = serializers.BooleanField(read_only=True)
    qr_code = serializers.ImageField(read_only=True)
    member_count = serializers.IntegerField(required=False, allow_null=True, min_value=0)
    family_members = serializers.ListField(
        child=serializers.DictField(),
        required=False,
        allow_empty=True,
    )

    password = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    password_crt_date = serializers.DateTimeField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)

    class Meta:
        model = CustomerCreation
        fields = [
            "unique_id",
            "customer_id",
            "company_id",
            "company_name",
            "project_id",
            "project_name",
            "project_logo",
            "customer_name",
            "contact_no",
            "building_no",
            "street",
            "area",
            "apartment_name",
            "block_no",
            "flat_no",
            "villa_no",
            "industry_name",
            "industry_type",
            "group_qr_id",
            "ward_id",
            "zone_id",
            "city_id",
            "district_id",
            "state_id",
            "country_id",
            "panchayat_id",
            "pincode",
            "latitude",
            "longitude",
            "sqft",
            "water_consumption_lpd",
            "waste_collection_kg_per_day",
            "id_proof_type",
            "id_no",
            "member_count",
            "family_members",
            "property_id",
            "sub_property_id",
            "waste_type_ids",
            "waste_types",
            "username",
            "app_module",
            "email",
            "password",
            "password_crt_date",
            "created_at",
            "is_deleted",
            "is_active",
            "ward_name",
            "zone_name",
            "panchayat_name",
            "city_name",
            "district_name",
            "state_name",
            "country_name",
            "property_name",
            "sub_property_name",
            "is_bulkwaste_generator",
            "qr_code",
        ]
        read_only_fields = ["unique_id", "customer_id", "password_crt_date", "created_at"]
        validators = []

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['password'] = decrypt_password(instance.password or "")
        return data

        # =============================
    # CREATE (ENCRYPT PASSWORD)
    # =============================
    def create(self, validated_data):
        password = validated_data.pop("password", None)
        waste_types = validated_data.pop("waste_type_ids", None)
        if waste_types is not None:
            validated_data["waste_type_ids"] = ",".join(w.unique_id for w in waste_types)

        instance = super().create(validated_data)

        if password:
            instance.password = encrypt_password(password)
            instance.save(update_fields=["password"])

        return instance

    # =============================
    # UPDATE (ENCRYPT PASSWORD)
    # =============================
    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        waste_types = validated_data.pop("waste_type_ids", None)
        if waste_types is not None:
            validated_data["waste_type_ids"] = ",".join(w.unique_id for w in waste_types)

        instance = super().update(instance, validated_data)

        if password:
            instance.password = encrypt_password(password)
            instance.save(update_fields=["password"])

        return instance

    def validate(self, attrs):
        # username has no DB-level unique constraint (MariaDB can't express
        # "unique among active rows only", and a plain unique=True would
        # block reusing a soft-deleted customer's username/email) — enforced
        # here instead, scoped like unique_name_validator's other callers:
        # only among is_deleted=False rows, within the same company/project.
        if attrs.get("username") == "":
            attrs["username"] = None
        if attrs.get("username"):
            attrs = unique_name_validator(
                Model=CustomerCreation,
                name_field="username",
                scope_fields=["company_id", "project_id"],
            )(self, attrs)

        instance = getattr(self, "instance", None)
        name = attrs.get("customer_name") or getattr(instance, "customer_name", None)
        mobile = attrs.get("contact_no") or getattr(instance, "contact_no", None)

        # if name and mobile:
        #     qs = CustomerCreation.objects.filter(
        #         customer_name__iexact=name,
        #         contact_no=mobile,
        #         is_deleted=False,
        #     )
        #     if instance:
        #         qs = qs.exclude(pk=instance.pk)
        #     if qs.exists():
        #         raise serializers.ValidationError(
        #             {"detail": "Customer with the same name and mobile already exists."}
        #         )

        building_no = attrs.get("building_no", getattr(instance, "building_no", None))
        if not building_no:
            raise serializers.ValidationError({"building_no": "Building/House number is required."})

        sqft = attrs.get("sqft", getattr(instance, "sqft", None))
        if sqft is None:
            raise serializers.ValidationError({"sqft": "Sqft is required."})

        # property_id/sub_property_id in attrs are plain unique_id strings
        # (NameOrUniqueIdField resolves to the slug, not the instance, since
        # the backing model fields are plain CharFields) — resolve the
        # actual rows before touching anything but the id.
        sub_property_id = attrs.get("sub_property_id") or getattr(instance, "sub_property_id", None)
        sub_property = (
            SubProperty.objects.filter(unique_id=sub_property_id).first()
            if sub_property_id else None
        )
        sub_name = (sub_property.sub_property_name or "").lower() if sub_property else ""

        property_id = attrs.get("property_id") or getattr(instance, "property_id", None)
        property_ref = (
            Property.objects.filter(unique_id=property_id).first()
            if property_id else None
        )
        # waste_type_ids in attrs is a list of plain unique_id strings, same
        # reason as above — the model's own field is a comma-separated
        # TextField, not a relation, so NameOrUniqueIdField resolves each
        # entry to its slug rather than the WasteType instance.
        waste_type_ids = attrs.get("waste_type_ids")
        if property_ref and waste_type_ids is not None:
            waste_types = list(WasteType.objects.filter(unique_id__in=waste_type_ids))
            property_name = (property_ref.property_name or "").lower()
            is_residential_customer = (
                "industry" not in sub_name
                and (
                    any(keyword in property_name for keyword in RESIDENTIAL_PROPERTY_KEYWORDS)
                    or any(keyword in sub_name for keyword in RESIDENTIAL_SUB_PROPERTY_KEYWORDS)
                )
            )
            if is_residential_customer:
                invalid_waste_types = [
                    waste_type.waste_type_name
                    for waste_type in waste_types
                    if (
                        "organic" in (waste_type.waste_type_name or "").lower()
                        or not any(
                            keyword in (waste_type.waste_type_name or "").lower()
                            for keyword in RESIDENTIAL_WASTE_TYPE_KEYWORDS
                        )
                    )
                ]
                if invalid_waste_types:
                    raise serializers.ValidationError(
                        {
                            "waste_type_ids": (
                                "Residential customers can only use Dry, Wet, Mixed, "
                                "and Sanitary Waste."
                            )
                        }
                    )

        return attrs

    def validate_family_members(self, value):
        allowed_keys = {"member_name", "id_proof_type", "id_no"}
        valid_id_proof_types = {choice for choice, _ in CustomerCreation.IDProofType.choices}
        for member in value:
            if not isinstance(member, dict):
                raise serializers.ValidationError("Each family member must be an object.")
            extra_keys = set(member.keys()) - allowed_keys
            if extra_keys:
                raise serializers.ValidationError(
                    f"Unsupported family member field(s): {', '.join(sorted(extra_keys))}"
                )
            id_proof_type = member.get("id_proof_type")
            if id_proof_type and id_proof_type not in valid_id_proof_types:
                raise serializers.ValidationError(
                    f"Invalid id_proof_type '{id_proof_type}' for family member."
                )
        return value

    def get_project_logo(self, obj):
        logo = getattr(getattr(obj, "project", None), "project_logo", None)
        if not logo:
            return None
        request = self.context.get("request")
        return request.build_absolute_uri(logo.url) if request else logo.url

    def get_waste_types(self, obj):
        return [
            {
                "unique_id": waste_type.unique_id,
                "waste_type_name": waste_type.waste_type_name,
            }
            for waste_type in obj.waste_types_queryset
        ]
