from rest_framework import serializers
from app.serializers.company_projects.tenancy import TenancyReadSerializerMixin
from app.models.superadmin.screen_management.mainscreentype import MainScreenType


class MainScreenTypeSerializer(TenancyReadSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = MainScreenType
        fields = "__all__"
