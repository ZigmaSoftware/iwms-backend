from rest_framework import serializers
from api.serializers.utils.tenancy import TenancyReadSerializerMixin
from api.models.commonmasters.continent import Continent
from api.validators.unique_name_validator import unique_name_validator

class ContinentSerializer(TenancyReadSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = Continent
        fields = "__all__"
        read_only_fields = ["unique_id"]
        validators = []  # disable DRF unique constraint

    def validate(self, attrs):
        return unique_name_validator(
            Model=Continent,
            name_field="name",
        )(self, attrs)
