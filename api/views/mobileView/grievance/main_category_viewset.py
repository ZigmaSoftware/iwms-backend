from rest_framework import viewsets, status
from rest_framework.response import Response
from django.db.models import Q

from api.apps.main_category_citizenGrievance import MainCategory
from api.serializers.mobileView.grievance.maincategory_serializer import MainCategorySerializer


class MainCategoryViewSet(viewsets.ViewSet):

    # Helper method
    def get_object(self, pk):
        return MainCategory.objects.filter(pk=pk, is_delete=False).first()

    # GET /main-category/
    def list(self, request):
        queryset = MainCategory.objects.filter(is_delete=False).order_by("id")
        serializer = MainCategorySerializer(queryset, many=True)
        return Response({"status": True, "data": serializer.data})

    # POST /main-category/
    def create(self, request):
        serializer = MainCategorySerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"status": False, "errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        instance = serializer.save()  # unique_id auto generated
        return Response(
            {
                "status": True,
                "message": "Main category created successfully",
                "data": MainCategorySerializer(instance).data,
            },
            status=status.HTTP_201_CREATED,
        )

    # GET /main-category/<id>/
    def retrieve(self, request, pk=None):
        instance = self.get_object(pk)
        if not instance:
            return Response(
                {"status": False, "message": "Main category not found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(
            {"status": True, "data": MainCategorySerializer(instance).data}
        )

    # PUT /main-category/<id>/
    def update(self, request, pk=None):
        instance = self.get_object(pk)
        if not instance:
            return Response(
                {"status": False, "message": "Main category not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = MainCategorySerializer(instance, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(
                {"status": False, "errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer.save()
        return Response(
            {"status": True, "message": "Updated successfully", "data": serializer.data}
        )

    # DELETE /main-category/<id>/
    def destroy(self, request, pk=None):
        instance = self.get_object(pk)
        if not instance:
            return Response(
                {"status": False, "message": "Main category not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        instance.delete()  # Soft delete (your custom delete method)
        return Response(
            {"status": True, "message": "Main category deactivated"},
            status=status.HTTP_200_OK,
        )
