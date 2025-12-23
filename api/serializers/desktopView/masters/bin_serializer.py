from rest_framework import serializers
from api.apps.bin import Bin
from api.validators.unique_name_validator import unique_name_validator


class BinSerializer(serializers.ModelSerializer):
    class Meta:
        model = Bin
        fields = [
            "unique_id",
            "ward",
            "bin_name",
            "bin_type",
            "waste_type",
            "color_code",
            "capacity_liters",
            "latitude",
            "longitude",
            "installation_date",
            "expected_life_years",
            "bin_status",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "unique_id",
            "created_at",
            "updated_at",
        ]
        validators = []

    def validate(self, attrs):
        """
        Enforce unique bin_name within a ward (enterprise-safe)
        """
        return unique_name_validator(
            Model=Bin,
            name_field="bin_name",
            extra_filters={
                "ward": attrs.get("ward", getattr(self.instance, "ward", None)),
                "is_deleted": False,
            },
        )(self, attrs)

    def update(self, instance, validated_data):
        """
        Auto-deactivate when decommissioned
        """
        bin_status = validated_data.get("bin_status")

        if bin_status == "decommissioned":
            validated_data["is_active"] = False

        return super().update(instance, validated_data)
