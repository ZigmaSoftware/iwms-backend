import ipaddress
import logging

from django.forms.models import model_to_dict
from django.db.models.fields.files import FieldFile
from rest_framework.exceptions import ValidationError
from app.utils.common_audit import CommonAudit
from app.utils.audit_context import resolve_actor, resolve_tenancy
from app.utils.base_models import Account
from app.utils.delete_reason import (
    DELETE_REASON_FIELD,
    DELETE_REASON_MAX_LENGTH,
    read_delete_reason,
    reset_current_delete_reason,
    set_current_delete_reason,
)
from app.models.superadmin.staff_management.staffcreation import Staffcreation
from datetime import datetime, date, time
from decimal import Decimal
from uuid import UUID

logger = logging.getLogger(__name__)


def serialize_instance_for_audit(instance, redact_fields=()):
    """Standalone version of AuditViewSetMixin._serialize_instance for plain
    function-based views (e.g. mobile actions) that don't inherit the mixin."""
    data = model_to_dict(instance)

    for field in instance._meta.fields:
        value = getattr(instance, field.name)

        if field.is_relation:
            data[field.name] = getattr(value, "unique_id", None) if value else None
        elif isinstance(value, Decimal):
            data[field.name] = float(value)
        elif isinstance(value, (datetime, date, time)):
            data[field.name] = value.isoformat()
        elif isinstance(value, UUID):
            data[field.name] = str(value)
        elif isinstance(value, FieldFile):
            data[field.name] = value.name or None
        else:
            data[field.name] = value

    for field_name in redact_fields:
        if field_name in data and data[field_name]:
            data[field_name] = "[REDACTED]"

    for field in instance._meta.many_to_many:
        related_qs = getattr(instance, field.name).all()
        data[field.name] = [
            getattr(obj, "unique_id", None) or str(obj.pk)
            for obj in related_qs
        ]

    return data


def get_audit_object_id(instance):
    if instance is None:
        return None
    for field in ("unique_id", "staff_unique_id", "id", "pk"):
        value = getattr(instance, field, None)
        if value:
            return str(value)
    return None


def get_client_ip(request):
    """Client IP, or None when the header isn't a valid address — the
    column is a GenericIPAddressField, so a spoofed/garbled
    X-Forwarded-For must not be allowed to fail the audit insert."""
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    candidate = (
        forwarded_for.split(",")[0].strip()
        if forwarded_for
        else request.META.get("REMOTE_ADDR")
    )
    try:
        return str(ipaddress.ip_address(candidate)) if candidate else None
    except ValueError:
        return None


def _to_json_safe(value):
    """serializer.initial_data on a failed write can be a QueryDict holding
    uploaded files — reduce it to something a JSONField can store."""
    if value is None:
        return None
    if hasattr(value, "lists"):
        value = {
            key: (items[0] if len(items) == 1 else items)
            for key, items in value.lists()
        }
    if isinstance(value, dict):
        return {key: _to_json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_json_safe(item) for item in value]
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(getattr(value, "name", value))


def write_common_audit(
    request, *, module_name, endpoint_name, instance=None,
    previous_data=None, new_data=None, success=True, reason=None,
    delete_reason=None,
):
    """Write one CommonAudit row, resolving actor, tenancy and request
    context server-side. Shared by AuditViewSetMixin and any non-viewset
    code (function-based views, services) that needs an audit entry."""
    if request.method == "DELETE":
        delete_reason = delete_reason or read_delete_reason(request) or None
        # Lets DeleteReasonMixin skip its fallback audit row.
        request._delete_audit_logged = True

    user = getattr(request, "user", None)
    is_authenticated = getattr(user, "is_authenticated", False)

    created_by_id, created_by_name, created_by_type = resolve_actor(user)
    scope, company_uid, company_name, project_uid, project_name = resolve_tenancy(
        user, instance
    )

    return CommonAudit.objects.create(
        module_name=module_name,
        endpoint_name=endpoint_name,
        method=request.method,
        object_id=get_audit_object_id(instance),
        previous_data=previous_data,
        new_data=new_data,
        scope=scope,
        company_unique_id=company_uid,
        company_name=company_name,
        project_unique_id=project_uid,
        project_name=project_name,
        createdBy=str(user) if is_authenticated else "SYSTEM",
        created_by_id=created_by_id,
        created_by_name=created_by_name,
        created_by_type=created_by_type,
        ip_address=get_client_ip(request),
        user_agent=request.META.get("HTTP_USER_AGENT"),
        success=success,
        reason=(reason or None) and str(reason)[:255],
        delete_reason=delete_reason and str(delete_reason)[:DELETE_REASON_MAX_LENGTH],
    )


# Alias matching TN_Iwms' name for the same helper.
log_common_audit = write_common_audit


def format_audit_error(exc):
    """Render a DRF/Django validation error into a short, readable string
    for the audit `reason` column — e.g. a dropdown left empty surfaces as
    its serializer field error, not a raw exception repr."""
    detail = getattr(exc, "detail", None)
    if detail is None:
        detail = getattr(exc, "message_dict", None) or getattr(exc, "messages", None)
    if detail is None:
        return (str(exc) or exc.__class__.__name__)[:255]

    parts = []

    def _walk(node, prefix=""):
        if isinstance(node, dict):
            for key, value in node.items():
                _walk(value, f"{prefix}{key}: ")
        elif isinstance(node, (list, tuple)):
            for item in node:
                _walk(item, prefix)
        else:
            parts.append(f"{prefix}{node}")

    _walk(detail)
    message = "; ".join(parts) if parts else str(exc)
    return message[:255]


class DeleteReasonMixin:
    """Requires a `delete_reason` on every DELETE request and records it.

    - Rejects the DELETE with 400 before anything is touched when the
      reason is missing.
    - Publishes the reason for the request so cascade_soft_delete() stamps
      it on the deleted row and every cascaded child.
    - After a successful destroy, stamps the reason on the row itself (for
      destroy paths that flip is_deleted by hand instead of calling
      delete()) and writes a CommonAudit row if the destroy path didn't.
    """

    AUDIT_MODULE = None
    AUDIT_ENDPOINT = None

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if request.method != "DELETE":
            return

        reason = read_delete_reason(request)
        if not reason:
            raise ValidationError({DELETE_REASON_FIELD: ["Please enter the reason for deleting this record."]})
        if len(reason) > DELETE_REASON_MAX_LENGTH:
            raise ValidationError({
                DELETE_REASON_FIELD: [f"Ensure this field has no more than {DELETE_REASON_MAX_LENGTH} characters."]
            })
        self._delete_reason = reason
        self._delete_reason_token = set_current_delete_reason(reason)

    def dispatch(self, request, *args, **kwargs):
        try:
            return super().dispatch(request, *args, **kwargs)
        finally:
            token = getattr(self, "_delete_reason_token", None)
            if token is not None:
                reset_current_delete_reason(token)
                self._delete_reason_token = None

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        reason = getattr(self, "_delete_reason", None)
        if reason and 200 <= response.status_code < 300:
            try:
                self._record_delete_reason(request, reason)
            except Exception:
                logger.exception(
                    "Failed to record delete reason for %s", self.__class__.__name__
                )
        return response

    def _deleted_instance(self):
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
        lookup_value = self.kwargs.get(lookup_url_kwarg)
        if lookup_value is None:
            return None
        model = self.get_queryset().model
        return model._base_manager.filter(**{self.lookup_field: lookup_value}).first()

    def _record_delete_reason(self, request, reason):
        instance = self._deleted_instance()
        if instance is not None and hasattr(instance, DELETE_REASON_FIELD):
            type(instance)._base_manager.filter(pk=instance.pk).update(delete_reason=reason)
            instance.delete_reason = reason

        if not getattr(request, "_delete_audit_logged", False):
            write_common_audit(
                request,
                module_name=self.AUDIT_MODULE or self.__class__.__name__,
                endpoint_name=self.AUDIT_ENDPOINT or self.__class__.__name__,
                instance=instance,
                new_data=serialize_instance_for_audit(instance) if instance is not None else None,
                delete_reason=reason,
            )


class AuditViewSetMixin(DeleteReasonMixin):

    AUDIT_REDACT_FIELDS = set()

    def get_audit_object_id(self, instance):
        return get_audit_object_id(instance)

    def _serialize_instance(self, instance):
        return serialize_instance_for_audit(instance, self.AUDIT_REDACT_FIELDS)

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

    def log_audit(
        self, request, instance=None, previous_data=None, new_data=None,
        success=True, reason=None,
    ):
        write_common_audit(
            request,
            module_name=self.AUDIT_MODULE,
            endpoint_name=self.AUDIT_ENDPOINT,
            instance=instance,
            previous_data=previous_data,
            new_data=new_data,
            success=success,
            reason=reason,
        )

    def _log_failed_audit(self, exc, instance=None, previous_data=None, new_data=None):
        """Record a rejected create/update/delete. Never allowed to raise —
        the caller re-raises the original error, which must reach the client
        unchanged even if the audit insert itself fails."""
        try:
            self.log_audit(
                self.request,
                instance=instance,
                previous_data=previous_data,
                new_data=_to_json_safe(new_data),
                success=False,
                reason=format_audit_error(exc),
            )
        except Exception:
            logger.exception(
                "Failed to write failure CommonAudit for %s/%s",
                self.AUDIT_MODULE, self.AUDIT_ENDPOINT,
            )

    # CREATE
    def perform_create(self, serializer):
        # Defers the actual serializer.save() to the next class in the MRO
        # (e.g. CompanyScopedViewSet), which resolves company_id/project_id
        # tenancy and its own created_by/updated_by stamping. Calling
        # serializer.save() directly here — as this used to do — bypassed
        # that resolution entirely for any viewset mixing in both, silently
        # leaving company_id/project_id null on create/update.
        try:
            super().perform_create(serializer)
        except Exception as exc:
            self._log_failed_audit(
                exc, new_data=getattr(serializer, "initial_data", None)
            )
            raise

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

        try:
            super().perform_update(serializer)
        except Exception as exc:
            self._log_failed_audit(
                exc,
                instance=instance,
                previous_data=previous_data,
                new_data=getattr(serializer, "initial_data", None),
            )
            raise

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

        try:
            super().perform_destroy(instance)
        except Exception as exc:
            self._log_failed_audit(
                exc, instance=instance, previous_data=previous_data
            )
            raise

        self.log_audit(
            self.request,
            instance=instance,
            previous_data=previous_data,
            new_data=None
        )
