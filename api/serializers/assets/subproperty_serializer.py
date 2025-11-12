from rest_framework import serializers
from ...apps.subproperty import SubProperty

class SubPropertySerializer(serializers.ModelSerializer):
    property_name = serializers.CharField(source="property.property_name", read_only=True)

    class Meta:
        model = SubProperty
        fields = "__all__"
