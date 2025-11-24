from rest_framework import viewsets, status
from rest_framework.response import Response
from django.db.models import Q

from api.apps.sub_category_citizenGrievance import SubCategory
from api.serializers.mobileView.grievance.subcategory_serializer import SubCategorySerializer


class SubCategoryViewSet(viewsets.ViewSet):

    def get_object(self, pk):
        return SubCategory.objects.filter(id=pk, is_delete=False).first()

    # GET: /subcategory/
    def list(self, request):
        queryset = SubCategory.objects.filter(is_delete=False).order_by("name")
        serializer = SubCategorySerializer(queryset, many=True)
        return Response({"status": True, "data": serializer.data})

    # POST: /subcategory/
    def create(self, request):
        serializer = SubCategorySerializer(data=request.data)

        if not serializer.is_valid():
            return Response(
                {"status": False, "errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        instance = serializer.save()

        return Response(
            {
                "status": True,
                "message": "SubCategory created successfully",
                "data": SubCategorySerializer(instance).data,
            },
            status=status.HTTP_201_CREATED,
        )

    # GET: /subcategory/<id>/
    def retrieve(self, request, pk=None):
        instance = self.get_object(pk)

        if not instance:
            return Response(
                {"status": False, "message": "SubCategory not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = SubCategorySerializer(instance)
        return Response({"status": True, "data": serializer.data})

    # PUT/PATCH: /subcategory/<id>/
    def update(self, request, pk=None):
        instance = self.get_object(pk)

        if not instance:
            return Response(
                {"status": False, "message": "SubCategory not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = SubCategorySerializer(instance, data=request.data, partial=True)

        if not serializer.is_valid():
            return Response(
                {"status": False, "errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        updated = serializer.save()

        return Response(
            {
                "status": True,
                "message": "SubCategory updated",
                "data": SubCategorySerializer(updated).data,
            }
        )

    # DELETE: /subcategory/<id>/
    def destroy(self, request, pk=None):
        instance = self.get_object(pk)

        if not instance:
            return Response(
                {"status": False, "message": "SubCategory not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        instance.delete()  # soft delete

        return Response(
            {"status": True, "message": "SubCategory deactivated"},
            status=status.HTTP_200_OK,
        )
