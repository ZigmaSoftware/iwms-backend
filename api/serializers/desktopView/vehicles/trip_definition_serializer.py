from rest_framework import serializers

from api.apps.trip_definition import TripDefinition
from api.apps.routeplan import RoutePlan
from api.apps.stafftemplate import StaffTemplate
from api.apps.property import Property
from api.apps.subproperty import SubProperty
from api.apps.userCreation import User
from api.serializers.desktopView.users.user_serializer import UniqueIdOrPkField


# ==========================================================
# MINI USER SERIALIZER (Driver / Operator)
# ==========================================================
class MiniUserSerializer(serializers.ModelSerializer):
    name = serializers.CharField(
        source="staff_id.employee_name",
        read_only=True
    )
    mobile = serializers.CharField(
        source="staff_id.personal_details.contact_mobile",
        read_only=True
    )
    designation = serializers.CharField(
        source="staff_id.designation",
        read_only=True
    )

    class Meta:
        model = User
        fields = (
            "unique_id",
            "name",
            "mobile",
            "designation",
        )


# ==========================================================
# TRIP DEFINITION SERIALIZER
# ==========================================================
class TripDefinitionSerializer(serializers.ModelSerializer):

    # ------------------------------------------------------
    # INPUT FIELDS (WRITE-ONLY | FK unique_id)
    # ------------------------------------------------------
    routeplan_id = UniqueIdOrPkField(
        slug_field="unique_id",
        queryset=RoutePlan.objects.all(),
        write_only=True,
    )

    staff_template_id = UniqueIdOrPkField(
        slug_field="unique_id",
        queryset=StaffTemplate.objects.all(),
        write_only=True,
    )

    property_id = UniqueIdOrPkField(
        slug_field="unique_id",
        queryset=Property.objects.all(),
        write_only=True,
    )

    sub_property_id = UniqueIdOrPkField(
        slug_field="unique_id",
        queryset=SubProperty.objects.all(),
        write_only=True,
    )

    # ------------------------------------------------------
    # OUTPUT FIELDS (READ-ONLY | Nested Objects)
    # ------------------------------------------------------
    routeplan = serializers.SerializerMethodField()
    staff_template = serializers.SerializerMethodField()
    property = serializers.SerializerMethodField()
    sub_property = serializers.SerializerMethodField()

    # ------------------------------------------------------
    # META CONFIGURATION
    # ------------------------------------------------------
    class Meta:
        model = TripDefinition
        fields = (
            "unique_id",

            # write-only
            "routeplan_id",
            "staff_template_id",
            "property_id",
            "sub_property_id",

            # read-only
            "routeplan",
            "staff_template",
            "property",
            "sub_property",

            "trip_trigger_weight_kg",
            "max_vehicle_capacity_kg",
            "approval_status",
            "status",
            "created_at",
        )

        read_only_fields = (
            "unique_id",
            "approval_status",
            "created_at",
        )

    # ======================================================
    # SERIALIZER METHOD FIELDS
    # ======================================================
    def get_routeplan(self, obj):
        rp = obj.routeplan_id
        return {
            "unique_id": rp.unique_id,
            "district": getattr(rp.district_id, "name", None),
            "city": getattr(rp.city_id, "name", None),
            "zone": getattr(rp.zone_id, "name", None),
            "vehicle_no": getattr(rp.vehicle_id, "vehicle_no", None),
            "supervisor": getattr(
                getattr(rp.supervisor_id, "staff_id", None),
                "employee_name",
                None
            ),
           "display_code": rp.display_code,
        }

    def get_staff_template(self, obj):
        st = obj.staff_template_id
        return {
            "unique_id": st.unique_id,
            "display_code": st.display_code,
            "driver": (
                MiniUserSerializer(st.driver_id, context=self.context).data
                if st.driver_id else None
            ),
            "operator": (
                MiniUserSerializer(st.operator_id, context=self.context).data
                if st.operator_id else None
            ),
            "status": st.status,
        }

    def get_property(self, obj):
        prop = obj.property_id
        return {
            "unique_id": prop.unique_id,
            "property_name": getattr(prop, "property_name", None),
        }

    def get_sub_property(self, obj):
        sub = obj.sub_property_id
        return {
            "unique_id": sub.unique_id,
            "sub_property_name": getattr(sub, "sub_property_name", None),
        }

    # ======================================================
    # VALIDATIONS
    # ======================================================
    def validate(self, attrs):
        instance = getattr(self, "instance", None)

        trigger = attrs.get(
            "trip_trigger_weight_kg",
            getattr(instance, "trip_trigger_weight_kg", None),
        )
        capacity = attrs.get(
            "max_vehicle_capacity_kg",
            getattr(instance, "max_vehicle_capacity_kg", None),
        )

        if trigger is not None and capacity is not None and trigger >= capacity:
            raise serializers.ValidationError(
                "Trigger weight must be less than vehicle capacity."
            )

        property_obj = attrs.get(
            "property_id",
            getattr(instance, "property_id", None),
        )
        sub_property_obj = attrs.get(
            "sub_property_id",
            getattr(instance, "sub_property_id", None),
        )

        if (
            property_obj
            and sub_property_obj
            and sub_property_obj.property_id != property_obj
        ):
            raise serializers.ValidationError(
                "Sub-property does not belong to the selected property."
            )

        return attrs


class TripDefinitionSwaggerSerializer(TripDefinitionSerializer):
    """
    Use a writable approval_status so swagger shows the field even though it is read-only in practice.
    """

    class Meta(TripDefinitionSerializer.Meta):
        read_only_fields = tuple(
            field
            for field in TripDefinitionSerializer.Meta.read_only_fields
            if field != "approval_status"
        )
