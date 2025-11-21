from rest_framework import serializers

from api.apps.staffcreation import Staffcreation


class StaffcreationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Staffcreation
        fields = "__all__"
