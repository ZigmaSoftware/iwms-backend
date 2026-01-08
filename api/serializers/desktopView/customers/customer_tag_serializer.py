from rest_framework import serializers
from api.apps.customer_tag import CustomerTag
from api.apps.customercreation import CustomerCreation


class CustomerTagSerializer(serializers.ModelSerializer):

    customer_id = serializers.SlugRelatedField(
        source="customer",
        slug_field="unique_id",
        queryset=CustomerCreation.objects.all()
    )

    class Meta:
        model = CustomerTag
        fields = [
            "id",
            "customer_id",
            "tag_code",
            "qr_image",
            "status",
            "issued_at",
            "revoked_at",
        ]
        read_only_fields = [
            "id",
            "tag_code",
            "qr_image",
            "issued_at",
            "revoked_at",
        ]
