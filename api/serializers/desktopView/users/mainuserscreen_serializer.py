from rest_framework import serializers
from api.apps.mainuserscreen import MainUserScreen

class MainUserScreenSerializer(serializers.ModelSerializer):
    class Meta:
        model = MainUserScreen
        fields = "__all__"
