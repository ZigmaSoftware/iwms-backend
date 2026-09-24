from django.forms.models import model_to_dict
from django.db.models.fields.files import FieldFile
from app.utils.common_audit import CommonAudit
from app.utils.audit_context import resolve_actor, resolve_tenancy
from app.utils.base_models import Account
from app.models.superadmin.staff_management.staffcreation import Staffcreation
from datetime import datetime, date, time
from decimal import Decimal
from uuid import UUID
from django.db.models.fields.files import FieldFile


class AuditViewSetMixin:

    AUDIT_MODULE = None
    AUDIT_ENDPOINT = None
    AUDIT_REDACT_FIELDS = set()

    def get_audit_object_id(self, instance):

        possible_fields = [
            "unique_id",
            "staff_unique_id",
            "id",
            "pk",
        ]

        for field in possible_fields:
            value = getattr(instance, field, None)
            if value:
                return str(value)

        return None

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

            elif isinstance(value, FieldFile):
                data[field.name] = value.name or None

            else:
                data[field.name] = value

        for field_name in self.AUDIT_REDACT_FIELDS:
            if field_name in data and data[field_name]:
                data[field_name] = "[REDACTED]"

        # M2M fields — convert to list of unique_ids (or PKs as fallback)
        for field in instance._meta.many_to_many:
            related_qs = getattr(instance, field.name).all()
            data[field.name] = [
                getattr(obj, "unique_id", None) or str(obj.pk)
                for obj in related_qs
            ]

        return data

    def _audit_actor_id(self):
        user = getattr(self.request, "user", None)
        if not user or not getattr(user, "is_authenticated", False):
            return None

        if isinstance(user, Staffcreation):
            account, _ = Account.objects.get_or_create(staff=user)
        else:
            account, _ = Account.objects.get_or_create(user=user)
        return account.account_id

    @staticmethod
    def _model_has_field(model, field_name):
        try:
            model._meta.get_field(field_name)
        except Exception:
            return False
        return True

    def _audit_save_kwargs(self, serializer, **fields):
        model = getattr(getattr(serializer, "Meta", None), "model", None)
        if not model:
            return {}

        actor_id = self._audit_actor_id()
        if not actor_id:
            return {}

        return {
            field_name: actor_id
            for field_name, enabled in fields.items()
            if enabled and self._model_has_field(model, field_name)
        }

    def log_audit(self, request, instance=None, previous_data=None, new_data=None):

        user = getattr(request, "user", None)

        created_by_id, created_by_name, created_by_type = resolve_actor(user)
        scope, company_uid, company_name, project_uid, project_name = resolve_tenancy(
            user, instance
        )

        CommonAudit.objects.create(
            module_name=self.AUDIT_MODULE,
            endpoint_name=self.AUDIT_ENDPOINT,
            method=request.method,
            object_id=self.get_audit_object_id(instance),
            previous_data=previous_data,
            new_data=new_data,
            scope=scope,
            company_unique_id=company_uid,
            company_name=company_name,
            project_unique_id=project_uid,
            project_name=project_name,
            createdBy=str(user) if getattr(user, "is_authenticated", False) else "SYSTEM",
            created_by_id=created_by_id,
            created_by_name=created_by_name,
            created_by_type=created_by_type,
        )

    # CREATE
    def perform_create(self, serializer):
        # Defers the actual serializer.save() to the next class in the MRO
        # (e.g. CompanyScopedViewSet), which resolves company_id/project_id
        # tenancy and its own created_by/updated_by stamping. Calling
        # serializer.save() directly here — as this used to do — bypassed
        # that resolution entirely for any viewset mixing in both, silently
        # leaving company_id/project_id null on create/update.
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
