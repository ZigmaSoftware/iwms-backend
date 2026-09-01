"""
Resolves the tenancy (company/project) and actor identity recorded on every
CommonAudit row.

Kept separate from AuditViewSetMixin so the same rules can be reused by any
non-viewset code that needs to write an audit entry.
"""


def _as_id(value):
    """FK attribute → its unique_id string, passing through plain values."""
    if value is None:
        return None
    return str(getattr(value, "unique_id", value) or "") or None


def _name_of(obj):
    return (getattr(obj, "name", None) or "").strip() or None


def is_platform_super_admin(user):
    """
    A platform super admin is a superuser with no company of their own.
    Mirrors CompanyScopedViewSet._is_platform_super_admin so the audit
    scope agrees with the access-control scope.
    """
    return bool(
        user
        and getattr(user, "is_authenticated", False)
        and getattr(user, "is_superuser", False)
        and getattr(user, "company_id", None) is None
    )


def resolve_actor(user):
    """
    (created_by_id, created_by_name, created_by_type) for the acting user.

    Both User and Staffcreation are possible request.user types here, so
    identity is probed in preference order rather than assumed.
    """
    if not user or not getattr(user, "is_authenticated", False):
        return None, "SYSTEM", "system"

    actor_id = (
        getattr(user, "staff_unique_id", None)
        or getattr(user, "unique_id", None)
        or getattr(user, "pk", None)
    )

    # Staff records carry a person's name; platform users usually only have
    # a username. Fall back through the options rather than showing blank.
    name = None
    for attr in ("full_name", "name", "staff_name"):
        name = (getattr(user, attr, None) or "").strip() or None
        if name:
            break

    if not name:
        first = (getattr(user, "first_name", "") or "").strip()
        last = (getattr(user, "last_name", "") or "").strip()
        name = f"{first} {last}".strip() or None

    if not name:
        name = (
            (getattr(user, "username", None) or "").strip()
            or (getattr(user, "email", None) or "").strip()
            or str(user)
        )

    if is_platform_super_admin(user):
        actor_type = "super_admin"
    elif getattr(user, "staff_unique_id", None):
        actor_type = "staff"
    else:
        actor_type = "user"

    return (str(actor_id) if actor_id else None), name, actor_type


def resolve_tenancy(user, instance=None):
    """
    (scope, company_id, company_name, project_id, project_name).

    The changed record is the primary source — a super admin editing a
    company's data must be filed under THAT company, not under "platform".
    The acting user's own company/project is only the fallback for records
    that carry no tenancy of their own.
    """
    from app.utils.common_audit import CommonAudit

    company = getattr(instance, "company_id", None) if instance is not None else None
    project = getattr(instance, "project_id", None) if instance is not None else None

    if company is None and user is not None:
        company = getattr(user, "company_id", None)
    if project is None and user is not None:
        project = getattr(user, "project_id", None)

    company_uid = _as_id(company)
    project_uid = _as_id(project)

    if company_uid:
        scope = CommonAudit.Scope.PROJECT if project_uid else CommonAudit.Scope.COMPANY
    else:
        # No company anywhere: a genuine platform-level action (super admin
        # managing companies, screen masters, etc).
        scope = CommonAudit.Scope.PLATFORM

    return (
        scope,
        company_uid,
        _name_of(company),
        project_uid,
        _name_of(project),
    )
