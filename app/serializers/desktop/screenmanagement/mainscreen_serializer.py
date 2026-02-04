from rest_framework import serializers
from app.serializers.utils.tenancy import TenancyReadSerializerMixin
from app.models.screenmanagement.mainscreen import MainScreen

class MainScreenSerializer(TenancyReadSerializerMixin, serializers.ModelSerializer):
    mainscreentype_name = serializers.CharField(
        source="mainscreentype_id.type_name",
        read_only=True
    )

    class Meta:
        model = MainScreen
        fields = "__all__"
