# =========================================================
# services/schema_sync_service.py
# =========================================================

from django.apps import apps
from django.db import models, transaction
from django.db.models import ForeignKey

from app.models.screen_managements.userscreencolumn import UserScreenColumn


# =========================================================
# IGNORE SYSTEM DJANGO FIELDS
# =========================================================

SYSTEM_FIELDS = {
    "id",
    "pk",
}


# =========================================================
# MAIN SYNC FUNCTION
# =========================================================

@transaction.atomic
def sync_screen_columns(userscreen):
    """
    Sync UserScreenColumn records with the actual Django model fields.
    Auto-detects schema changes and updates columns accordingly.

    Args:
        userscreen: UserScreen instance with model_app_label and model_name

    Returns:
        list: List of created/updated UserScreenColumn instances
    """

    print("===================================")
    print("SYNC SCREEN COLUMNS STARTED")
    print("===================================")

    print("USERSCREEN:", userscreen.userscreen_name)
    print("APP LABEL:", userscreen.model_app_label)
    print("MODEL NAME:", userscreen.model_name)

    # =====================================================
    # VALIDATE USERSCREEN CONFIGURATION
    # =====================================================

    if not userscreen.model_app_label or not userscreen.model_name:
        print("ERROR: UserScreen missing model_app_label or model_name")
        return []

    # =====================================================
    # LOAD DJANGO MODEL
    # =====================================================

    try:
        model_class = apps.get_model(
            userscreen.model_app_label,
            userscreen.model_name
        )
        print("MODEL CLASS FOUND:", model_class)

    except LookupError as e:
        print("MODEL LOOKUP FAILED:", str(e))
        return []

    # =====================================================
    # GET DJANGO MODEL FIELDS
    # =====================================================

    django_fields = model_class._meta.get_fields()
    print("TOTAL FIELDS:", len(django_fields))

    created_or_updated = []

    # =====================================================
    # EXISTING COLUMNS
    # =====================================================

    existing_columns = {
        obj.column_name: obj
        for obj in UserScreenColumn.objects.filter(
            userscreen_id=userscreen,
            is_deleted=False
        )
    }

    incoming_columns = set()
    order_no = 1

    # =====================================================
    # LOOP DJANGO FIELDS
    # =====================================================

    for field in django_fields:
        print("-----------------------------------")
        print("FIELD:", field.name)

        # =================================================
        # SKIP REVERSE RELATIONS
        # =================================================

        if field.auto_created and not field.concrete:
            print("SKIPPED REVERSE RELATION")
            continue

        # =================================================
        # SKIP SYSTEM FIELDS
        # =================================================

        if field.name in SYSTEM_FIELDS:
            print("SKIPPED SYSTEM FIELD")
            continue

        incoming_columns.add(field.name)

        # =================================================
        # FIELD METADATA
        # =================================================

        data = {
            "verbose_name": str(field.verbose_name),
            "data_type": field.get_internal_type(),
            "max_length": getattr(field, "max_length", None),
            "default_value": (
                str(field.default)
                if field.default is not None
                and field.default != models.NOT_PROVIDED
                else None
            ),
            "is_required": (
                not field.null
                and not field.blank
            ),
            "is_nullable": field.null,
            "is_unique": field.unique,
            "is_primary_key": field.primary_key,
            "is_foreign_key": isinstance(field, ForeignKey),
            "is_visible": True,
            "is_editable": field.editable,
            "is_filterable": True,
            "is_searchable": (
                field.get_internal_type() in [
                    "CharField",
                    "TextField",
                    "EmailField",
                    "URLField",
                    "SlugField"
                ]
            ),
            "is_sortable": True,
            "order_no": order_no,
        }

        # =================================================
        # FOREIGN KEY DETAILS
        # =================================================

        if isinstance(field, ForeignKey):
            related_model = field.related_model
            data["related_model"] = related_model.__name__
            data["related_app"] = related_model._meta.app_label

        # =================================================
        # UPDATE EXISTING
        # =================================================

        obj = existing_columns.get(field.name)

        if obj:
            print("UPDATING COLUMN:", field.name)

            # Check if any field has changed
            has_changes = False
            for key, value in data.items():
                if getattr(obj, key) != value:
                    has_changes = True
                    break

            if has_changes:
                for key, value in data.items():
                    setattr(obj, key, value)

                obj.is_deleted = False
                obj.is_active = True
                obj.save()
                created_or_updated.append(obj)
            else:
                created_or_updated.append(obj)  # Still include in result

        # =================================================
        # CREATE NEW
        # =================================================

        else:
            print("CREATING COLUMN:", field.name)

            obj = UserScreenColumn.objects.create(
                userscreen_id=userscreen,
                column_name=field.name,
                **data
            )

            created_or_updated.append(obj)

        order_no += 1

    # =====================================================
    # SOFT DELETE REMOVED COLUMNS
    # =====================================================

    for column_name, obj in existing_columns.items():
        if column_name not in incoming_columns:
            print("SOFT DELETING:", column_name)

            obj.is_deleted = True
            obj.is_active = False
            obj.save(
                update_fields=[
                    "is_deleted",
                    "is_active"
                ]
            )

    print("===================================")
    print("SYNC COMPLETED")
    print("TOTAL:", len(created_or_updated))
    print("===================================")

    return created_or_updated


# =========================================================
# BATCH SYNC UTILITY
# =========================================================

@transaction.atomic
def sync_all_screens():
    """
    Sync all UserScreens that have model mappings configured.
    Useful for initial setup or bulk schema updates.

    Returns:
        dict: Summary of sync results
    """
    from app.models.screen_managements.userscreen import UserScreen

    results = {
        "total_screens": 0,
        "successful_syncs": 0,
        "failed_syncs": 0,
        "errors": []
    }

    screens = UserScreen.objects.filter(
        is_deleted=False,
        model_app_label__isnull=False,
        model_name__isnull=False
    ).exclude(
        model_app_label="",
        model_name=""
    )

    results["total_screens"] = screens.count()

    for screen in screens:
        try:
            synced_columns = sync_screen_columns(screen)
            if synced_columns is not None:
                results["successful_syncs"] += 1
            else:
                results["failed_syncs"] += 1
                results["errors"].append(f"Failed to sync {screen.userscreen_name}")

        except Exception as e:
            results["failed_syncs"] += 1
            results["errors"].append(f"Error syncing {screen.userscreen_name}: {str(e)}")

    return results


# =========================================================
# DETECT SCHEMA CHANGES
# =========================================================

def detect_schema_changes(userscreen):
    """
    Detect if there are any changes between the UserScreen's columns
    and the actual Django model schema.

    Returns:
        dict: Changes detected with details
    """
    changes = {
        "has_changes": False,
        "added_fields": [],
        "removed_fields": [],
        "modified_fields": []
    }

    if not userscreen.model_app_label or not userscreen.model_name:
        return changes

    try:
        model_class = apps.get_model(
            userscreen.model_app_label,
            userscreen.model_name
        )
    except LookupError:
        return changes

    # Get current Django fields
    django_fields = set()
    for field in model_class._meta.get_fields():
        if field.concrete and not field.auto_created and field.name not in SYSTEM_FIELDS:
            django_fields.add(field.name)

    # Get existing screen columns
    screen_columns = set(
        UserScreenColumn.objects.filter(
            userscreen_id=userscreen,
            is_deleted=False
        ).values_list("column_name", flat=True)
    )

    # Detect changes
    added = django_fields - screen_columns
    removed = screen_columns - django_fields

    if added or removed:
        changes["has_changes"] = True
        changes["added_fields"] = list(added)
        changes["removed_fields"] = list(removed)

    return changes</content>
<parameter name="filePath">iwms-backend/app/services/schema_sync_service.py