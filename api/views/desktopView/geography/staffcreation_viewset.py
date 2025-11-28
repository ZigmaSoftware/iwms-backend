from rest_framework import viewsets, filters, status
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser

from api.models import Staffcreation
from api.serializers import StaffcreationSerializer


class StaffcreationViewset(viewsets.ModelViewSet):
    queryset = Staffcreation.objects.all().order_by("-id")
    serializer_class = StaffcreationSerializer
    parser_classes = (MultiPartParser, FormParser)

    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["employee_name", "employee_id", "site_name", "department", "designation"]
    ordering_fields = ["id", "employee_name", "employee_id", "created_at"]

    def get_queryset(self):
        queryset = Staffcreation.objects.all()

        site_name = self.request.query_params.get("site_name", None)
        employee_name = self.request.query_params.get("employee_name", None)
        active_status = self.request.query_params.get("active_status", None)
        salary_type = self.request.query_params.get("salary_type", None)

        if site_name:
            queryset = queryset.filter(site_name__icontains=site_name)

        if employee_name:
            queryset = queryset.filter(employee_name__icontains=employee_name)

        if active_status in ["0", "1"]:
            queryset = queryset.filter(active_status=active_status)

        if salary_type:
            queryset = queryset.filter(salary_type__icontains=salary_type)

        return queryset.order_by("-id")

    def create(self, request, *args, **kwargs):
        serializer = StaffcreationSerializer(data=request.data)

        if serializer.is_valid():
            serializer.save()
            return Response(
                {"status": True, "message": "Staff Created Successfully"},
                status=status.HTTP_201_CREATED
            )

        return Response(
            {"status": False, "errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = StaffcreationSerializer(instance, data=request.data, partial=True)

        if serializer.is_valid():
            serializer.save()
            return Response(
                {"status": True, "message": "Staff Updated Successfully"},
                status=status.HTTP_200_OK
            )

        return Response(
            {"status": False, "errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.delete()

        return Response(
            {"status": True, "message": "Staff Deleted Successfully"},
            status=status.HTTP_200_OK
        )
