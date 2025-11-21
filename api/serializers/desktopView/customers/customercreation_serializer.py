from typing import Optional

from rest_framework import serializers

from api.apps.customercreation import CustomerCreation


class CustomerCreationSerializer(serializers.ModelSerializer):
    ward_name = serializers.SerializerMethodField()
    zone_name = serializers.SerializerMethodField()
    city_name = serializers.SerializerMethodField()
    district_name = serializers.SerializerMethodField()
    state_name = serializers.SerializerMethodField()
    country_name = serializers.SerializerMethodField()
    property_name = serializers.SerializerMethodField()
    sub_property_name = serializers.SerializerMethodField()

    class Meta:
        model = CustomerCreation
        fields = "__all__"

    def _resolve_name(self, obj, attr: str) -> Optional[str]:
        related_obj = getattr(obj, attr, None)
        return getattr(related_obj, "name", None) if related_obj else None

    def _resolve_property_name(self, obj) -> Optional[str]:
        related_obj = getattr(obj, "property", None)
        return getattr(related_obj, "property_name", None) if related_obj else None

    def _resolve_sub_property_name(self, obj) -> Optional[str]:
        related_obj = getattr(obj, "sub_property", None)
        return getattr(related_obj, "sub_property_name", None) if related_obj else None

    def get_ward_name(self, obj):
        return self._resolve_name(obj, "ward")

    def get_zone_name(self, obj):
        return self._resolve_name(obj, "zone")

    def get_city_name(self, obj):
        return self._resolve_name(obj, "city")

    def get_district_name(self, obj):
        return self._resolve_name(obj, "district")

    def get_state_name(self, obj):
        return self._resolve_name(obj, "state")

    def get_country_name(self, obj):
        return self._resolve_name(obj, "country")

    def get_property_name(self, obj):
        return self._resolve_property_name(obj)

    def get_sub_property_name(self, obj):
        return self._resolve_sub_property_name(obj)
