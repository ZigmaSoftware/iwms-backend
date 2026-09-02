"""Named login users for the Blue Planet Integrated Waste Management project.

Builds one reporting chain against the department/designation masters from
StaffRoleMastersSeeder:

    aashish (driver) ─┐
                      ├─> Mukund (Operations Supervisor) ─> Megha (Project Admin)
    Cheren (operator)─┘

The driver/operator rows already exist for this project (created by
BluePlanetSeeder as ASHISH KASANA / CHREN SINGH), so they are matched on
employee name and updated in place — keeping their unique_id and any trip,
vehicle or attendance links — rather than being duplicated under a new
username.
"""

from django.utils import timezone

from app.management.commands.seeders.base import BaseSeeder
from app.models.masters.city import City
from app.models.masters.district import District
from app.models.masters.ward import Ward
from app.models.masters.zone import Zone
from app.models.role_assigns.staffUserType import StaffUserType
from app.models.role_assigns.userType import UserType
from app.models.screen_managements.companyuserscreenpermission import (
    CompanyUserScreenPermission,
)
from app.models.staff_creations.department import Department
from app.models.staff_creations.designation import Designation
from app.models.staff_creations.staff_access_configuration import (
    StaffAccessConfiguration,
    StaffAccessConfigurationPermission,
)

from app.models.staff_creations.staffcreation import Staffcreation
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project
from app.utils.password_encryption import encrypt_password


class GnoNamedStaffSeeder(BaseSeeder):
    name = "gno-named-staff"

    PROJECT_NAME = "Blue Planet Integrated Waste Management"

    # Department/designation codes come from StaffRoleMastersSeeder.
    DEPT_OPS = "OPS"
    DEPT_TRANS = "TRANS"

    DESG_SUPERVISOR = "Operations Supervisor"
    DESG_DRIVER = "Driver"
    DESG_OPERATOR = "Operator"

    def _get_role(self, staff_type, role_name):
        role, _ = StaffUserType.objects.get_or_create(
            name=role_name,
            usertype_id=staff_type,
            defaults={"is_active": True, "is_deleted": False},
        )
        return role

    def _upsert(self, *, username, employee_name, password, role, department,
                designation, staff_head, staff_head_id, match_names, base):
        """Update the existing person if present, else create them.

        `match_names` are the employee names this person may already be
        stored under (BluePlanetSeeder uses the upper-case forms).
        """
        # username is unique, so claim that row first — BluePlanetSeeder
        # seeds its own copy of these people under bp_gno_* usernames, and
        # matching on employee name alone can pick that duplicate and then
        # collide on the unique username.
        staff = Staffcreation.objects.filter(username=username).first()
        if staff is None:
            staff = (
                Staffcreation.objects.filter(
                    project_id=base["project_id"],
                    employee_name__in=match_names,
                )
                .exclude(username__startswith="bp_")
                .first()
            )

        fields = {
            **base,
            "employee_name": employee_name,
            "username": username,
            "office_email": f"{username.lower()}@blueplanet.local",
            "staffusertype_id": role,
            "department_id": department,
            "designation_id": designation,
            # Denormalised labels the list screens read.
            "department": department.department_name if department else None,
            "designation": designation.designation_name if designation else None,
            "staff_head": staff_head,
            "staff_head_id": staff_head_id,
            "login_enabled": True,
            "approval_status": Staffcreation.APPROVAL_APPROVED,
            "is_active": True,
            "is_deleted": False,
        }

        created = staff is None
        if created:
            staff = Staffcreation(**fields)
        else:
            for key, value in fields.items():
                setattr(staff, key, value)

        # Passwords are Fernet-encrypted at rest (see utils/password_encryption).
        staff.password = encrypt_password(password)
        staff.password_crt_date = timezone.now()
        staff.save()

        self.log(
            f"{employee_name} [{username}] as {role.name} "
            f"({'Created' if created else 'Updated'})"
        )
        return staff

    def run(self):
        project = Project.objects.filter(
            name=self.PROJECT_NAME, is_deleted=False
        ).first()
        if not project:
            self.log_error(
                f"Project '{self.PROJECT_NAME}' not found — run BluePlanetSeeder first."
            )
            return
        company = project.company_id

        staff_type = UserType.objects.filter(name__iexact="staff").first()
        if not staff_type:
            self.log_error("UserType 'Staff' not found — run the role seeders first.")
            return

        def _dept(code):
            return Department.objects.filter(
                company_id=company, project_id=project,
                department_code=code, is_deleted=False,
            ).first()

        def _desg(name, department):
            return Designation.objects.filter(
                company_id=company, project_id=project,
                designation_name=name, department_id=department,
                is_deleted=False,
            ).first()

        dept_ops = _dept(self.DEPT_OPS)
        dept_trans = _dept(self.DEPT_TRANS)
        if not dept_ops or not dept_trans:
            self.log_error(
                "Departments OPS/TRANS missing — run StaffRoleMastersSeeder first."
            )
            return

        desg_supervisor = _desg(self.DESG_SUPERVISOR, dept_ops)
        desg_operator = _desg(self.DESG_OPERATOR, dept_ops)
        desg_driver = _desg(self.DESG_DRIVER, dept_trans)
        if not all([desg_supervisor, desg_operator, desg_driver]):
            self.log_error(
                "Designations missing — run StaffRoleMastersSeeder first."
            )
            return

        base = {
            "user_type_id": staff_type,
            "company_id": company,
            "project_id": project,
            "district_id": District.objects.filter(is_deleted=False).first(),
            "city_id": City.objects.filter(is_deleted=False).first(),
            "zone_id": Zone.objects.filter(is_deleted=False).first(),
            "ward_id": Ward.objects.filter(is_deleted=False).first(),
        }

        # 1. Project admin — top of the chain, so no staff head of their own.
        megha = self._upsert(
            username="megha",
            employee_name="Megha",
            password="megha@123",
            role=self._get_role(staff_type, "Company Project Admin"),
            department=dept_ops,
            designation=desg_supervisor,
            staff_head=None,
            staff_head_id=None,
            match_names=["Megha", "MEGHA"],
            base=base,
        )

        # 2. Supervisor — reports to the project admin, replaces Mithun.M as
        #    the head for the field crew below.
        mukund = self._upsert(
            username="mukund",
            employee_name="Mukund",
            password="Mukund@123",
            role=self._get_role(staff_type, "Company Supervisor"),
            department=dept_ops,
            designation=desg_supervisor,
            staff_head=megha.employee_name,
            staff_head_id=megha.staff_unique_id,
            match_names=["Mukund", "MUKUND"],
            base=base,
        )

        # 3. Field crew — both now head-ed by Mukund instead of Mithun.M.
        self._upsert(
            username="aashish",
            employee_name="ASHISH KASANA",
            password="Aashish@123",
            role=self._get_role(staff_type, "Company Driver"),
            department=dept_trans,
            designation=desg_driver,
            staff_head=mukund.employee_name,
            staff_head_id=mukund.staff_unique_id,
            match_names=["ASHISH KASANA", "Ashish Kasana", "Aashish"],
            base=base,
        )

        self._upsert(
            username="cheren",
            employee_name="CHREN SINGH",
            password="Cheren@123",
            role=self._get_role(staff_type, "Company Operator"),
            department=dept_ops,
            designation=desg_operator,
            staff_head=mukund.employee_name,
            staff_head_id=mukund.staff_unique_id,
            match_names=["CHREN SINGH", "Chren Singh", "Cheren"],
            base=base,
        )

        self.log("---Named GNO staff seeded (1 project admin, 1 supervisor, 2 field staff)---")


class MeghaProjectAdminPermissionSeeder(BaseSeeder):
    """Grant Megha the full permission catalog for her company/project.

    Staff authorization resolves through StaffAccessConfiguration ->
    StaffAccessConfigurationPermission (see utils/permission_response.py
    permission_querysets), NOT through CompanyUserScreenPermission directly —
    the company catalog only defines what *may* be granted. As project admin
    Megha gets every action of that catalog, mirrored one-for-one, and the
    config is scoped to her project so column permissions narrow with it.
    """

    name = "megha-project-admin-permissions"

    USERNAME = "megha"

    def run(self):
        staff = Staffcreation.objects.filter(username=self.USERNAME).first()
        if not staff:
            self.log_error(
                f"Staff '{self.USERNAME}' not found — run GnoNamedStaffSeeder first."
            )
            return

        company = staff.company_id
        project = staff.project_id
        if not company or not project:
            self.log_error(f"'{self.USERNAME}' has no company/project assigned.")
            return

        catalog = list(
            CompanyUserScreenPermission.objects.filter(
                company_id=company,
                project_id=project,
                is_active=True,
                is_deleted=False,
            ).select_related("mainscreen_id", "userscreen_id", "userscreenaction_id")
        )
        if not catalog:
            self.log_error(
                f"No permission catalog for {company.name}/{project.name} — "
                "run the screen-managements seeder first."
            )
            return

        config, created = StaffAccessConfiguration.objects.update_or_create(
            staff_id=staff,
            defaults={
                "company_id": company,
                "is_active": True,
                "is_deleted": False,
            },
        )
        config.projects.set([project])
        self.log(
            f"Access configuration for {staff.employee_name} "
            f"({'Created' if created else 'Updated'}) -> project {project.name}"
        )

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

        # Drop grants that are no longer in the catalog so a re-run cannot
        # leave Megha holding permissions the company no longer defines.
        # The triple has to be compared as a whole — three independent __in
        # filters would keep any row whose columns each appear in some other
        # valid combination.
        stale_ids = [
            perm.unique_id
            for perm in StaffAccessConfigurationPermission.objects.filter(
                staff_access_configuration_id=config,
            )
            if (
                perm.mainscreen_id_id,
                perm.userscreen_id_id,
                perm.userscreenaction_id_id,
            ) not in seen
        ]
        removed = len(stale_ids)
        if removed:
            StaffAccessConfigurationPermission.objects.filter(
                unique_id__in=stale_ids
            ).delete()

        screens = len({k[1] for k in seen})
        self.log(
            f"---Granted {granted} permissions across {screens} screens"
            + (f" (removed {removed} stale)" if removed else "")
            + "---"
        )
