from django.db.models import Max

from app.management.commands.seeders.base import BaseSeeder
from app.models.screen_managements.mainscreentype import MainScreenType
from app.models.screen_managements.app_module import AppModule
from app.models.staff_creations.staff_access_configuration import (
    StaffAccessConfigurationPermission,
)
from app.utils.app_feature_grants import (
    APP_MODULE_SEED,
    CITIZEN_APP_MAINSCREEN,
    CITIZEN_APP_SCREENS,
)
from app.models.screen_managements.userscreenaction import UserScreenAction
from app.models.screen_managements.mainscreen import MainScreen
from app.models.screen_managements.userscreen import UserScreen
from app.models.screen_managements.companyuserscreenpermission import (
    CompanyUserScreenPermission,
)
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project

from app.models.screen_managements.userscreencolumn import UserScreenColumn
from app.models.screen_managements.companyuserscreencolumnpermission import (
    CompanyUserScreenColumnPermission,
)


class PermissionSeeder(BaseSeeder):
    name = "permission_full"

    def _grant_palakkad_project_admin_access(self):
        from app.models.staff_creations.staffcreation import Staffcreation
        from app.models.staff_creations.staff_access_configuration import (
            StaffAccessConfiguration,
            StaffAccessConfigurationPermission,
        )

        staff = (
            Staffcreation.objects.select_related("company_id", "project_id")
            .filter(
                username="haripillai",
                project_id__name="Palakkad BP",
                is_active=True,
                is_deleted=False,
            )
            .first()
        )
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
            .select_related("mainscreen_id")
            .order_by("mainscreen_id__order_no", "order_no", "unique_id")
        )
        created = 0
        for screen in active_screens:
            for order_no, action in enumerate(active_actions, start=1):
                _, made = CompanyUserScreenPermission.objects.get_or_create(
                    company_id=staff.company_id,
                    project_id=staff.project_id,
                    mainscreen_id=screen.mainscreen_id,
                    userscreen_id=screen,
                    userscreenaction_id=action,
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
            ).select_related("mainscreen_id", "userscreen_id", "userscreenaction_id")
        )
        if not catalog:
            self.log(
                "Palakkad project admin haripillai exists, but no Palakkad BP "
                "permission catalog is available yet."
            )
            return

        config, _ = StaffAccessConfiguration.objects.update_or_create(
            staff_id=staff,
            defaults={
                "company_id": staff.company_id,
                "is_active": True,
                "is_deleted": False,
            },
        )
        config.projects.set([staff.project_id])

        seen = set()
        granted = 0
        for order, entry in enumerate(catalog, start=1):
            key = (
                entry.mainscreen_id_id,
                entry.userscreen_id_id,
                entry.userscreenaction_id_id,
            )
            if key in seen:
                continue
            seen.add(key)

            StaffAccessConfigurationPermission.objects.update_or_create(
                staff_access_configuration_id=config,
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
                staff_access_configuration_id=config,
            )
            if (
                perm.mainscreen_id_id,
                perm.userscreen_id_id,
                perm.userscreenaction_id_id,
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

    def _move_mainscreen_orders_out_of_range(self, mainscreentype, reserved_count):
        """Free the target 1..N order range without tripping MySQL unique checks."""
        screens = list(
            MainScreen.objects.filter(mainscreentype_id=mainscreentype)
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
            UserScreen.objects.filter(mainscreen_id=main).aggregate(
                top=Max("order_no")
            )["top"]
            or 0
        )
        return max_order + 1001

    def _move_userscreen_orders_out_of_range(self, main):
        """Free per-main user screen orders before applying canonical order."""
        screens = list(
            UserScreen.objects.filter(mainscreen_id=main)
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
                userscreen_id_id__in=retired_ids
            ).update(is_active=False, is_deleted=True)
            StaffAccessConfigurationPermission.objects.filter(
                userscreen_id_id__in=retired_ids
            ).update(is_active=False, is_deleted=True)
            retired.update(is_active=False, is_deleted=True)
            self.log(f"Retired {len(retired_ids)} per-surface app feature screens.")

        # --------------------------------------------------
        # 1. MAIN SCREEN TYPE
        # --------------------------------------------------
        screen_type_names = (
            "super-admin",
            "masters",
            "core-modules",
            "reports",
            # Holds the citizen app screens. Every other mobile screen is
            # governed by the ordinary web permission it maps to — see
            # app/utils/app_feature_grants.py — so only the citizen app, which
            # has no web screens at all, needs rows of its own here.
            "mobile-app",
        )
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
        # 3. SCREEN STRUCTURE (MATCHES ROUTER GROUPS)
        # --------------------------------------------------
        screen_structure = {
            "common-masters": [
                "continents",
                "countries",
                "states",
            ],
            "masters": [
                "districts",
                "cities",
                "zones",
                "wards",
                "panchayat",
                "panchayat-leaders",
                "district-leaders",
                "plants",
            ],
            "waste-types": [
                "properties",
                "subproperties",
                # merged in from the legacy "assets" screen group
                "bins",
                "waste type",
            ],
            "screen-managements": [
                "mainscreentype",
                "mainscreens",
                "userscreens",
                "userscreen-action",
                "companywisescreenpermissions",
                "app-modules",
            ],
            "role-assigns": [
                "user-type",
                "staffusertypes",
                "contractorusertypes",
            ],
            "staff-creations": [
                # "users-creation",
                # moved out of the "masters" group so the org/staff setup
                # screens live with the rest of staff management
                "department-masters",
                "designation-masters",
                "staffcreation",
                "staff-access-configuration",
                # "stafftemplate-creation",
                # "alternative-stafftemplate",
                # "supervisor-zone-map",
                # "unassigned-staff-pool",
            ],
            "attendance": [
                "attendance",
            ],
            "customers": [
                "customercreations",
                "customer-access-configuration",
                "apartment-list",
            ],
            # "waste-management": [
            #     "collection monitoring",
            #     "panchayat base collection",
            #     "ward base collection",
            # ],
            # SUPER ADMIN — global complaint configuration. Split out of
            # "complaint-ticket" because these tables have no company/project
            # FK: one edit changes behaviour for every tenant.
            #
            # Only the three Complaint Types tabs get screens. The seeded
            # reference tables (module/priority/status/source/language) are
            # code-keyed vocabularies the routing and SLA resolvers depend on,
            # so they stay seeder-owned with no UI; routing rules are an
            # API-only override now that routing falls back to the category's
            # default_team.
            "complaint-masters": [
                "types",
                "categories",
                "subcategories",
                "sla-rules",
            ],
            # CORE MODULES — company/project-scoped complaint entries. The
            # master screens are intentionally absent: staff read them through
            # the view-only routes (MODULE_READONLY_RESOURCES) and never get
            # add/edit/delete on them from here.
            "complaint-ticket": [
                # renamed from the legacy "grivences" screen group
                "tickets",
                "teams",
                "feedback",
                "reopen-history",
                "notifications",
                "address-change",
            ],
            "transport-masters": [
                "vehicle-type",
                "vehicle-creation",
                "fuels",
            ],
            "schedule-setup": [
                # split from the legacy "schedule-masters" screen group
                "staff-templates",
                "alternative-staff-templates",
                "collection-points",
                "trip-plans",
            ],
            "schedule-operations": [
                # split from the legacy "schedule-masters" screen group
                "daily-trip-assignments",
                "daily-trip-collection-points",
                "daily-trip-household-collections",
                "static-route-map",
                "bin-collection-events",
                "daily-trip-logs",
                "wastecollections",
                # registered in base_urls.py but previously missing here, so no
                # UserScreen/permission row was ever seeded for them
                "vehicle-breakdowns",
                "trip-delay-reports",
                "retrip-requests",
                # Registered in base_urls.py and called by every mobile
                # surface, but no UserScreen existed — so it could not be
                # granted from web at all, only through the role baseline.
                "staff-notifications",
            ],
            "schedule-masters": [
                # legacy name — kept alive only for the reporting
                # sub-resources still registered under it (see base_urls.py)
                "daily-waste-comparisons",
                "monthly-waste-comparison",
            ],
            "audits": [
                # "stafftemplate-audit-log",
                # "supervisor-zone-access-audit",
                # "vehicle-trip-audit",
                # "trip-exception-log",
                # "bin-load-log",
                "common-audit",
                "login-audit",
            ],
            # CITIZEN APP — the one exception to "one permission list".
            # Every citizen route is middleware-exempt and self-scoped, so
            # there is nothing in the ordinary catalog to grant a customer;
            # these rows are ticked on a CustomerAccessConfiguration and gate
            # the app's UI only.
            CITIZEN_APP_MAINSCREEN: CITIZEN_APP_SCREENS,
            "reports": [
                "trip-summary",
                "monthly-distance",
                "waste-collected-summary",
                "vehicle-track",
                "vehicle-history",
                "workforce-management",
                "date-report",
                "day-report",
                # "monthly-waste-comparison",
            ],
        }

        # Keep the backend permission hierarchy in the same groups and order as
        # the admin sidebar. MainScreen remains the permission module key; its
        # MainScreenType provides the parent group shown in screen management.
        screen_groups = {
            "super-admin": (
                "screen-managements",
                "role-assigns",
                "staff-creations",
                "common-masters",
                "complaint-masters",
                "audits",
            ),
            "masters": (
                "masters",
                "waste-types",
                "transport-masters",
                "customers",
            ),
            "core-modules": (
                "schedule-setup",
                "schedule-operations",
                "complaint-ticket",
                "attendance",
            ),
            "reports": (
                "schedule-masters",
                "reports",
            ),
            "mobile-app": (CITIZEN_APP_MAINSCREEN,),
        }

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
                    "mainscreentype_id": screen_types[group_name],
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
                if screen_name == "companywisescreenpermissions":
                    legacy_screen = UserScreen.objects.filter(
                        userscreen_name="CompanyUserScreenPermission",
                        mainscreen_id=main,
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

                screen, _ = UserScreen.objects.get_or_create(
                    userscreen_name=screen_name,
                    defaults={
                        "mainscreen_id": main,
                        "folder_name": screen_name,
                        "icon_name": screen_name,
                        "order_no": idx,
                        "is_active": True,
                        "is_deleted": False,
                    },
                )
                if screen.mainscreen_id_id != main.pk:
                    # `_move_userscreen_orders_out_of_range` above only parked
                    # the screens ALREADY under `main`. A screen arriving from
                    # a different mainscreen — as the complaint masters do when
                    # they split out of "complaint-ticket" into
                    # "complaint-masters" — still carries its old `order_no`,
                    # which may be a low number that the renumber loop below is
                    # about to hand to a different screen. Park it into the same
                    # out-of-range band on the way in so the two cannot collide
                    # on (mainscreen_id, order_no).
                    screen.mainscreen_id = main
                    screen.order_no = self._parked_order_no(main)
                    screen.save(update_fields=["mainscreen_id", "order_no"])
                ordered_screens.append(screen)

            # Retire screens this main screen no longer defines. Without this
            # they keep `is_active=True` and stay parked at the out-of-range
            # order `_move_userscreen_orders_out_of_range` gave them, so they
            # linger in permission grids as pickable rows for screens the UI
            # no longer routes (e.g. the complaint reference tables once they
            # lost their CRUD pages). Soft-delete only — the permission rows
            # hanging off them are left intact in case a screen comes back.
            canonical_ids = {screen.pk for screen in ordered_screens}
            orphaned = UserScreen.objects.filter(mainscreen_id=main).exclude(
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

        legacy_megamenu = MainScreenType.objects.filter(type_name="megamenu").first()
        if legacy_megamenu and not MainScreen.objects.filter(
            mainscreentype_id=legacy_megamenu,
            is_active=True,
            is_deleted=False,
        ).exists():
            legacy_megamenu.is_active = False
            legacy_megamenu.is_deleted = True
            legacy_megamenu.save(update_fields=["is_active", "is_deleted"])

        # --------------------------------------------------
        # 4C. MONTHLY WASTE COMPARISON COLUMNS
        # --------------------------------------------------
        reports_main = mainscreens.get("reports")
        if reports_main:
            monthly_waste_screen = UserScreen.objects.filter(
                mainscreen_id=reports_main,
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
                        userscreen_id=monthly_waste_screen,
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
                mainscreen_id=masters_main,
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
                        userscreen_id=panchayat_screen,
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
                Project.objects.filter(company_id=company, is_active=True, is_deleted=False)
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

                for screen in UserScreen.objects.filter(mainscreen_id=main, is_deleted=False):
                    for order_no, action in enumerate(screen_actions, start=1):
                        CompanyUserScreenPermission.objects.get_or_create(
                            company_id=company,
                            project_id=company_project,
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

        # --------------------------------------------------
        # 7. BASELINE COLUMN PERMISSIONS (FULL ACCESS TO ALL COLUMNS)
        # --------------------------------------------------
        self.log("Seeding baseline column permissions...")

        all_screens = UserScreen.objects.filter(is_deleted=False, is_active=True)

        for company in companies:
            company_project = (
                Project.objects.filter(company_id=company, is_active=True, is_deleted=False)
                .order_by("unique_id")
                .first()
            )
            for screen in all_screens:
                columns = UserScreenColumn.objects.filter(
                    userscreen_id=screen,
                    is_deleted=False,
                    is_active=True,
                )
                for order_no, column in enumerate(columns, start=1):
                    CompanyUserScreenColumnPermission.objects.update_or_create(
                        company_id=company,
                        project_id=company_project,
                        userscreen_id=screen,
                        column_id=column,
                        defaults={
                            "can_view": True,
                            "order_no": order_no,
                            "description": f"{screen.userscreen_name} - {column.display_name}",
                            "is_active": True,
                            "is_deleted": False,
                        },
                    )

        self._grant_palakkad_project_admin_access()

        self.log("--- Baseline permission seeding completed successfully ---")
