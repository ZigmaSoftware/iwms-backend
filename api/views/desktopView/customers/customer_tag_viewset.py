from rest_framework.viewsets import ModelViewSet
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction

from api.apps.customer_tag import CustomerTag
from api.serializers.desktopView.customers.customer_tag_serializer import (
    CustomerTagSerializer
)
from api.apps.utils.customer_tag_utils import (
    generate_customer_tag_code,
    generate_customer_qr,
)


class CustomerTagViewSet(ModelViewSet):
    """
    Customer container QR issuance & revocation.
    Auth enforced via JWT + ModulePermissionMiddleware.
    """

    queryset = CustomerTag.objects.all()
    serializer_class = CustomerTagSerializer
    permission_resource = "CustomerTag"
    

    def create(self, request, *args, **kwargs):
        """
        ADMIN ONLY (enforced by JWT permissions).
        Issue a new QR tag.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        customer = serializer.validated_data["customer"]

        if not customer.city or not customer.ward:
            return Response(
                {"detail": "Customer must have city and ward to issue tag"},
                status=status.HTTP_400_BAD_REQUEST
            )

        city_code = customer.city.short_code if hasattr(customer.city, "short_code") else customer.city.name[:3]
        ward_no = int(customer.ward.id)

        with transaction.atomic():
            tag_code = generate_customer_tag_code(city_code, ward_no)
            qr_file = generate_customer_qr(tag_code)

            instance = CustomerTag.objects.create(
                customer=customer,
                tag_code=tag_code,
                qr_image=qr_file,
            )

        return Response(
            CustomerTagSerializer(instance).data,
            status=status.HTTP_201_CREATED
        )

    def update(self, request, *args, **kwargs):
        """
        ADMIN + SUPERVISOR.
        Only revocation allowed.
        """
        instance = self.get_object()

        if instance.status == "REVOKED":
            return Response(
                {"detail": "Tag already revoked"},
                status=status.HTTP_400_BAD_REQUEST
            )

        instance.revoke()

        return Response(
            CustomerTagSerializer(instance).data,
            status=status.HTTP_200_OK
        )

    def destroy(self, request, *args, **kwargs):
        return Response(
            {"detail": "Deletion is not allowed for customer tags"},
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )
