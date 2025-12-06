from rest_framework import serializers
from api.apps.mainscreen import MainScreen

class MainScreenSerializer(serializers.ModelSerializer):
    mainscreentype_name = serializers.CharField(
        source="mainscreentype_id.type_name",
        read_only=True
    )

    class Meta:
        model = MainScreen
        fields = "__all__"
