from rest_framework import viewsets, status
from rest_framework.response import Response
from api.apps.main_category_citizenGrievance import MainCategory
from api.serializers.mobileView.grievance.maincategory_serializer import MainCategorySerializer


class MainCategoryViewSet(viewsets.ModelViewSet):
    serializer_class = MainCategorySerializer

    def get_queryset(self):
        return MainCategory.objects.filter(is_delete=False).order_by("id")

    # GET /main-category/<id>/
    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = MainCategorySerializer(instance)
        return Response(serializer.data, status=200)

    # POST
    def create(self, request, *args, **kwargs):
        serializer = MainCategorySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"status": True, "msg": "Created Successfully"}, status=201)

    # PUT
    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = MainCategorySerializer(instance, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"status": True, "msg": "Updated Successfully"}, status=200)

    # PATCH (Status Toggle)
    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = MainCategorySerializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"status": True, "msg": "Updated Successfully"}, status=200)

    # DELETE (Soft Delete)
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.is_delete = True
        instance.is_active = False
        instance.save(update_fields=["is_delete", "is_active"])
        return Response({"status": True, "msg": "Deleted Successfully"}, status=200)
