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
        # ==================================================
        # 1. MAIN SCREEN TYPE
        # ==================================================
        megamenu, _ = MainScreenType.objects.get_or_create(
            type_name="megamenu",
            defaults={"is_active": True, "is_deleted": False}
        )

        # ==================================================
        # 2. USER SCREEN ACTIONS
        # ==================================================
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

        # ==================================================
        # 3. MAIN SCREENS + USER SCREENS (YOUR DATA ONLY)
        # ==================================================
        screen_structure = {
            "masters": [
                "Continent", "Countries", "States", "Districts",
                "Cities", "Zones", "Wards"
            ],
            "assets": [
                "Fuels", "Properties", "Subproperties"
            ],
            "role-assign": [
                "UserType",
                "Staffusertypes",
                "Assignments",
                "DailyAssignments",
                "StaffAssignments",
                "CollectionLogs",
                "CitizenAssignments",
            ],
            "user-creation": [
                "UsersCreation", "Staffcreation"
            ],
            "customers": [
                "Customercreations", "Wastecollections",
                "Feedbacks", "Complaints"
            ],
            "vehicles": [
                "VehicleType", "VehicleCreation"
            ],
        }

        mainscreens = {}
        for order, (main_name, userscreens) in enumerate(screen_structure.items(), start=1):
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

            for idx, us_name in enumerate(userscreens, start=1):
                UserScreen.objects.get_or_create(
                    userscreen_name=us_name,
                    defaults={
                        "mainscreen_id": main,
                        "folder_name": us_name.lower(),
                        "icon_name": us_name.lower(),
                        "order_no": idx,
                        "is_active": True,
                        "is_deleted": False,
                    }
                )

        # ==================================================
        # 4. USER SCREEN PERMISSIONS (STAFF → ADMIN)
        # ==================================================
        staff_type = UserType.objects.get(name__iexact="staff")
        admin_role = StaffUserType.objects.get(
            name="admin",
            usertype_id=staff_type
        )

        
        for main in mainscreens.values():
            screens = UserScreen.objects.filter(mainscreen_id=main)
            for screen in screens:
                order_no = 1
                for action in actions.values():
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
                    order_no += 1

        self.log("✅ Full permission structure seeded successfully")
