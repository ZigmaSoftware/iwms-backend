from rest_framework import serializers

from app.models.common_masters.country import Country
from app.models.common_masters.state import State
from app.models.customers.customercreation import CustomerCreation
from app.models.masters.city import City
from app.models.masters.district import District
from app.models.masters.panchayat import Panchayat
from app.models.masters.ward import Ward
from app.models.masters.zone import Zone
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project
from app.models.waste_types.property import Property
from app.models.waste_types.subproperty import SubProperty
from app.models.staff_creations.waste_collection_bluetooth import WasteType
from app.serializers.company_projects.tenancy import TenancyReadSerializerMixin
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
    company_id = serializers.SlugRelatedField(
        # source="company_id",
        queryset=Company.objects.all(),
        slug_field="unique_id",
        required=False,
        allow_null=True,
        )

    project_id = serializers.SlugRelatedField(
        # source="project_id",
        queryset=Project.objects.all(),
        slug_field="unique_id",
        required=False,
        allow_null=True,
    )
    ward_id = serializers.SlugRelatedField(
        source="ward",
        queryset=Ward.objects.all(),
        slug_field="unique_id",
        required=False,
        allow_null=True,
    )
    zone_id = serializers.SlugRelatedField(
        source="zone",
        queryset=Zone.objects.all(),
        slug_field="unique_id",
        required=False,
        allow_null=True,
    )
    city_id = serializers.SlugRelatedField (
        source="city",
        queryset=City.objects.all(),
        slug_field="unique_id",
        required=False,
        allow_null=True,
    )
    district_id = serializers.SlugRelatedField(
        source="district",
        queryset=District.objects.all(),
        slug_field="unique_id",
        required=False,
        allow_null=True,
    )
    state_id = serializers.SlugRelatedField(
        source="state",
        queryset=State.objects.all(),
        slug_field="unique_id",
        required=False,
        allow_null=True,
    )
    country_id = serializers.SlugRelatedField(
        source="country",
        queryset=Country.objects.all(),
        slug_field="unique_id",
        required=False,
        allow_null=True,
    )
    panchayat_id = serializers.SlugRelatedField(
        # source="panchayat_id",
        queryset=Panchayat.objects.all(),
        slug_field="unique_id",
        required=False,
        allow_null=True,
    )
    property_id = serializers.SlugRelatedField(
        source="property_ref",
        queryset=Property.objects.all(),
        slug_field="unique_id",
        required=False,
        allow_null=True,
    )
    sub_property_id = serializers.SlugRelatedField(
        source="sub_property",
        queryset=SubProperty.objects.all(),
        slug_field="unique_id",
        required=False,
        allow_null=True,
    )
    waste_type_ids = serializers.SlugRelatedField(
        source="waste_types",
        queryset=WasteType.objects.filter(is_deleted=False),
        slug_field="unique_id",
        many=True,
        required=False,
    )
    waste_types = serializers.SerializerMethodField(read_only=True)
    # Local-body emblem for the project, printed on the customer QR sticker.
    project_logo = serializers.SerializerMethodField(read_only=True)
    panchayat_id = serializers.SlugRelatedField(
        # source="panchayat_id",
        queryset=Panchayat.objects.all(),
        slug_field="unique_id",
        required=False,
        allow_null=True,
    )
    panchayat_name = serializers.CharField(source="panchayat_id.panchayat_name", read_only=True)
    ward_name = serializers.CharField(source="ward.ward_name", read_only=True)
    zone_name = serializers.CharField(source="zone.zone_name", read_only=True)
    city_name = serializers.CharField(source="city.name", read_only=True)
    district_name = serializers.CharField(source="district.name", read_only=True)
    state_name = serializers.CharField(source="state.name", read_only=True)
    country_name = serializers.CharField(source="country.name", read_only=True)
    property_name = serializers.CharField(source="property_ref.property_name", read_only=True)
    sub_property_name = serializers.CharField(source="sub_property.sub_property_name", read_only=True)

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

        instance = super().update(instance, validated_data)

        if password:
            instance.password = encrypt_password(password)
            instance.save(update_fields=["password"])

        return instance

    def validate(self, attrs):
        # attrs = unique_name_validator(
        #     Model=CustomerCreation,
        #     name_field="user_name",
        # )(self, attrs)

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

        sub_property = attrs.get("sub_property") or getattr(instance, "sub_property", None)
        sub_name = (sub_property.sub_property_name or "").lower() if sub_property else ""

        property_ref = attrs.get("property_ref") or getattr(instance, "property_ref", None)
        waste_types = attrs.get("waste_types")
        if property_ref and waste_types is not None:
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
        logo = getattr(getattr(obj, "project_id", None), "project_logo", None)
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
            for waste_type in obj.waste_types.all()
        ]
