from rest_framework import status, viewsets

from api.utils.audit_logger import create_audit_log


AUDITED_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


class AuditLoggingMixin:
    audit_response_key = "audit_log"
    audited_methods = AUDITED_METHODS

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        try:
            self._attach_audit_trail(request, response)
        except Exception:
            # Audit logging must never block the main response path.
            pass
        return response

    def _attach_audit_trail(self, request, response):
        if request.method not in self.audited_methods:
            return

        resolver_match = getattr(request, "resolver_match", None)
        view_func = getattr(resolver_match, "func", None) if resolver_match else None
        if not view_func:
            return

        success = status.is_success(response.status_code)
        reason = None if success else self._extract_failure_reason(response)

        audit_result = create_audit_log(
            request,
            view_func,
            success=success,
            reason=reason,
        )

        if hasattr(response, "data") and isinstance(response.data, dict):
            payload = {"logged": bool(audit_result)}
            if audit_result:
                payload.update(audit_result)
            response.data[self.audit_response_key] = payload

    def _extract_failure_reason(self, response):
        data = getattr(response, "data", None)

        if isinstance(data, dict):
            detail = data.get("detail")
            if isinstance(detail, (str, bytes)):
                return detail[:255]
            return str(data)[:255]

        if data is None:
            return None

        if isinstance(data, (list, tuple)):
            return str(data[0])[:255] if data else None

        return str(data)[:255]


class AuditLoggedModelViewSet(AuditLoggingMixin, viewsets.ModelViewSet):
    """Base ModelViewSet that automatically logs create/edit/delete actions."""

    pass
