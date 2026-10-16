from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from app.models.core_modules.daily_operations.daily_service_notice import DailyServiceNotice
from app.models.core_modules.daily_operations.daily_trip_assignment import DailyTripAssignment
from app.models.core_modules.daily_operations.daily_trip_collection_point import DailyTripCollectionPoint
from app.models.core_modules.daily_operations.daily_trip_household_collection import DailyTripHouseholdCollection
from app.models.core_modules.notifications.staff_notification import StaffNotification
from app.models.core_modules.schedule_setup.staff_template import StaffTemplate
from app.models.core_modules.schedule_setup.trip_plan import TripPlan
from app.models.core_modules.schedule_setup.trip_plan_collection_point import TripPlanCollectionPoint
from app.models.masters.customer_masters.customercreation import CustomerCreation
from app.models.superadmin.staff_management.staffcreation import StaffcreationOfficeDetails
from app.services.push_notification_service import send_push_to_customer
from app.services.staff_notification_service import notify_staff


class DailyServiceNoticeError(Exception):
    pass


def serialize_notice(notice):
    if notice is None:
        return None
    plan = TripPlan.objects.filter(unique_id=notice.trip_plan_id).first()
    return {
        "unique_id": notice.unique_id,
        "trip_plan_id": notice.trip_plan_id,
        "trip_plan_code": getattr(plan, "display_code", notice.trip_plan_id),
        "service_date": notice.service_date.isoformat(),
        "status": notice.status,
        "reason_code": notice.reason_code,
        "reason_label": notice.get_reason_code_display(),
        "reason_text": notice.reason_text,
        "staff_recipient_count": len(notice.recipient_staff_ids or []),
        "customer_recipient_count": len(notice.recipient_customer_ids or []),
        "staff_notified_count": notice.staff_notified_count,
        "customer_notified_count": notice.customer_notified_count,
        "notification_failed_count": notice.notification_failed_count,
        "notified_at": notice.notified_at,
        "created_at": notice.created_at,
    }


def active_notice_for_plan(plan_id, service_date):
    return DailyServiceNotice.objects.filter(
        trip_plan_id=plan_id,
        service_date=service_date,
        status=DailyServiceNotice.STATUS_ACTIVE,
        is_deleted=False,
    ).first()


def _staff_ids(plan):
    ids = {plan.supervisor_id} if plan.supervisor_id else set()
    template = StaffTemplate.objects.filter(
        unique_id=plan.staff_template_id, is_deleted=False
    ).first()
    if template:
        ids.update(
            value
            for value in [template.driver_id, template.operator_id]
            if value
        )
        ids.update(value for value in (template.extra_operator_id or []) if value)
    return sorted(ids)


def _customer_ids(plan):
    if plan.collection_type not in {
        TripPlan.COLLECTION_TYPE_HOUSEHOLD,
        TripPlan.COLLECTION_TYPE_BULK,
    }:
        return []

    stops = TripPlanCollectionPoint.objects.filter(
        trip_plan_id=plan.unique_id,
        collection_type=plan.collection_type,
        is_active=True,
        is_deleted=False,
    )
    direct_ids = set(stops.exclude(customer_id__isnull=True).exclude(customer_id="").values_list("customer_id", flat=True))
    scope = Q()
    has_scope = False
    for stop in stops.filter(Q(customer_id__isnull=True) | Q(customer_id="")):
        clause = Q(company_id=plan.company_id, project_id=plan.project_id)
        if stop.ward_id:
            clause &= Q(ward_id=stop.ward_id)
        elif stop.panchayat_id:
            clause &= Q(panchayat_id=stop.panchayat_id)
        elif stop.zone_id:
            clause &= Q(zone_id=stop.zone_id)
        else:
            continue
        scope |= clause
        has_scope = True
    if has_scope:
        direct_ids.update(
            CustomerCreation.objects.filter(scope, is_deleted=False, is_active=True)
            .values_list("unique_id", flat=True)
        )
    return sorted(direct_ids)


def _has_collection_activity(assignments):
    ids = list(assignments.values_list("unique_id", flat=True))
    if not ids:
        return False
    return (
        DailyTripCollectionPoint.objects.filter(
            trip_assignment_id__in=ids, is_deleted=False, is_collected=True
        ).exists()
        or DailyTripHouseholdCollection.objects.filter(
            trip_assignment_id__in=ids, is_deleted=False, is_collected=True
        ).exists()
    )


def _dispatch_notice(notice_id):
    notice = DailyServiceNotice.objects.filter(unique_id=notice_id).first()
    if not notice or notice.status != DailyServiceNotice.STATUS_ACTIVE:
        return
    title = "No collection today"
    detail = notice.reason_text.strip() or notice.get_reason_code_display()
    body = f"Collection will not take place today due to {detail.lower()}."
    data = {
        "type": StaffNotification.TYPE_NO_COLLECTION_TODAY,
        "notice_id": notice.unique_id,
        "trip_plan_id": notice.trip_plan_id,
        "service_date": notice.service_date.isoformat(),
    }
    staff_sent = customer_sent = failed = 0
    for staff in StaffcreationOfficeDetails.objects.filter(
        staff_unique_id__in=notice.recipient_staff_ids,
        is_deleted=False,
        is_active=True,
    ):
        notification = notify_staff(
            staff,
            StaffNotification.TYPE_NO_COLLECTION_TODAY,
            title,
            body,
            data=data,
        )
        if notification:
            staff_sent += 1
        else:
            failed += 1
    for customer in CustomerCreation.objects.filter(
        unique_id__in=notice.recipient_customer_ids,
        is_deleted=False,
        is_active=True,
    ):
        if send_push_to_customer(customer, title, body, data=data):
            customer_sent += 1
        else:
            failed += 1
    DailyServiceNotice.objects.filter(unique_id=notice_id).update(
        staff_notified_count=staff_sent,
        customer_notified_count=customer_sent,
        notification_failed_count=failed,
        notified_at=timezone.now(),
    )


def _dispatch_restoration(notice_id):
    notice = DailyServiceNotice.objects.filter(unique_id=notice_id).first()
    if not notice or notice.status != DailyServiceNotice.STATUS_REVOKED:
        return
    title = "Collection restored today"
    body = "The earlier no-collection update has been withdrawn. Please check today's trip status."
    data = {
        "type": StaffNotification.TYPE_COLLECTION_RESTORED,
        "notice_id": notice.unique_id,
        "trip_plan_id": notice.trip_plan_id,
        "service_date": notice.service_date.isoformat(),
    }
    for staff in StaffcreationOfficeDetails.objects.filter(
        staff_unique_id__in=notice.recipient_staff_ids,
        is_deleted=False,
        is_active=True,
    ):
        notify_staff(
            staff,
            StaffNotification.TYPE_COLLECTION_RESTORED,
            title,
            body,
            data=data,
        )
    for customer in CustomerCreation.objects.filter(
        unique_id__in=notice.recipient_customer_ids,
        is_deleted=False,
        is_active=True,
    ):
        send_push_to_customer(customer, title, body, data=data)


@transaction.atomic
def declare_no_collection(plan, service_date, reason_code, reason_text, actor_id=None):
    plan = TripPlan.objects.select_for_update().get(unique_id=plan.unique_id)
    if reason_code not in dict(DailyServiceNotice.REASON_CHOICES):
        raise DailyServiceNoticeError("Choose a valid no-collection reason.")
    reason_text = (reason_text or "").strip()
    if reason_code == DailyServiceNotice.REASON_OTHER and not reason_text:
        raise DailyServiceNoticeError("Add a short explanation for Other.")

    existing = DailyServiceNotice.objects.select_for_update().filter(
        trip_plan_id=plan.unique_id,
        service_date=service_date,
        status=DailyServiceNotice.STATUS_ACTIVE,
        is_deleted=False,
    ).first()
    if existing:
        return existing

    assignments = DailyTripAssignment.objects.select_for_update().filter(
        trip_plan_id=plan.unique_id,
        trip_date=service_date,
        is_deleted=False,
    )
    if assignments.filter(
        status__in=[
            DailyTripAssignment.STATUS_IN_PROGRESS,
            DailyTripAssignment.STATUS_COMPLETED,
        ]
    ).exists() or _has_collection_activity(assignments):
        raise DailyServiceNoticeError(
            "Collection has already started for this trip. Report a delay or operational incident instead."
        )

    assignments.filter(status=DailyTripAssignment.STATUS_SCHEDULED).update(
        status=DailyTripAssignment.STATUS_CANCELLED,
        remarks=f"No collection today: {reason_text or dict(DailyServiceNotice.REASON_CHOICES)[reason_code]}",
        updated_by_id=actor_id,
    )
    staff_ids = _staff_ids(plan)
    customer_ids = _customer_ids(plan)
    notice, _ = DailyServiceNotice.objects.update_or_create(
        trip_plan_id=plan.unique_id,
        service_date=service_date,
        defaults={
            "company_id": plan.company_id,
            "project_id": plan.project_id,
            "supervisor_id": plan.supervisor_id,
            "status": DailyServiceNotice.STATUS_ACTIVE,
            "reason_code": reason_code,
            "reason_text": reason_text,
            "recipient_staff_ids": staff_ids,
            "recipient_customer_ids": customer_ids,
            "staff_notified_count": 0,
            "customer_notified_count": 0,
            "notification_failed_count": 0,
            "notified_at": None,
            "revoked_at": None,
            "revoked_by_id": None,
            "revoked_reason": "",
            "created_by_id": actor_id,
            "updated_by_id": actor_id,
            "is_deleted": False,
            "is_active": True,
        },
    )
    transaction.on_commit(lambda: _dispatch_notice(notice.unique_id))
    return notice


@transaction.atomic
def revoke_no_collection(notice, actor_id=None, reason=""):
    notice = DailyServiceNotice.objects.select_for_update().get(unique_id=notice.unique_id)
    if notice.status != DailyServiceNotice.STATUS_ACTIVE:
        raise DailyServiceNoticeError("This notice is already inactive.")
    notice.status = DailyServiceNotice.STATUS_REVOKED
    notice.revoked_at = timezone.now()
    notice.revoked_by_id = actor_id
    notice.revoked_reason = (reason or "").strip()
    notice.updated_by_id = actor_id
    notice.save(update_fields=["status", "revoked_at", "revoked_by_id", "revoked_reason", "updated_by_id", "updated_at"])
    DailyTripAssignment.objects.filter(
        trip_plan_id=notice.trip_plan_id,
        trip_date=notice.service_date,
        status=DailyTripAssignment.STATUS_CANCELLED,
        remarks__startswith="No collection today:",
        is_deleted=False,
    ).update(
        status=DailyTripAssignment.STATUS_SCHEDULED,
        remarks=f"Service restored: {notice.revoked_reason or 'No-collection notice withdrawn'}",
        updated_by_id=actor_id,
    )
    transaction.on_commit(lambda: _dispatch_restoration(notice.unique_id))
    return notice


def notice_for_customer(customer, service_date):
    customer_id = getattr(customer, "unique_id", None)
    if not customer_id:
        return None
    notices = DailyServiceNotice.objects.filter(
        service_date=service_date,
        status=DailyServiceNotice.STATUS_ACTIVE,
        is_deleted=False,
    ).order_by("-created_at")
    return next(
        (notice for notice in notices if customer_id in (notice.recipient_customer_ids or [])),
        None,
    )


def notices_for_staff(staff, service_date):
    staff_id = getattr(staff, "staff_unique_id", None)
    if not staff_id:
        return DailyServiceNotice.objects.none()
    notices = DailyServiceNotice.objects.filter(
        service_date=service_date,
        status=DailyServiceNotice.STATUS_ACTIVE,
        is_deleted=False,
    ).order_by("created_at")
    return [notice for notice in notices if staff_id in (notice.recipient_staff_ids or [])]
