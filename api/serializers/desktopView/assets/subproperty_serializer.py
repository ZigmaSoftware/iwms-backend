from rest_framework import serializers
from api.apps.subproperty import SubProperty


class SubPropertySerializer(serializers.ModelSerializer):
    property_name = serializers.CharField(
        source="property_id.property_name",
        read_only=True
    )

    class Meta:
        model = SubProperty
        fields = "__all__"
        read_only_fields = ["unique_id"]   # SAME PATTERN AS StaffUserType
        validators = []                    # avoid built-in unique validator

    def validate_property_id(self, property_obj):
        """
        Ensure Property is valid (not deleted or inactive)
        """

        if hasattr(property_obj, "is_deleted") and property_obj.is_deleted:
            raise serializers.ValidationError("Selected Property is deleted.")

        if hasattr(property_obj, "is_active") and not property_obj.is_active:
            raise serializers.ValidationError("Selected Property is inactive.")

        return property_obj

    def validate(self, attrs):
        """
        Ensure unique sub-property per property (case-insensitive)
        """

        instance = getattr(self, "instance", None)

        prop = attrs.get("property_id", getattr(instance, "property_id", None))
        name = attrs.get("sub_property_name", getattr(instance, "sub_property_name", None))

        # PATCH-safe: if either field missing, skip validation
        if prop is None or name is None:
            return attrs

        name = name.strip()

        qs = SubProperty.objects.filter(
            sub_property_name__iexact=name,
            property_id=prop,
        )

        if hasattr(SubProperty, "is_deleted"):
            qs = qs.filter(is_deleted=False)

        if instance:
            qs = qs.exclude(pk=instance.pk)

        if qs.exists():
            raise serializers.ValidationError({
                "sub_property_name": "This sub property already exists for the selected property."
            })

        return attrs
