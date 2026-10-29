from django.apps import AppConfig
from django.db.backends.signals import connection_created
from django.db.models.signals import post_migrate, pre_migrate


class ApiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'app'
    
    def ready(self):
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

        # DB Change Audit: tag Django's own connections so the triggers skip
        # app writes, and rebuild the triggers around every migrate.
        from app.services.db_change_audit import (
            drop_triggers_before_migrate,
            install_triggers_after_migrate,
            mark_app_connection,
        )

        connection_created.connect(
            mark_app_connection,
            dispatch_uid="app.db_change_audit.mark_app_connection",
        )
        pre_migrate.connect(
            drop_triggers_before_migrate,
            sender=self,
            dispatch_uid="app.db_change_audit.drop_triggers_before_migrate",
        )
        post_migrate.connect(
            install_triggers_after_migrate,
            sender=self,
            dispatch_uid="app.db_change_audit.install_triggers_after_migrate",
        )
