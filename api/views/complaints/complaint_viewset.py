from rest_framework import viewsets, status
from rest_framework.response import Response
from ...apps.complaints import Complaint
from ...serializers.complaints.complaint_serializer import ComplaintSerializer

class ComplaintViewSet(viewsets.ModelViewSet):
    serializer_class = ComplaintSerializer
    queryset = Complaint.objects.filter(is_deleted=False).select_related("customer", "zone", "ward")

    def get_queryset(self):
        queryset = Complaint.objects.filter(is_deleted=False)
        customer_id = self.request.query_params.get("customer_id") or self.request.query_params.get("customer")
        if customer_id:
            queryset = queryset.filter(customer_id=customer_id)
        return queryset

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.is_deleted = True
        instance.save()
        return Response({"message": "Complaint soft deleted successfully"}, status=status.HTTP_200_OK)
