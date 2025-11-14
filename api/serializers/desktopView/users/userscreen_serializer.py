from rest_framework import serializers
from api.apps.userscreen import UserScreen

class UserScreenSerializer(serializers.ModelSerializer):
    mainscreen_name = serializers.CharField(source="mainscreen.mainscreen", read_only=True)

    class Meta:
        model = UserScreen
        fields = "__all__"
