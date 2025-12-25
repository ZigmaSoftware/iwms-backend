from rest_framework import serializers
from api.apps.bin import Bin
from api.validators.unique_name_validator import unique_name_validator


class BinSerializer(serializers.ModelSerializer):
    ward_name = serializers.CharField(source="ward.name", read_only=True)

    class Meta:
        model = Bin
        fields = [
            "unique_id",
            "ward_id",
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
            "ward_name"
        ]
        read_only_fields = [
            "unique_id",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        # Allow PATCH for status / active toggle without name validation
        if self.instance and "bin_name" not in attrs:
            return attrs

        return unique_name_validator(
            Model=Bin,
            name_field="bin_name",
            scope_fields=["ward"],   # uniqueness per ward
        )(self, attrs)

    def update(self, instance, validated_data):
        # Business rule: decommissioned bins must be inactive
        if validated_data.get("bin_status") == "decommissioned":
            validated_data["is_active"] = False

        return super().update(instance, validated_data)
