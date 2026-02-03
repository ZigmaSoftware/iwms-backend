from django.db.models import F

from api.management.commands.seeders.base import BaseSeeder
from api.apps.mainscreentype import MainScreenType
from api.apps.userscreenaction import UserScreenAction
from api.apps.mainscreen import MainScreen
from api.apps.userscreen import UserScreen
from api.apps.companyuserscreenpermission import CompanyUserScreenPermission
from api.apps.userType import UserType
from api.apps.staffUserType import StaffUserType
from api.apps.company import Company


class PermissionSeeder(BaseSeeder):
    name = "permission_full"

    def run(self):
        # --------------------------------------------------
        # 0. COMPANIES
        # --------------------------------------------------
        companies = Company.objects.filter(is_deleted=False)

        if not companies.exists():
            self.log("❌ No companies found. Seed companies first.")
            return

        # --------------------------------------------------
        # 1. MAIN SCREEN TYPE
        # --------------------------------------------------
        megamenu, _ = MainScreenType.objects.get_or_create(
            type_name="megamenu",
            defaults={"is_active": True, "is_deleted": False},
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
                },
            )
            actions[name] = action

        # --------------------------------------------------
        # 3. SCREENS
        # --------------------------------------------------
        screen_structure = {
            "masters": [
                "Continent", "Countries", "States", "Districts",
                "Cities", "Zones", "Wards", "Bins",
            ],
            "assets": [
                "Fuels", "Properties", "Subproperties",
                "ZonePropertyLoadTracker",
            ],
            "role-assign": [
                "UserType", "StaffUserTypes",
            ],
            "user-creation": [
                "UsersCreation", "StaffCreation",
                "StaffTemplateCreation", "AlternativeStaffTemplate",
                "StaffTemplateAuditLog", "RoutePlan",
                "SupervisorZoneMap", "SupervisorZoneAccessAudit",
                "UnassignedStaffPool",
            ],
            "customers": [
                "Customercreations", "Wastecollections",
                "Feedbacks", "Complaints",
            ],
            "vehicles": [
                "VehicleType", "VehicleCreation", "TripDefinition",
                "BinLoadLog", "TripInstance", "TripAttendance",
                "VehicleTripAudit", "TripExceptionLog",
            ],
            "grievance": [
                "MainCategory", "SubCategory",
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
                },
            )
            mainscreens[main_name] = main

            UserScreen.objects.filter(mainscreen_id=main).update(
                order_no=F("order_no") + 1000
            )

            ordered = []
            for idx, screen_name in enumerate(screens, start=1):
                screen, _ = UserScreen.objects.get_or_create(
                    userscreen_name=screen_name,
                    defaults={
                        "mainscreen_id": main,
                        "folder_name": screen_name.lower(),
                        "icon_name": screen_name.lower(),
                        "order_no": idx,
                        "is_active": True,
                        "is_deleted": False,
                    },
                )
                ordered.append(screen)

            for idx, screen in enumerate(ordered, start=1):
                screen.order_no = idx
                screen.is_active = True
                screen.is_deleted = False
                screen.save(update_fields=["order_no", "is_active", "is_deleted"])

        # --------------------------------------------------
        # 4. ROLES
        # --------------------------------------------------
        staff_type = UserType.objects.get(name__iexact="staff")

        admin_role = StaffUserType.objects.get(name="admin", usertype_id=staff_type)
        driver_role = StaffUserType.objects.get(name="driver", usertype_id=staff_type)
        operator_role = StaffUserType.objects.get(name="operator", usertype_id=staff_type)
        supervisor_role = StaffUserType.objects.get(name="supervisor", usertype_id=staff_type)

        # --------------------------------------------------
        # 5. PERMISSIONS (COMPANY AWARE)
        # --------------------------------------------------
        for company in companies:
            self.log(f"🔹 Seeding permissions for company: {company.name}")

            # ADMIN → FULL ACCESS
            for main in mainscreens.values():
                for screen in UserScreen.objects.filter(mainscreen_id=main):
                    for order_no, action in enumerate(actions.values(), start=1):
                        CompanyUserScreenPermission.objects.get_or_create(
                            company_id=company,          # ✅ KEY CHANGE
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
                            },
                        )

            # LIMITED ROLES
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

            for role, modules in limited_permissions.items():
                for module_name, screens in modules.items():
                    main = mainscreens.get(module_name)
                    if not main:
                        continue

                    for screen_name, action_names in screens.items():
                        screen = UserScreen.objects.filter(
                            mainscreen_id=main,
                            userscreen_name=screen_name,
                        ).first()
                        if not screen:
                            continue

                        for order_no, action_name in enumerate(action_names, start=1):
                            action = actions.get(action_name)
                            if not action:
                                continue

                            CompanyUserScreenPermission.objects.get_or_create(
                                company_id=company,      # ✅ KEY CHANGE
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
                                },
                            )

        self.log("✅ Permission seeding completed successfully (company-wise)")
