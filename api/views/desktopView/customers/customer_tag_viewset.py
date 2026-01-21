import re

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
    lookup_field = "unique_id"
    permission_resource = "CustomerTag"
    
    def _get_city_code(self, city):
        if getattr(city, "short_code", None):
            return city.short_code
        return (city.name or "")[:3]

    def _get_ward_code(self, ward):
        ward_no = getattr(ward, "ward_no", None)
        if ward_no:
            return str(ward_no)

        match = re.search(r"\d+", getattr(ward, "name", "") or "")
        if match:
            return match.group(0)

        return None

    def create(self, request, *args, **kwargs):
        """
        ADMIN ONLY (enforced by JWT permissions).
        Issue a new QR tag.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        customer = serializer.validated_data["customer"]
        customer_profile = getattr(customer, "customer_id", None)
        if not customer_profile:
            return Response(
                {"detail": "Selected user has no customer profile"},
                status=status.HTTP_400_BAD_REQUEST
            )
        if CustomerTag.objects.filter(customer=customer).exists():
            return Response(
                {"detail": "Customer tag already exists for this user"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not customer_profile.city or not customer_profile.ward:
            return Response(
                {"detail": "Customer must have city and ward to issue tag"},
                status=status.HTTP_400_BAD_REQUEST
            )

        city_code = self._get_city_code(customer_profile.city).upper()
        ward_code = self._get_ward_code(customer_profile.ward)

        if not ward_code:
            return Response(
                {"detail": "Ward must include a numeric identifier to issue tag"},
                status=status.HTTP_400_BAD_REQUEST
            )

        with transaction.atomic():
            tag_code = generate_customer_tag_code(city_code, ward_code)
            qr_payload = {
                "v": 1,
                "type": "HOUSEHOLD",
                "customer_id": customer.unique_id,
                "tag_code": tag_code,
                "zone": customer_profile.zone.name if customer_profile.zone else None,
                "ward": customer_profile.ward.name if customer_profile.ward else None,
            }
            qr_file = generate_customer_qr(qr_payload)

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
        Only status updates allowed.
        """
        instance = self.get_object()
        status_value = request.data.get("status")
        if not status_value:
            return Response(
                {"detail": "Status is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        valid_statuses = {choice[0] for choice in CustomerTag.Status.choices}
        if status_value not in valid_statuses:
            return Response(
                {"detail": "Invalid status"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if instance.status == status_value:
            return Response(
                {"detail": "Status already set"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if status_value == CustomerTag.Status.INACTIVE:
            instance.deactivate()
        else:
            instance.status = status_value
            instance.save(update_fields=["status", "updated_at"])

        return Response(
            CustomerTagSerializer(instance).data,
            status=status.HTTP_200_OK
        )

    def destroy(self, request, *args, **kwargs):
        return Response(
            {"detail": "Deletion is not allowed for customer tags"},
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )
