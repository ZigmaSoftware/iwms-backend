from rest_framework import viewsets, status
from rest_framework.response import Response
from app.viewsets.superadminmasters.company_scoped_viewset import CompanyScopedViewSet
from app.models.assets.bins import Bins
from app.serializers.assets.bins_serializer import BinsSerializer
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
import os
import datetime
from django.conf import settings
from app.utils.audit_mixin import AuditViewSetMixin

def save_uploaded_file(file, folder_name):
    """
    Saves uploaded file inside MEDIA_ROOT/folder_name/
    Returns relative file path to store in DB
    """

    if not file:
        return None

    # Create folder path
    upload_dir = os.path.join(settings.MEDIA_ROOT, folder_name)

    os.makedirs(upload_dir, exist_ok=True)

    original_name = file.name.replace(" ", "_")
    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S%f")
    filename = f"{timestamp}_{original_name}"

    file_path = os.path.join(upload_dir, filename)

    # Save file manually
    with open(file_path, 'wb+') as destination:
        for chunk in file.chunks():
            destination.write(chunk)

    # Return relative path (to store in DB)
    return os.path.join(folder_name, filename)



class BinsViewSet(AuditViewSetMixin,CompanyScopedViewSet):

    parser_classes = (MultiPartParser, FormParser, JSONParser)

    serializer_class = BinsSerializer
    lookup_field = "unique_id"

    permission_resource = "Bins"

    AUDIT_MODULE = "bp-palakkad"
    AUDIT_ENDPOINT ="bins"

    def create(self, request, *args, **kwargs):

        data = request.data.copy()

        image_file = request.FILES.get("bin_image")

        if image_file:
            image_path = save_uploaded_file(image_file, "bins")
            data["bin_image"] = image_path

        qr_file = request.FILES.get("bin_qr")
        if qr_file:
            qr_path = save_uploaded_file(qr_file, "bins/qr")
            data["bin_qr"] = qr_path

        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        
        return Response(serializer.data, status=201)
    
    def get_queryset(self):
        return Bins.objects.filter(is_deleted=False)
    
    def perform_destroy(self, instance):
        instance.delete()