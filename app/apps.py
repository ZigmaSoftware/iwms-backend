from django.apps import AppConfig
from django.db.models.signals import post_migrate


class ApiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'app'
    
    def ready(self):
        # Registers the CompanyUserScreenPermission receivers that write
        # PermissionAuditLog. Nothing else imports this module, so without it
        # the permission audit trail is never written.
        import app.signals.permission_signals  # noqa: F401

        from app.services.daily_trip_scheduler import start_daily_trip_scheduler

        start_daily_trip_scheduler()

        def sync_userscreen_columns_after_migrate(sender, **kwargs):
            if sender.name != self.name:
                return
            try:
                from app.services.schema_sync_service import sync_all_screens
                sync_all_screens()
            except Exception:
                pass

        post_migrate.connect(
            sync_userscreen_columns_after_migrate,
            sender=self,
            dispatch_uid="app.sync_userscreen_columns_after_migrate",
        )
