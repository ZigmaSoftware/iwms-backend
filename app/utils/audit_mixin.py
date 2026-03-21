from django.forms.models import model_to_dict
from app.utils.common_audit import CommonAudit
from datetime import datetime, date, time
from decimal import Decimal
from uuid import UUID


class AuditViewSetMixin:

    AUDIT_MODULE = None
    AUDIT_ENDPOINT = None


    def _serialize_instance(self, instance):
        data = model_to_dict(instance)

        for field in instance._meta.fields:
            value = getattr(instance, field.name)

            # ForeignKey → store unique_id
            if field.is_relation:
                data[field.name] = getattr(value, "unique_id", None) if value else None

            # Decimal → convert to float
            elif isinstance(value, Decimal):
                data[field.name] = float(value)

            # Datetime → convert to ISO string
            elif isinstance(value, (datetime, date, time)):
                data[field.name] = value.isoformat()

            elif isinstance(value, UUID):
                data[field.name] = str(value)

            else:
                data[field.name] = value

        return data

    def log_audit(self, request, instance=None, previous_data=None, new_data=None):

        CommonAudit.objects.create(
            module_name=self.AUDIT_MODULE,
            endpoint_name=self.AUDIT_ENDPOINT,
            method=request.method,
            object_id=getattr(instance, "unique_id", None),
            previous_data=previous_data,
            new_data=new_data,
            createdBy=str(request.user) if request.user.is_authenticated else "SYSTEM",
        )

    # CREATE
    def perform_create(self, serializer):
        super().perform_create(serializer)

        instance = serializer.instance
        new_data = self._serialize_instance(instance)

        self.log_audit(
            self.request,
            instance=instance,
            previous_data=None,
            new_data=new_data
        )

    # UPDATE
    def perform_update(self, serializer):

        instance = serializer.instance
        previous_data = self._serialize_instance(instance)

        super().perform_update(serializer)

        updated_instance = serializer.instance
        new_data = self._serialize_instance(updated_instance)

        self.log_audit(
            self.request,
            instance=updated_instance,
            previous_data=previous_data,
            new_data=new_data
        )

    # DELETE
    def perform_destroy(self, instance):

        previous_data = self._serialize_instance(instance)

        self.log_audit(
            self.request,
            instance=instance,
            previous_data=previous_data,
            new_data=None
        )

        super().perform_destroy(instance)