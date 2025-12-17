from django.dispatch import receiver
from django.contrib.auth.signals import user_logged_in, user_login_failed
from api.models import LoginAudit


@receiver(user_logged_in)
def log_login_success(sender, request, user, **kwargs):
    LoginAudit.objects.create(
        user_unique_id=user.unique_id,
        username=user.username,
        ip_address=getattr(request, "ip_address", ""),
        user_agent=getattr(request, "user_agent", ""),
        success=True,
        reason=None,
    )


@receiver(user_login_failed)
def log_login_failure(sender, credentials, request, **kwargs):
    LoginAudit.objects.create(
        user_unique_id=None,
        username=credentials.get("username", ""),
        ip_address=getattr(request, "ip_address", ""),
        user_agent=getattr(request, "user_agent", ""),
        success=False,
        reason="Invalid credentials",
    )
