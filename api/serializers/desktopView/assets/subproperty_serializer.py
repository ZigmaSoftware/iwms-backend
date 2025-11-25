from rest_framework import serializers
from api.apps.subproperty import SubProperty

class SubPropertySerializer(serializers.ModelSerializer):
    property_name = serializers.CharField(
        source="property.property_name",
        read_only=True
    )

    class Meta:
        model = SubProperty
        fields = "__all__"
        # ⚠️ IMPORTANT: REMOVE ALL BUILT-IN UNIQUE VALIDATORS
        validators = []   # This eliminates the is_deleted KeyError

    def validate(self, attrs):
        instance = getattr(self, "instance", None)

        # Get the values - PATCH safe
        name = attrs.get("sub_property_name", getattr(instance, "sub_property_name", None))
        prop = attrs.get("property", getattr(instance, "property", None))

        # If PATCH only updates is_active → skip validation entirely
        if name is None or prop is None:
            return attrs

        name = name.strip()

        # Duplicate check
        qs = SubProperty.objects.filter(
            sub_property_name__iexact=name,
            property=prop,
        )

        # If you have soft delete
        if hasattr(SubProperty, "is_deleted"):
            qs = qs.filter(is_deleted=False)

        # Exclude the same row on edit
        if instance:
            qs = qs.exclude(pk=instance.pk)

        if qs.exists():
            raise serializers.ValidationError({
                "sub_property_name": "This sub property already exists for the selected property."
            })

        return attrs

