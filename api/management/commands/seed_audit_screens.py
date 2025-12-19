from django.core.management.base import BaseCommand
from django.db import transaction

from api.apps.mainscreentype import MainScreenType
from api.apps.mainscreen import MainScreen
from api.apps.userscreen import UserScreen
from api.apps.userscreenaction import UserScreenAction


DEFAULT_MAINSCREEN_TYPE = "Desktop"

AUDIT_MODULES = [
    "masters",
    "assets",
    "role-assign",
    "user-creation",
    "customers",
    "vehicles",
]

MODULE_SCREEN_CONFIG = {
    "masters": [
        "continents",
        "countries",
        "states",
        "districts",
        "cities",
        "zones",
        "wards",
    ],
    "assets": [
        "fuels",
        "properties",
        "subproperties",
    ],
    "role-assign": [
        "user-type",
        "staffusertypes",
    ],
    "user-creation": [
        "users-creation",
        "staffcreation",
    ],
    "customers": [
        "customercreations",
        "wastecollections",
        "feedbacks",
        "complaints",
    ],
    "vehicles": [
        "vehicle-type",
        "vehicle-creation",
    ],
}

DEFAULT_ACTIONS = [
    ("Add", "add"),
    ("Edit", "edit"),
    ("Delete", "delete"),
    ("View", "view"),
]


class Command(BaseCommand):
    help = "Ensure MainScreen/UserScreen/UserScreenAction rows exist for audit logging."

    @transaction.atomic
    def handle(self, *args, **options):
        mainscreen_type = self._get_or_create_mainscreen_type()
        self.stdout.write(self.style.SUCCESS(f"Main screen type ⇒ {mainscreen_type.type_name}"))

        for order, module in enumerate(AUDIT_MODULES, start=1):
            resources = MODULE_SCREEN_CONFIG.get(module, [])
            if not resources:
                continue

            mainscreen = self._get_or_create_mainscreen(
                mainscreen_type=mainscreen_type,
                module=module,
                order=order,
            )
            self.stdout.write(self.style.SUCCESS(f"Main screen ready ⇒ {mainscreen.mainscreen_name}"))

            self._ensure_user_screens(mainscreen, resources, order)

        self._ensure_actions()
        self.stdout.write(self.style.SUCCESS("Audit screen scaffolding complete."))

    # ------------------------------------------------------------------
    # MainScreenType helper
    # ------------------------------------------------------------------
    def _get_or_create_mainscreen_type(self):
        type_obj, _ = MainScreenType.objects.get_or_create(
            type_name=DEFAULT_MAINSCREEN_TYPE,
            defaults={
                "is_active": True,
                "is_deleted": False,
            },
        )
        return type_obj

    # ------------------------------------------------------------------
    # MainScreen helper
    # ------------------------------------------------------------------
    def _get_or_create_mainscreen(self, *, mainscreen_type, module, order):
        name = module.replace("-", " ").title()

        mainscreen, created = MainScreen.objects.get_or_create(
            mainscreen_name=name,
            defaults={
                "mainscreentype_id": mainscreen_type,
                "icon_name": f"icon-{module}",
                "order_no": order * 10,
                "description": f"Auto-generated main screen for {name}",
                "is_active": True,
                "is_deleted": False,
            },
        )

        if not created and mainscreen.mainscreentype_id_id != mainscreen_type.unique_id:
            mainscreen.mainscreentype_id = mainscreen_type
            mainscreen.save(update_fields=["mainscreentype_id"])

        return mainscreen

    # ------------------------------------------------------------------
    # UserScreen helper
    # ------------------------------------------------------------------
    def _ensure_user_screens(self, mainscreen, resources, module_order):
        for offset, slug in enumerate(resources, start=1):
            label = slug.replace("-", " ").replace("_", " ").title()
            defaults = {
                "mainscreen_id": mainscreen,
                "userscreen_name": label,
                "folder_name": slug,
                "icon_name": f"icon-{slug}",
                "order_no": module_order * 100 + offset,
                "description": f"{label} screen",
                "is_active": True,
                "is_deleted": False,
            }

            userscreen, created = UserScreen.objects.get_or_create(
                folder_name=slug,
                defaults=defaults,
            )

            if not created:
                updated = False
                if userscreen.mainscreen_id_id != mainscreen.unique_id:
                    userscreen.mainscreen_id = mainscreen
                    updated = True

                if userscreen.userscreen_name != label:
                    userscreen.userscreen_name = label
                    updated = True

                if updated:
                    userscreen.save(update_fields=["mainscreen_id", "userscreen_name"])

            self.stdout.write(
                f"  - Screen {'created' if created else 'checked'} ⇒ {label}"
            )

    # ------------------------------------------------------------------
    # UserScreenAction helper
    # ------------------------------------------------------------------
    def _ensure_actions(self):
        for name, variable in DEFAULT_ACTIONS:
            action, created = UserScreenAction.objects.get_or_create(
                variable_name=variable,
                defaults={
                    "action_name": name,
                    "is_active": True,
                    "is_deleted": False,
                },
            )

            if not created and action.action_name != name:
                action.action_name = name
                action.save(update_fields=["action_name"])

            self.stdout.write(
                f"Action {'created' if created else 'checked'} ⇒ {name}"
            )
