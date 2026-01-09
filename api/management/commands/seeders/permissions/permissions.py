# api/management/commands/seeders/permission_seeder.py

from django.db.models import F

from api.management.commands.seeders.base import BaseSeeder
from api.apps.mainscreentype import MainScreenType
from api.apps.userscreenaction import UserScreenAction
from api.apps.mainscreen import MainScreen
from api.apps.userscreen import UserScreen
from api.apps.userscreenpermission import UserScreenPermission
from api.apps.userType import UserType
from api.apps.staffUserType import StaffUserType


class PermissionSeeder(BaseSeeder):
    name = "permission_full"

    def run(self):
        # --------------------------------------------------
        # 1. MAIN SCREEN TYPE
        # --------------------------------------------------
        megamenu, _ = MainScreenType.objects.get_or_create(
            type_name="megamenu",
            defaults={"is_active": True, "is_deleted": False}
        )

        # --------------------------------------------------
        # 2. ACTIONS
        # --------------------------------------------------
        actions = {}
        for name in ["add", "view", "edit", "delete"]:
            action, _ = UserScreenAction.objects.get_or_create(
                action_name=name,
                defaults={
                    "variable_name": name,
                    "is_active": True,
                    "is_deleted": False,
                }
            )
            actions[name] = action

        # --------------------------------------------------
        # 3. SCREENS (MATCH VIEWSET NAMES EXACTLY)
        # --------------------------------------------------
        screen_structure = {
            "masters": [
                "Continent",
                "Countries",
                "States",
                "Districts",
                "Cities",
                "Zones",
                "Wards",
                "Bins",
            ],
            "assets": [
                "Fuels",
                "Properties",
                "Subproperties",
                "ZonePropertyLoadTracker",
            ],
            "role-assign": [
                "UserType",
                "StaffUserTypes",
            ],
            "user-creation": [
                "UsersCreation",
                "StaffCreation",
                "StaffTemplateCreation",
                "AlternativeStaffTemplate",
                "StaffTemplateAuditLog",
                "RoutePlan",
                "SupervisorZoneMap",
                "SupervisorZoneAccessAudit",
            ],
            "customers": [
                "Customercreations",
                "Wastecollections",
                "Feedbacks",
                "Complaints",
                "CustomerTag",
                "HouseholdPickupEvent",
            ],
            "vehicles": [
                "VehicleType",
                "VehicleCreation",
                "TripDefinition",
                "BinLoadLog",
            ],
            "grievance": [
                "MainCategory",
                "SubCategory",
            ],
        }

        mainscreens = {}

        for order, (main_name, screens) in enumerate(screen_structure.items(), start=1):
            main, _ = MainScreen.objects.get_or_create(
                mainscreen_name=main_name,
                defaults={
                    "mainscreentype_id": megamenu,
                    "icon_name": main_name,
                    "order_no": order,
                    "is_active": True,
                    "is_deleted": False,
                }
            )
            mainscreens[main_name] = main

            # Avoid unique_order_per_mainscreen conflicts while creating new screens.
            order_offset = 1000
            UserScreen.objects.filter(mainscreen_id=main).update(
                order_no=F("order_no") + order_offset
            )

            ordered_screens = []
            for idx, screen_name in enumerate(screens, start=1):
                screen, created = UserScreen.objects.get_or_create(
                    userscreen_name=screen_name,
                    defaults={
                        "mainscreen_id": main,
                        "folder_name": screen_name.lower(),
                        "icon_name": screen_name.lower(),
                        "order_no": idx,
                        "is_active": True,
                        "is_deleted": False,
                    }
                )
                if not created:
                    update_fields = []
                    desired_folder = screen_name.lower()

                    if screen.mainscreen_id_id != main.unique_id:
                        screen.mainscreen_id = main
                        update_fields.append("mainscreen_id")

                    if screen.folder_name != desired_folder:
                        screen.folder_name = desired_folder
                        update_fields.append("folder_name")

                    if screen.icon_name != desired_folder:
                        screen.icon_name = desired_folder
                        update_fields.append("icon_name")

                    if not screen.is_active or screen.is_deleted:
                        screen.is_active = True
                        screen.is_deleted = False
                        update_fields.extend(["is_active", "is_deleted"])

                    if update_fields:
                        screen.save(update_fields=update_fields)

                ordered_screens.append(screen)

            ordered_ids = []
            next_order = 1
            for screen in ordered_screens:
                screen.order_no = next_order
                screen.is_active = True
                screen.is_deleted = False
                screen.save(update_fields=["order_no", "is_active", "is_deleted"])
                ordered_ids.append(screen.unique_id)
                next_order += 1

            extra_screens = UserScreen.objects.filter(
                mainscreen_id=main
            ).exclude(unique_id__in=ordered_ids).order_by("order_no")
            for screen in extra_screens:
                screen.order_no = next_order
                screen.save(update_fields=["order_no"])
                next_order += 1

        # --------------------------------------------------
        # 4. ROLES
        # --------------------------------------------------
        staff_type = UserType.objects.get(name__iexact="staff")

        admin_role = StaffUserType.objects.get(name="admin", usertype_id=staff_type)
        driver_role = StaffUserType.objects.get(name="driver", usertype_id=staff_type)
        operator_role = StaffUserType.objects.get(name="operator", usertype_id=staff_type)
        supervisor_role = StaffUserType.objects.get(name="supervisor", usertype_id=staff_type)

        # --------------------------------------------------
        # 5. ADMIN → FULL ACCESS
        # --------------------------------------------------
        for main in mainscreens.values():
            screens = UserScreen.objects.filter(mainscreen_id=main)
            for screen in screens:
                for order_no, action in enumerate(actions.values(), start=1):
                    UserScreenPermission.objects.get_or_create(
                        usertype_id=staff_type,
                        staffusertype_id=admin_role,
                        mainscreen_id=main,
                        userscreen_id=screen,
                        userscreenaction_id=action,
                        defaults={
                            "order_no": order_no,
                            "description": f"{action.variable_name} {screen.userscreen_name}",
                            "is_active": True,
                            "is_deleted": False,
                        }
                    )

        # --------------------------------------------------
        # 6. LIMITED ROLES
        # --------------------------------------------------
        limited_permissions = {
            driver_role: {
                "customers": {
                    "Customercreations": ["view"],
                }
            },
            operator_role: {
                "customers": {
                    "Customercreations": ["view"],
                }
            },
            supervisor_role: {
                "vehicles": {
                    "TripDefinition": ["add", "view", "edit"],
                }
            },
        }

        # Provide full CRUD access to RoutePlan for operators and drivers by default
        for role in (driver_role, operator_role):
            limited_permissions.setdefault(role, {}).setdefault(
                "user-creation", {}
            )["RoutePlan"] = ["add", "view", "edit", "delete"]

        # Also grant view access to AlternativeStaffTemplate for operators and drivers
        for role in (driver_role, operator_role):
            limited_permissions.setdefault(role, {}).setdefault(
                "user-creation", {}
            )["AlternativeStaffTemplate"] = ["view"]

        # Operator access for household pickup events
        limited_permissions.setdefault(operator_role, {}).setdefault(
            "customers", {}
        )["HouseholdPickupEvent"] = ["add", "view", "edit", "delete"]

        # Operator access for bin load logs
        limited_permissions.setdefault(operator_role, {}).setdefault(
            "vehicles", {}
        )["BinLoadLog"] = ["add", "view", "edit"]

        # Supervisor access for zone property load tracker
        limited_permissions.setdefault(supervisor_role, {}).setdefault(
            "assets", {}
        )["ZonePropertyLoadTracker"] = ["add", "view", "edit"]

        for role, modules in limited_permissions.items():
            for module_name, screens in modules.items():
                main = mainscreens.get(module_name)
                if not main:
                    continue

                for screen_name, action_names in screens.items():
                    screen = UserScreen.objects.filter(
                        mainscreen_id=main,
                        userscreen_name=screen_name
                    ).first()
                    if not screen:
                        continue

                    for order_no, action_name in enumerate(action_names, start=1):
                        action = actions.get(action_name)
                        if not action:
                            continue

                        UserScreenPermission.objects.get_or_create(
                            usertype_id=staff_type,
                            staffusertype_id=role,
                            mainscreen_id=main,
                            userscreen_id=screen,
                            userscreenaction_id=action,
                            defaults={
                                "order_no": order_no,
                                "description": f"{action.variable_name} {screen.userscreen_name}",
                                "is_active": True,
                                "is_deleted": False,
                            }
                        )
                        

        self.log("✅ Permission seeding completed successfully")
