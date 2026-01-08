# api/management/commands/seeders/permission_seeder.py

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
                "RoutePlan",
            ],
            "customers": [
                "CustomerCreations",
                "WasteCollections",
                "Feedbacks",
                "Complaints",
            ],
            "vehicles": [
                "VehicleType",
                "VehicleCreation",
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

            for idx, screen_name in enumerate(screens, start=1):
                UserScreen.objects.get_or_create(
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

        # --------------------------------------------------
        # 4. ROLES
        # --------------------------------------------------
        staff_type = UserType.objects.get(name__iexact="staff")

        admin_role = StaffUserType.objects.get(name="admin", usertype_id=staff_type)
        driver_role = StaffUserType.objects.get(name="driver", usertype_id=staff_type)
        operator_role = StaffUserType.objects.get(name="operator", usertype_id=staff_type)

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
                    "CustomerCreations": ["view"],
                }
            },
            operator_role: {
                "customers": {
                    "CustomerCreations": ["view"],
                }
            },
        }

        # Provide view access to RoutePlan for operators and drivers by default
        for role in (driver_role, operator_role):
            limited_permissions.setdefault(role, {}).setdefault(
                "user-creation", {}
            )["RoutePlan"] = ["view"]

        # Also grant view access to AlternativeStaffTemplate for operators and drivers
        for role in (driver_role, operator_role):
            limited_permissions.setdefault(role, {}).setdefault(
                "user-creation", {}
            )["AlternativeStaffTemplate"] = ["view"]

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
