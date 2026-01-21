from rest_framework import serializers
from api.apps.customer_tag import CustomerTag
from api.apps.userCreation import User

class UniqueIdOrPkField(serializers.SlugRelatedField):
    """
    Accept related object via unique_id (slug) or numeric PK.
    Serialize always as unique_id.
    """

    def to_representation(self, value):
        return getattr(value, self.slug_field, None)

    def to_internal_value(self, data):
        try:
            return super().to_internal_value(data)
        except Exception:
            try:
                return self.get_queryset().get(pk=data)
            except Exception:
                raise serializers.ValidationError("Invalid reference value")



class CustomerTagSerializer(serializers.ModelSerializer):

    # customer_id = serializers.SlugRelatedField(
    #     source="customer",
    #     slug_field="unique_id",
    #     queryset=User.objects.all()
    # )
    customer_id = UniqueIdOrPkField(
        source="customer",
        slug_field="unique_id",
        queryset=User.objects.filter(customer_id__isnull=False),
        required=False,
        allow_null=True,
    )
    customer_name = serializers.CharField(
        source="customer.customer_id.customer_name",
        read_only=True
    )

    class Meta:
        model = CustomerTag
        fields = [
           
            "unique_id",
            "customer_id",
            "customer_name",
            "tag_code",
            "qr_image",
            "status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
          
            "unique_id",
            "tag_code",
            "qr_image",
            "created_at",
            "updated_at",
        ]
