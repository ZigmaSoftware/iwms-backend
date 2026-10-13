from django.db.models import Max

from app.management.commands.seeders.base import BaseSeeder
from app.models.superadmin.screen_management.mainscreentype import MainScreenType
from app.models.superadmin.screen_management.app_module import AppModule
from app.models.superadmin.staff_management.staff_access_configuration import (
    StaffAccessConfigurationPermission,
)
from app.utils.app_feature_grants import (
    APP_MODULE_SEED,
    CITIZEN_APP_MAINSCREEN,
    CITIZEN_APP_SCREENS,
)
from app.models.superadmin.screen_management.userscreenaction import UserScreenAction
from app.utils.permission_catalog import (
    ANY_GRANT,
    INHERITS_GRANTS_FROM,
    SCREEN_ACTIONS,
    SCREEN_STRUCTURE,
    SECTION_MODULES,
    SUPERADMIN_ONLY_SCREENS,
)
from app.models.superadmin.screen_management.mainscreen import MainScreen
from app.models.superadmin.screen_management.userscreen import UserScreen
from app.models.superadmin.screen_management.companyuserscreenpermission import (
    CompanyUserScreenPermission,
)
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project

from app.models.superadmin.screen_management.userscreencolumn import UserScreenColumn
from app.models.superadmin.screen_management.companyuserscreencolumnpermission import (
    CompanyUserScreenColumnPermission,
)


class PermissionSeeder(BaseSeeder):
    name = "permission_full"

    # Blue Planet's Greater Noida project (see BluePlanetSeeder).
    NOIDA_COMPANY = "Blue Planet"
    NOIDA_PROJECT = "Blue Planet Integrated Waste Management"

    @staticmethod
    def _seedable_actions(screen_name, actions):
        """The actions a company/project catalog offers on `screen_name`:
        none for a superadmin-only screen, the catalog's `actions` when it
        names some, otherwise all of them."""
        if screen_name in SUPERADMIN_ONLY_SCREENS:
            return []
        allowed = SCREEN_ACTIONS.get(screen_name)
        if allowed is None:
            return list(actions)
        return [a for a in actions if a.action_name in allowed]

    def _grant_palakkad_project_admin_access(self):
        from app.models.superadmin.staff_management.staffcreation import Staffcreation
        from app.models.superadmin.staff_management.staff_access_configuration import (
            StaffAccessConfiguration,
            StaffAccessConfigurationPermission,
        )

        project = Project.objects.filter(name="Palakkad BP", is_deleted=False).first()
        if not project:
            return

        staff = Staffcreation.objects.filter(
            username="haripillai",
            project_id=project.unique_id if hasattr(project, 'unique_id') else project,
            is_active=True,
            is_deleted=False,
        ).first()
        if not staff:
            return

        # Runs every time, not just when the catalog is empty. Guarding on
        # "does a catalog already exist" meant a screen added later never got
        # rows for this project, so it stayed invisible in Staff Access
        # Configuration and could not be granted at all.
        active_actions = list(
            UserScreenAction.objects.filter(is_active=True, is_deleted=False)
            .order_by("unique_id")
        )
        active_screens = (
            UserScreen.objects.filter(is_active=True, is_deleted=False)
            .order_by("mainscreen_id", "order_no", "unique_id")
        )
        created = 0
        for screen in active_screens:
            screen_actions = self._seedable_actions(screen.userscreen_name, active_actions)
            for order_no, action in enumerate(screen_actions, start=1):
                _, made = CompanyUserScreenPermission.objects.get_or_create(
                    company_id=staff.company_id,
                    project_id=staff.project_id,
                    mainscreen_id=screen.mainscreen_id,
                    userscreen_id=screen.unique_id,
                    userscreenaction_id=action.unique_id if hasattr(action, 'unique_id') else action,
                    defaults={
                        "order_no": order_no,
                        "description": f"{action.variable_name} {screen.userscreen_name}",
                        "is_active": True,
                        "is_deleted": False,
                    },
                )
                created += 1 if made else 0
        if created:
            self.log(f"Palakkad BP catalog: added {created} new permission rows.")

        catalog = list(
            CompanyUserScreenPermission.objects.filter(
                company_id=staff.company_id,
                project_id=staff.project_id,
                is_active=True,
                is_deleted=False,
            )
        )
        if not catalog:
            self.log(
                "Palakkad project admin haripillai exists, but no Palakkad BP "
                "permission catalog is available yet."
            )
            return

        config, _ = StaffAccessConfiguration.objects.update_or_create(
            staff_id=staff.staff_unique_id if hasattr(staff, 'staff_unique_id') else staff,
            defaults={
                "company_id": staff.company_id,
                "is_active": True,
                "is_deleted": False,
            },
        )
        config.project_ids = staff.project_id or ""
        config.save(update_fields=["project_ids", "updated_at"])

        seen = set()
        granted = 0
        for order, entry in enumerate(catalog, start=1):
            key = (
                entry.mainscreen_id,
                entry.userscreen_id,
                entry.userscreenaction_id,
            )
            if key in seen:
                continue
            seen.add(key)

            StaffAccessConfigurationPermission.objects.update_or_create(
                staff_access_configuration_id=config.unique_id if hasattr(config, 'unique_id') else config,
                mainscreen_id=entry.mainscreen_id,
                userscreen_id=entry.userscreen_id,
                userscreenaction_id=entry.userscreenaction_id,
                defaults={
                    "order_no": order,
                    "is_active": True,
                    "is_deleted": False,
                },
            )
            granted += 1

        stale_ids = [
            perm.unique_id
            for perm in StaffAccessConfigurationPermission.objects.filter(
                staff_access_configuration_id=config.unique_id if hasattr(config, 'unique_id') else config,
            )
            if (
                perm.mainscreen_id,
                perm.userscreen_id,
                perm.userscreenaction_id,
            )
            not in seen
        ]
        if stale_ids:
            StaffAccessConfigurationPermission.objects.filter(
                unique_id__in=stale_ids
            ).delete()

        screens = len({key[1] for key in seen})
        self.log(
            f"Granted Palakkad project-admin access to haripillai: "
            f"{granted} permissions across {screens} screens."
        )

    @staticmethod
    def _copy_rows(model, rows, screen, existing_key):
        """Clone `rows` onto `screen`, skipping ones it already holds."""
        skip = {"id", "unique_id", "created_at", "updated_at"}
        fields = [
            f.name for f in model._meta.concrete_fields if f.name not in skip
        ]
        copied = 0
        for row in rows:
            values = {name: getattr(row, name) for name in fields}
            values["userscreen_id"] = screen.unique_id
            values["mainscreen_id"] = screen.mainscreen_id
            if "description" in values and values["description"]:
                action = (values["description"].split(" ", 1) + [""])[0]
                values["description"] = f"{action} {screen.userscreen_name}"
            if model.objects.filter(
                userscreen_id=screen.unique_id, **existing_key(row)
            ).exists():
                continue
            model.objects.create(**values)
            copied += 1
        return copied

    def _inherit_grants(self, screen, source_name):
        """Give a newly created screen the grants of the screen it was split
        from (catalog `inherits_grants_from`), so the split takes no access
        away. Runs only when the screen row is first created."""
        if source_name == ANY_GRANT:
            self._grant_view_to_every_holder(screen)
            return
        source = UserScreen.objects.filter(
            userscreen_name=source_name, is_deleted=False
        ).first()
        if not source:
            return

        company = self._copy_rows(
            CompanyUserScreenPermission,
            CompanyUserScreenPermission.objects.filter(
                userscreen_id=source.unique_id, is_deleted=False
            ),
            screen,
            lambda row: {
                "company_id": row.company_id,
                "project_id": row.project_id,
                "userscreenaction_id": row.userscreenaction_id,
            },
        )
        staff = self._copy_rows(
            StaffAccessConfigurationPermission,
            StaffAccessConfigurationPermission.objects.filter(
                userscreen_id=source.unique_id, is_deleted=False
            ),
            screen,
            lambda row: {
                "staff_access_configuration_id": row.staff_access_configuration_id,
                "userscreenaction_id": row.userscreenaction_id,
            },
        )
        self.log(
            f"{screen.userscreen_name}: copied {company} company and {staff} "
            f"staff grants from {source_name}."
        )

    def _grant_view_to_every_holder(self, screen):
        """`view` on `screen` for every company/project and every staff
        access configuration that holds any grant: a page that used to be
        open to every signed-in user keeps being open to them."""
        view = UserScreenAction.objects.filter(action_name="view", is_deleted=False).first()
        if not view:
            return
        company = 0
        for company_id, project_id in (
            CompanyUserScreenPermission.objects.filter(is_deleted=False)
            .exclude(userscreen_id=screen.unique_id)
            .values_list("company_id", "project_id").distinct()
        ):
            _, created = CompanyUserScreenPermission.objects.get_or_create(
                company_id=company_id,
                project_id=project_id,
                mainscreen_id=screen.mainscreen_id,
                userscreen_id=screen.unique_id,
                userscreenaction_id=view.unique_id,
                defaults={"description": f"view {screen.userscreen_name}", "order_no": 1},
            )
            company += int(created)
        staff = 0
        for config_id in (
            StaffAccessConfigurationPermission.objects.filter(is_deleted=False)
            .exclude(userscreen_id=screen.unique_id)
            .values_list("staff_access_configuration_id", flat=True).distinct()
        ):
            _, created = StaffAccessConfigurationPermission.objects.get_or_create(
                staff_access_configuration_id=config_id,
                mainscreen_id=screen.mainscreen_id,
                userscreen_id=screen.unique_id,
                userscreenaction_id=view.unique_id,
            )
            staff += int(created)
        self.log(
            f"{screen.userscreen_name}: granted view to {company} company/project "
            f"scopes and {staff} staff access configurations that hold any grant."
        )

    def _retire_unseedable_grants(self):
        """Soft-delete company and staff grants the catalog no longer offers:
        any on a superadmin-only screen, and actions outside a screen's
        `actions` (e.g. add/edit/delete on a dashboard)."""
        all_actions = list(UserScreenAction.objects.filter(is_deleted=False))
        retired = 0
        for screen in UserScreen.objects.filter(
            userscreen_name__in=set(SCREEN_ACTIONS) | SUPERADMIN_ONLY_SCREENS,
            is_deleted=False,
        ):
            keep = {
                a.unique_id
                for a in self._seedable_actions(screen.userscreen_name, all_actions)
            }
            for model in (CompanyUserScreenPermission, StaffAccessConfigurationPermission):
                retired += (
                    model.objects.filter(userscreen_id=screen.unique_id, is_deleted=False)
                    .exclude(userscreenaction_id__in=keep)
                    .update(is_active=False, is_deleted=True)
                )
        if retired:
            self.log(f"Retired {retired} grants the permission catalog does not offer.")

    def _grant_noida_admin_dashboard(self):
        """`view` on the Admin Dashboard for the Greater Noida project's
        catalog and every staff access configuration scoped to it."""
        from app.models.superadmin.staff_management.staff_access_configuration import (
            StaffAccessConfiguration,
        )

        company = Company.objects.filter(name=self.NOIDA_COMPANY, is_deleted=False).first()
        project = company and Project.objects.filter(
            company_id=company.unique_id, name=self.NOIDA_PROJECT, is_deleted=False,
        ).first()
        screen = UserScreen.objects.filter(
            userscreen_name="admin-dashboard", is_deleted=False,
        ).first()
        view = UserScreenAction.objects.filter(action_name="view", is_deleted=False).first()
        if not (project and screen and view):
            return

        if not CompanyUserScreenPermission.objects.filter(
            company_id=company.unique_id,
            project_id=project.unique_id,
            userscreen_id=screen.unique_id,
            userscreenaction_id=view.unique_id,
            is_deleted=False,
        ).exists():
            CompanyUserScreenPermission.objects.create(
                company_id=company.unique_id,
                project_id=project.unique_id,
                mainscreen_id=screen.mainscreen_id,
                userscreen_id=screen.unique_id,
                userscreenaction_id=view.unique_id,
                order_no=1,
                description=f"view {screen.userscreen_name}",
            )

        staff = 0
        for config in StaffAccessConfiguration.objects.filter(
            company_id=company.unique_id, is_active=True, is_deleted=False,
        ):
            if project.unique_id not in config.get_project_ids():
                continue
            if StaffAccessConfigurationPermission.objects.filter(
                staff_access_configuration_id=config.unique_id,
                userscreen_id=screen.unique_id,
                userscreenaction_id=view.unique_id,
                is_deleted=False,
            ).exists():
                continue
            StaffAccessConfigurationPermission.objects.create(
                staff_access_configuration_id=config.unique_id,
                mainscreen_id=screen.mainscreen_id,
                userscreen_id=screen.unique_id,
                userscreenaction_id=view.unique_id,
            )
            staff += 1
        self.log(
            f"Admin Dashboard granted to {self.NOIDA_PROJECT} "
            f"(+{staff} staff access configurations)."
        )

    def _move_mainscreen_orders_out_of_range(self, mainscreentype, reserved_count):
        """Free the target 1..N order range without tripping MySQL unique checks."""
        screens = list(
            MainScreen.objects.filter(mainscreentype_id=mainscreentype.unique_id if hasattr(mainscreentype, 'unique_id') else mainscreentype)
            .order_by("order_no", "unique_id")
        )
        if not screens:
            return

        max_order = max((screen.order_no or 0) for screen in screens)
        offset = max_order + len(screens) + reserved_count + 1000
        for idx, screen in enumerate(screens, start=1):
            screen.order_no = offset + idx
            screen.save(update_fields=["order_no"])

    def _parked_order_no(self, main):
        """A free, out-of-range `order_no` under `main`.

        Used when adopting a screen from another mainscreen, so it lands in the
        same high band `_move_userscreen_orders_out_of_range` uses rather than
        keeping an old low number that the canonical renumber is about to
        assign to someone else.
        """
        max_order = (
            UserScreen.objects.filter(mainscreen_id=main.unique_id if hasattr(main, 'unique_id') else main).aggregate(
                top=Max("order_no")
            )["top"]
            or 0
        )
        return max_order + 1001

    def _move_userscreen_orders_out_of_range(self, main):
        """Free per-main user screen orders before applying canonical order."""
        screens = list(
            UserScreen.objects.filter(mainscreen_id=main.unique_id if hasattr(main, 'unique_id') else main)
            .order_by("order_no", "unique_id")
        )
        if not screens:
            return

        max_order = max((screen.order_no or 0) for screen in screens)
        offset = max_order + len(screens) + 1000
        for idx, screen in enumerate(screens, start=1):
            screen.order_no = offset + idx
            screen.save(update_fields=["order_no"])

    def run(self):
        # --------------------------------------------------
        # 0. COMPANIES
        # --------------------------------------------------
        companies = Company.objects.filter(is_deleted=False)
        if not companies.exists():
            self.log("No companies found. Seed companies first.")
            return

        # --------------------------------------------------
        # 0B. APP MODULE MASTER
        # --------------------------------------------------
        # module_key / surface_key / route are read-only in web because the
        # screens and routes behind them ship inside the Flutter build. Only
        # the label and ordering are maintained here.
        for entry in APP_MODULE_SEED:
            module, created = AppModule.objects.get_or_create(
                module_key=entry["module_key"],
                defaults={
                    "surface_key": entry["surface_key"],
                    "label": entry["label"],
                    "route": entry["route"],
                    "order_no": entry["order_no"],
                    "description": entry["description"],
                },
            )
            # Never overwrite a label or ordering an admin has changed in web;
            # the read-only identity fields are kept in step with the app.
            changed = []
            if module.surface_key != entry["surface_key"]:
                module.surface_key = entry["surface_key"]
                changed.append("surface_key")
            if module.route != entry["route"]:
                module.route = entry["route"]
                changed.append("route")
            if module.is_deleted:
                module.is_deleted = False
                module.is_active = True
                changed += ["is_deleted", "is_active"]
            if changed:
                module.save(update_fields=changed + ["updated_at"])

        self.log(f"App Module master: {AppModule.objects.filter(is_deleted=False).count()} modules.")

        # Retire the per-surface feature screens from the earlier design. There
        # is one permission list now: a driver/supervisor screen is governed by
        # the ordinary web permission it maps to, so these rows would only be a
        # second, divergent place to tick.
        retired = UserScreen.objects.filter(
            userscreen_name__regex=r"^app-(supervisor|driver|operator)-",
            is_deleted=False,
        )
        retired_ids = list(retired.values_list("unique_id", flat=True))
        if retired_ids:
            CompanyUserScreenPermission.objects.filter(
                userscreen_id__in=retired_ids
            ).update(is_active=False, is_deleted=True)
            StaffAccessConfigurationPermission.objects.filter(
                userscreen_id__in=retired_ids
            ).update(is_active=False, is_deleted=True)
            retired.update(is_active=False, is_deleted=True)
            self.log(f"Retired {len(retired_ids)} per-surface app feature screens.")

        # --------------------------------------------------
        # 1. MAIN SCREEN TYPE
        # --------------------------------------------------
        # The sidebar sections (permission_catalog.SECTIONS), plus
        # "mobile-app" for the citizen app screens. Every other mobile screen
        # is governed by the ordinary web permission it maps to — see
        # app/utils/app_feature_grants.py — so only the citizen app, which
        # has no web screens at all, needs rows of its own here.
        screen_type_names = tuple(SECTION_MODULES) + ("mobile-app",)
        screen_types = {}
        for type_name in screen_type_names:
            screen_type, _ = MainScreenType.objects.update_or_create(
                type_name=type_name,
                defaults={
                    "is_active": True,
                    "is_deleted": False,
                },
            )
            screen_types[type_name] = screen_type

        # --------------------------------------------------
        # 2. ACTIONS
        # --------------------------------------------------
        actions = {}
        for name in ["add", "view", "edit", "delete", "use"]:
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
        # 3. SCREEN STRUCTURE — from the one permission catalog
        # --------------------------------------------------
        # Modules, screens and their sidebar grouping are defined once in
        # app/utils/permission_catalog.py (shared with the middleware and,
        # via the generated permissionCatalog.ts, the frontend sidebar). Add
        # or rename screens there, never here.
        screen_structure = {
            name: list(screens) for name, screens in SCREEN_STRUCTURE.items()
        }
        # CITIZEN APP — the one exception to "one permission list". Every
        # citizen route is middleware-exempt and self-scoped, so there is
        # nothing in the ordinary catalog to grant a customer; these rows are
        # ticked on a CustomerAccessConfiguration and gate the app's UI only.
        screen_structure[CITIZEN_APP_MAINSCREEN] = CITIZEN_APP_SCREENS

        screen_groups = dict(SECTION_MODULES)
        screen_groups["mobile-app"] = (CITIZEN_APP_MAINSCREEN,)

        module_group = {
            module_name: group_name
            for group_name, module_names in screen_groups.items()
            for module_name in module_names
        }
        module_order = {
            module_name: order
            for module_names in screen_groups.values()
            for order, module_name in enumerate(module_names, start=1)
        }
        ungrouped_modules = set(screen_structure) - set(module_group)
        unknown_modules = set(module_group) - set(screen_structure)
        if ungrouped_modules or unknown_modules:
            raise RuntimeError(
                "Permission screen grouping is out of sync: "
                f"ungrouped={sorted(ungrouped_modules)}, "
                f"unknown={sorted(unknown_modules)}"
            )

        # --------------------------------------------------
        # 4. CREATE MAIN SCREENS + USER SCREENS
        # --------------------------------------------------
        mainscreens = {}
        created_screens = []

        for group_name, module_names in screen_groups.items():
            self._move_mainscreen_orders_out_of_range(
                screen_types[group_name],
                len(module_names),
            )

        for main_name, screens in screen_structure.items():
            group_name = module_group[main_name]
            main, _ = MainScreen.objects.update_or_create(
                mainscreen_name=main_name,
                defaults={
                    "mainscreentype_id": screen_types[group_name].unique_id if hasattr(screen_types[group_name], 'unique_id') else screen_types[group_name],
                    "icon_name": main_name,
                    "order_no": module_order[main_name],
                    "is_active": True,
                    "is_deleted": False,
                },
            )
            mainscreens[main_name] = main

            self._move_userscreen_orders_out_of_range(main)

            ordered_screens = []
            for idx, screen_name in enumerate(screens, start=1):
                # Preserve existing permission rows when adopting the router's
                # canonical screen name instead of creating a duplicate screen.
                if screen_name == "weighbridge-management":
                    # Renamed from "workforce-management"; keep the row (and
                    # every grant on it) rather than seeding a duplicate.
                    if not UserScreen.objects.filter(userscreen_name=screen_name).exists():
                        UserScreen.objects.filter(
                            userscreen_name="workforce-management"
                        ).update(
                            userscreen_name=screen_name,
                            folder_name=screen_name,
                            icon_name=screen_name,
                        )

                if screen_name == "companywisescreenpermissions":
                    legacy_screen = UserScreen.objects.filter(
                        userscreen_name="CompanyUserScreenPermission",
                        mainscreen_id=main.unique_id if hasattr(main, 'unique_id') else main,
                    ).first()
                    canonical_exists = UserScreen.objects.filter(
                        userscreen_name=screen_name,
                    ).exists()
                    if legacy_screen and not canonical_exists:
                        legacy_screen.userscreen_name = screen_name
                        legacy_screen.folder_name = screen_name
                        legacy_screen.icon_name = screen_name
                        legacy_screen.save(
                            update_fields=[
                                "userscreen_name",
                                "folder_name",
                                "icon_name",
                                "updated_at",
                            ]
                        )

                screen, screen_created = UserScreen.objects.get_or_create(
                    userscreen_name=screen_name,
                    defaults={
                        "mainscreen_id": main.unique_id if hasattr(main, 'unique_id') else main,
                        "folder_name": screen_name,
                        "icon_name": screen_name,
                        "order_no": idx,
                        "is_active": True,
                        "is_deleted": False,
                    },
                )
                if screen_created:
                    created_screens.append(screen)
                main_id = main.unique_id if hasattr(main, 'unique_id') else main
                if screen.mainscreen_id != main_id:
                    # `_move_userscreen_orders_out_of_range` above only parked
                    # the screens ALREADY under `main`. A screen arriving from
                    # a different mainscreen — as the complaint masters do when
                    # they split out of "complaint-ticket" into
                    # "complaint-masters" — still carries its old `order_no`,
                    # which may be a low number that the renumber loop below is
                    # about to hand to a different screen. Park it into the same
                    # out-of-range band on the way in so the two cannot collide
                    # on (mainscreen_id, order_no).
                    screen.mainscreen_id = main_id
                    screen.order_no = self._parked_order_no(main)
                    screen.save(update_fields=["mainscreen_id", "order_no"])
                    # Grant rows carry their own mainscreen_id and the
                    # permission payload is keyed by it — re-point them or
                    # every existing grant on the moved screen goes inert.
                    CompanyUserScreenPermission.objects.filter(
                        userscreen_id=screen.unique_id
                    ).exclude(mainscreen_id=main_id).update(mainscreen_id=main_id)
                    StaffAccessConfigurationPermission.objects.filter(
                        userscreen_id=screen.unique_id
                    ).exclude(mainscreen_id=main_id).update(mainscreen_id=main_id)
                ordered_screens.append(screen)

            # Retire screens this main screen no longer defines. Without this
            # they keep `is_active=True` and stay parked at the out-of-range
            # order `_move_userscreen_orders_out_of_range` gave them, so they
            # linger in permission grids as pickable rows for screens the UI
            # no longer routes (e.g. the complaint reference tables once they
            # lost their CRUD pages). Soft-delete only — the permission rows
            # hanging off them are left intact in case a screen comes back.
            canonical_ids = {screen.pk for screen in ordered_screens}
            orphaned = UserScreen.objects.filter(mainscreen_id=main.unique_id if hasattr(main, 'unique_id') else main).exclude(
                pk__in=canonical_ids
            )
            for screen in orphaned:
                if screen.is_active or not screen.is_deleted:
                    screen.is_active = False
                    screen.is_deleted = True
                    screen.save(update_fields=["is_active", "is_deleted"])

            for idx, screen in enumerate(ordered_screens, start=1):
                screen.order_no = idx
                screen.is_active = True
                screen.is_deleted = False
                screen.save(update_fields=["order_no", "is_active", "is_deleted"])

                # Persist model mapping for known screens so schema resolver can find models
                mapping = {
                    "department-masters": ("app", "Department"),
                    "designation-masters": ("app", "Designation"),
                    "panchayat-leaders": ("app", "PanchayatLeaderLogin"),
                    "district-leaders": ("app", "DistrictLeaderLogin"),
                }
                if screen.userscreen_name in mapping:
                    app_label, model_name = mapping[screen.userscreen_name]
                    if screen.model_app_label != app_label or screen.model_name != model_name:
                        screen.model_app_label = app_label
                        screen.model_name = model_name
                        screen.save(update_fields=["model_app_label", "model_name", "updated_at"])

        # "schedule-masters" lost its last screens to "reports"; retire the
        # emptied main screen so it stops showing as a blank permission group.
        legacy_schedule_masters = MainScreen.objects.filter(
            mainscreen_name="schedule-masters", is_deleted=False,
        ).first()
        if legacy_schedule_masters and not UserScreen.objects.filter(
            mainscreen_id=legacy_schedule_masters.unique_id,
            is_deleted=False,
        ).exists():
            legacy_schedule_masters.is_active = False
            legacy_schedule_masters.is_deleted = True
            legacy_schedule_masters.save(update_fields=["is_active", "is_deleted"])

        legacy_megamenu = MainScreenType.objects.filter(type_name="megamenu").first()
        if legacy_megamenu and not MainScreen.objects.filter(
            mainscreentype_id=legacy_megamenu.unique_id if hasattr(legacy_megamenu, 'unique_id') else legacy_megamenu,
            is_active=True,
            is_deleted=False,
        ).exists():
            legacy_megamenu.is_active = False
            legacy_megamenu.is_deleted = True
            legacy_megamenu.save(update_fields=["is_active", "is_deleted"])

        # --------------------------------------------------
        # 4B. GRANTS FOR SCREENS SPLIT OUT OF AN EXISTING ONE
        # --------------------------------------------------
        for screen in created_screens:
            source_name = INHERITS_GRANTS_FROM.get(screen.userscreen_name)
            if source_name:
                self._inherit_grants(screen, source_name)

        # --------------------------------------------------
        # 4C. MONTHLY WASTE COMPARISON COLUMNS
        # --------------------------------------------------
        reports_main = mainscreens.get("reports")
        if reports_main:
            monthly_waste_screen = UserScreen.objects.filter(
                mainscreen_id=reports_main.unique_id if hasattr(reports_main, 'unique_id') else reports_main,
                userscreen_name="monthly-waste-comparison",
                is_deleted=False,
            ).first()
            if monthly_waste_screen:
                monthly_waste_columns = [
                    ("month",                         "Month",                   "string",  "month",                          1),
                    ("panchayat_name",                "Panchayat",               "string",  "panchayat_id__panchayat_name",   2),
                    ("waste_type",                    "Waste Type",              "string",  "waste_type_id__waste_type_name",  3),
                    ("total_agreed_weight",           "Agreed Weight (kg)",      "decimal", "agreed_weight_kg",               4),
                    ("total_actual_weight",           "Actual Weight (kg)",      "decimal", "actual_weight_kg",               5),
                    ("variance_kg",                   "Variance (kg)",           "decimal", "variance_kg",                    6),
                    ("variance_percent",              "Variance %",              "decimal", "variance_percent",               7),
                    ("report_status",                 "Status",                  "string",  "report_status",                  8),
                    ("total_trips",                   "Total Trips",             "integer", "total_trips",                    9),
                    ("collection_points_covered",     "Collection Points",       "integer", "collection_points_covered",      10),
                    ("collection_efficiency_percent", "Collection Efficiency %", "decimal", "collection_efficiency_percent",  11),
                    ("average_weight_per_trip",       "Avg Weight/Trip (kg)",    "decimal", "average_weight_per_trip",        12),
                    ("coverage_efficiency_percent",   "Coverage Efficiency %",   "decimal", "coverage_efficiency_percent",    13),
                ]
                for field_name, display_name, data_type, db_col, order_no in monthly_waste_columns:
                    UserScreenColumn.objects.update_or_create(
                        userscreen_id=monthly_waste_screen.unique_id if hasattr(monthly_waste_screen, 'unique_id') else monthly_waste_screen,
                        field_name=field_name,
                        is_deleted=False,
                        defaults={
                            "display_name": display_name,
                            "data_type": data_type,
                            "db_column": db_col,
                            "order_no": order_no,
                            "is_required": False,
                            "is_nullable": True,
                            "is_active": True,
                            "is_visible": True,
                            "is_editable": False,
                            "is_filterable": True,
                            "is_searchable": True,
                            "is_sortable": True,
                        },
                    )
                self.log("Monthly waste comparison columns seeded.")

        # --------------------------------------------------
        # 4D. PANCHAYAT COLUMNS
        # --------------------------------------------------
        masters_main = mainscreens.get("masters")
        if masters_main:
            panchayat_screen = UserScreen.objects.filter(
                mainscreen_id=masters_main.unique_id if hasattr(masters_main, 'unique_id') else masters_main,
                userscreen_name="panchayat",
                is_deleted=False,
            ).first()
            if panchayat_screen:
                panchayat_columns = [
                    ("agreed_weight_kg", "Agreed Weight", "decimal", "agreed_weight_kg", 50),
                    ("weight_unit",      "Weight Unit",   "string",  "weight_unit",      51),
                    ("effective_from",   "Effective From","date",    "effective_from",   52),
                ]
                for field_name, display_name, data_type, db_column, order_no in panchayat_columns:
                    UserScreenColumn.objects.update_or_create(
                        userscreen_id=panchayat_screen.unique_id if hasattr(panchayat_screen, 'unique_id') else panchayat_screen,
                        field_name=field_name,
                        is_deleted=False,
                        defaults={
                            "display_name": display_name,
                            "data_type": data_type,
                            "db_column": db_column,
                            "order_no": order_no,
                            "is_required": False,
                            "is_nullable": True,
                            "is_active": True,
                            "is_visible": True,
                            "is_editable": True,
                            "is_filterable": True,
                            "is_searchable": True,
                            "is_sortable": True,
                        },
                    )

        # --------------------------------------------------
        # 5. BASELINE PERMISSIONS (COMPANY-WIDE, PROJECT-INDEPENDENT)
        # --------------------------------------------------
        # Roles no longer gate permission rows; this seeds a full-access
        # baseline per company with project_id left null (project-level
        # scoping, if needed, is layered on top via the normal permission
        # APIs).
        # --------------------------------------------------
        # 6. BASELINE SCREEN PERMISSIONS (FULL ACCESS TO ALL SCREENS)
        # --------------------------------------------------
        for company in companies:
            self.log(f"--- Seeding baseline permissions for company: {company.name} ---")

            company_project = (
                Project.objects.filter(company_id=company.unique_id if hasattr(company, 'unique_id') else company, is_active=True, is_deleted=False)
                .order_by("unique_id")
                .first()
            )
            if not company_project:
                self.log(
                    f"    No active project found for company {company.name}; "
                    "seeding baseline permissions with project_id=None."
                )

            for main in mainscreens.values():
                # A citizen app screen answers only "can they see it", so
                # add/edit/delete/use are not offered against one.
                if main.mainscreen_name == CITIZEN_APP_MAINSCREEN:
                    screen_actions = [actions["view"]] if "view" in actions else []
                else:
                    screen_actions = list(actions.values())

                main_id = main.unique_id if hasattr(main, 'unique_id') else main
                for screen in UserScreen.objects.filter(mainscreen_id=main_id, is_deleted=False):
                    for order_no, action in enumerate(
                        self._seedable_actions(screen.userscreen_name, screen_actions),
                        start=1,
                    ):
                        CompanyUserScreenPermission.objects.get_or_create(
                            company_id=company.unique_id if hasattr(company, 'unique_id') else company,
                            project_id=company_project.unique_id if hasattr(company_project, 'unique_id') else company_project,
                            mainscreen_id=main_id,
                            userscreen_id=screen.unique_id if hasattr(screen, 'unique_id') else screen,
                            userscreenaction_id=action.unique_id if hasattr(action, 'unique_id') else action,
                            defaults={
                                "order_no": order_no,
                                "description": f"{action.variable_name} {screen.userscreen_name}",
                                "is_active": True,
                                "is_deleted": False,
                            },
                        )

        # --------------------------------------------------
        # 7. BASELINE COLUMN PERMISSIONS (FULL ACCESS TO ALL COLUMNS)
        # --------------------------------------------------
        self.log("Seeding baseline column permissions...")

        all_screens = UserScreen.objects.filter(is_deleted=False, is_active=True)

        for company in companies:
            company_project = (
                Project.objects.filter(company_id=company.unique_id if hasattr(company, 'unique_id') else company, is_active=True, is_deleted=False)
                .order_by("unique_id")
                .first()
            )
            for screen in all_screens:
                columns = UserScreenColumn.objects.filter(
                    userscreen_id=screen.unique_id if hasattr(screen, 'unique_id') else screen,
                    is_deleted=False,
                    is_active=True,
                )
                for order_no, column in enumerate(columns, start=1):
                    CompanyUserScreenColumnPermission.objects.update_or_create(
                        company_id=company.unique_id if hasattr(company, 'unique_id') else company,
                        project_id=company_project.unique_id if hasattr(company_project, 'unique_id') else company_project,
                        userscreen_id=screen.unique_id if hasattr(screen, 'unique_id') else screen,
                        column_id=column.unique_id if hasattr(column, 'unique_id') else column,
                        defaults={
                            "can_view": True,
                            "order_no": order_no,
                            "description": f"{screen.userscreen_name} - {column.display_name}",
                            "is_active": True,
                            "is_deleted": False,
                        },
                    )

        self._retire_unseedable_grants()
        self._grant_palakkad_project_admin_access()
        self._grant_noida_admin_dashboard()

        self.log("--- Baseline permission seeding completed successfully ---")
