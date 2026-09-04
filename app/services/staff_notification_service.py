"""Single choke point for a staff member's in-app notification.

Every operational event that should alert a driver/operator/supervisor
(vehicle breakdown reported/replacement approved/rejected, Re-Trip
requested/approved/rejected) should call `notify_staff` instead of creating a
`StaffNotification` directly, so every call site stays consistent if delivery
(e.g. push) is added later.
"""
from app.models.notifications.staff_notification import StaffNotification


def notify_staff(staff, notification_type, title, body, data=None):
    """Create a StaffNotification row for `staff`.

    Returns the created StaffNotification, or None if `staff` is None.
    """
    if staff is None:
        return None

    return StaffNotification.objects.create(
        recipient_staff=staff,
        notification_type=notification_type,
        title=title,
        message=body,
        data=data or {},
    )
