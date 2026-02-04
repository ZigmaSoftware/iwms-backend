from rest_framework import serializers
from api.serializers.utils.tenancy import TenancyReadSerializerMixin
from api.models.users.userType import UserType
from api.validators.unique_name_validator import unique_name_validator
class UserTypeSerializer(TenancyReadSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = UserType
        fields = '__all__'
        read_only_fields = ["unique_id"]  
        validators = []
    def validate(self, attrs):
        return unique_name_validator(
            Model=UserType,
            name_field="name",
        )(self, attrs)
