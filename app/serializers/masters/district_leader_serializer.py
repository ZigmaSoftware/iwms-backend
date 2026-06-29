from rest_framework import serializers
from django.contrib.auth.hashers import make_password

from app.models.masters.district_leader_login import DistrictLeaderLogin
from app.models.masters.district import District
from app.serializers.company_projects.tenancy import TenancyReadSerializerMixin


class DistrictLeaderLoginSerializer(TenancyReadSerializerMixin, serializers.ModelSerializer):

    district_id = serializers.PrimaryKeyRelatedField(
        queryset=District.objects.filter(is_deleted=False),
        required=True,
    )
    district_name = serializers.CharField(
        source="district_id.name",
        read_only=True,
    )

    password = serializers.CharField(
        required=False,
        allow_blank=True,
        # write_only=False to match project pattern for edit forms
    )

    class Meta:
        model = DistrictLeaderLogin
        fields = [
            "unique_id",
            "company_id",
            "company_name",
            "project_id",
            "project_name",
            "district_id",
            "district_name",
            "username",
            "password",
            "email",
            "leader_name",
            "is_active",
            "is_deleted",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["unique_id", "created_at", "updated_at"]

    def validate_district_id(self, value):
        """One district can have at most one (non-deleted) leader."""
        if not value:
            return value
        qs = DistrictLeaderLogin.objects.filter(
            district_id=value,
            is_deleted=False,
        )
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                "This district already has a leader assigned. Each district can have only one leader."
            )
        return value

    def validate_username(self, value):
        if not value:
            return value
        qs = DistrictLeaderLogin.objects.filter(username=value, is_deleted=False)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("A district leader with this username already exists.")
        return value

    def create(self, validated_data):
        raw_password = validated_data.pop("password", None)
        if raw_password:
            validated_data["password"] = make_password(raw_password)
        else:
            raise serializers.ValidationError({"password": "Password is required."})

        # Inherit company/project from district if not provided
        district = validated_data.get("district_id")
        if district and not validated_data.get("company_id"):
            validated_data["company_id"] = district.company_id
        if district and not validated_data.get("project_id"):
            validated_data["project_id"] = district.project_id

        return DistrictLeaderLogin.objects.create(**validated_data)

    def update(self, instance, validated_data):
        raw_password = validated_data.pop("password", None)
        if raw_password:
            validated_data["password"] = make_password(raw_password)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance
