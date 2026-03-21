from rest_framework import serializers
from app.serializers.company_projects.tenancy import TenancyReadSerializerMixin
from app.models.customers.customercreation import CustomerCreation

from app.models.common_masters.country import Country
from app.models.common_masters.state import State
from app.models.masters.district import District
from app.models.masters.city import City
from app.models.masters.zone import Zone
from app.models.masters.ward import Ward
from app.models.masters.panchayat import Panchayat

from app.models.waste_types.property import Property
from app.models.waste_types.subproperty import SubProperty

from app.validators.unique_name_validator import unique_name_validator


class CustomerCreationSerializer(
    TenancyReadSerializerMixin,
    serializers.ModelSerializer
):

    # -----------------------------
    # FK INPUTS
    # -----------------------------
    ward_id = serializers.PrimaryKeyRelatedField(
        source="ward",
        queryset=Ward.objects.all(),
        required=False,
        allow_null=True,
    )

    zone_id = serializers.PrimaryKeyRelatedField(
        source="zone",
        queryset=Zone.objects.all(),
        required=False,
        allow_null=True,
    )

    city_id = serializers.PrimaryKeyRelatedField(
        source="city",
        queryset=City.objects.all(),
        required=False,
        allow_null=True,
    )

    district_id = serializers.PrimaryKeyRelatedField(
        source="district",
        queryset=District.objects.all(),
        required=False,
        allow_null=True,
    )

    state_id = serializers.PrimaryKeyRelatedField(
        source="state",
        queryset=State.objects.all(),
    )

    country_id = serializers.PrimaryKeyRelatedField(
        source="country",
        queryset=Country.objects.all(),
    )

    panchayat_id = serializers.PrimaryKeyRelatedField(
        queryset=Panchayat.objects.all(),
        required=False,
        allow_null=True
    )

    property_id = serializers.PrimaryKeyRelatedField(
        source="property_ref",
        queryset=Property.objects.all(),
    )

    sub_property_id = serializers.PrimaryKeyRelatedField(
        source="sub_property",
        queryset=SubProperty.objects.all(),
    )

    # -----------------------------
    # READABLE NAME MAPPING (FIXED)
    # -----------------------------
    ward_name = serializers.CharField(source="ward.ward_name", read_only=True)
    zone_name = serializers.CharField(source="zone.zone_name", read_only=True)

    city_name = serializers.CharField(source="city.name", read_only=True)
    district_name = serializers.CharField(source="district.name", read_only=True)
    state_name = serializers.CharField(source="state.name", read_only=True)
    country_name = serializers.CharField(source="country.name", read_only=True)

    property_name = serializers.CharField(source="property_ref.property_name", read_only=True)
    sub_property_name = serializers.CharField(source="sub_property.sub_property_name", read_only=True)

    class Meta:
        model = CustomerCreation

        fields = [
            "unique_id",
            "company_id",
            "company_name",
            "project_id",
            "project_name",

            "customer_name",
            "contact_no",

            "building_no",
            "street",
            "area",

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

            "id_proof_type",
            "id_no",

            "property_id",
            "sub_property_id",

            "username",
            "email",

            "is_deleted",
            "is_active",

            "ward_name",
            "zone_name",
            "city_name",
            "district_name",
            "state_name",
            "country_name",
            "property_name",
            "sub_property_name",
            "is_bulkwaste_generator"
        ]

        read_only_fields = ["unique_id"]
        validators = []

    # -----------------------------
    # VALIDATION
    # -----------------------------
    def validate(self, attrs):

        attrs = unique_name_validator(
            Model=CustomerCreation,
            name_field="customer_name",
        )(self, attrs)

        name = attrs.get("customer_name")
        mobile = attrs.get("contact_no")

        instance = getattr(self, "instance", None)

        qs = CustomerCreation.objects.filter(
            customer_name__iexact=name,
            contact_no=mobile,
            is_deleted=False
        )

        if instance:
            qs = qs.exclude(pk=instance.pk)

        if qs.exists():
            raise serializers.ValidationError(
                {"detail": "Customer with the same name and mobile already exists."}
            )

        return attrs