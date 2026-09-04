"""Grievance-handling staff and the escalation chain they form.

Before this, every complaint team shared one `lead_staff` (the generic
`supervisor_user`) and only SANITATION had an `escalates_to`, so escalating a
Billing or Address ticket raised "Already at the top of the escalation chain."

This creates one grievance officer per team plus a single grievance manager
above them, then wires the chain so escalation always has somewhere to go:

    SANITATION ─┐
    BILLING   ──┼─► SANITATION_L2 ─► GRIEVANCE_CELL   (manager)
    ADDRESS   ──┤
    GENERAL   ──┘

`perform_escalation` walks `ComplaintTeam.escalates_to` and notifies the
target team's `lead_staff`, so a ticket escalated from Billing reaches the L2
desk's officer and then the manager — two real people, not one shared login.

Everything is stamped with the complaint module's company/project (Palakkad
BP), matching the tenancy the masters were scoped to in migration 0003.

Must run AFTER `complaint_team` (needs the teams) and after the staff
seeders (needs a UserType/StaffUserType to attach logins to).
"""

from app.management.commands.seeders.base import BaseSeeder
from app.models.complaint_management import ComplaintTeam
from app.models.role_assigns.staffUserType import StaffUserType
from app.models.role_assigns.userType import UserType
from app.models.staff_creations.staffcreation import Staffcreation
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project


class ComplaintGrievanceStaffSeeder(BaseSeeder):
    name = "complaint_grievance_staff"

    PASSWORD = "Grievance123"
    ROLE_NAME = "Grievance Officer"
    MANAGER_ROLE_NAME = "Grievance Manager"

    # (team_code, username, employee_name, designation)
    OFFICERS = [
        ("SANITATION", "grv_sanitation", "Ramesh Nair", "Grievance Officer - Sanitation"),
        ("SANITATION_L2", "grv_sanitation_l2", "Devika Menon", "Grievance Officer - Sanitation L2"),
        ("BILLING", "grv_billing", "Priya Thomas", "Grievance Officer - Billing"),
        ("ADDRESS_DESK", "grv_address", "Anil Kumar", "Grievance Officer - Address Desk"),
        ("GENERAL", "grv_general", "Sneha Pillai", "Grievance Officer - General"),
    ]

    MANAGER = ("grv_manager", "Suresh Menon", "Grievance Manager")

    # Every level-1 desk escalates to the L2 desk; L2 escalates to the
    # manager's own team, which is the top of the chain.
    ESCALATION_CHAIN = {
        "SANITATION": "SANITATION_L2",
        "BILLING": "SANITATION_L2",
        "ADDRESS_DESK": "SANITATION_L2",
        "GENERAL": "SANITATION_L2",
        "SANITATION_L2": "GRIEVANCE_CELL",
    }

    def _resolve_tenancy(self):
        """Company/project the complaint module runs under.

        Read off the already-scoped teams so staff, teams and masters cannot
        disagree; falls back to the single active company/project.
        """
        team = (
            ComplaintTeam.objects.filter(is_deleted=False, project_id__isnull=False)
            .order_by("team_code")
            .first()
        )
        if team:
            return team.company_id, team.project_id

        companies = list(Company.objects.filter(is_deleted=False, is_active=True)[:2])
        if len(companies) != 1:
            return None, None
        company = companies[0]
        projects = list(
            Project.objects.filter(
                company_id=company, is_deleted=False, is_active=True
            ).order_by("unique_id")[:2]
        )
        return company, (projects[0] if len(projects) == 1 else None)

    def _upsert_staff(self, *, username, name, designation, role, staff_type, company, project):
        staff, created = Staffcreation.objects.get_or_create(
            username=username,
            defaults={
                "employee_name": name,
                "designation": designation,
                "password": self.PASSWORD,
                "user_type_id": staff_type,
                "staffusertype_id": role,
                "company_id": company,
                "project_id": project,
                "is_active": True,
                "is_deleted": False,
                "is_superuser": False,
                "login_enabled": True,
                "approval_status": Staffcreation.APPROVAL_APPROVED,
            },
        )
        if not created:
            staff.employee_name = name
            staff.designation = designation
            staff.staffusertype_id = role
            staff.login_enabled = True
            staff.is_active = True
            staff.is_deleted = False
            staff.approval_status = Staffcreation.APPROVAL_APPROVED
            # `staff_id` is allocated once per company+project (see
            # `Staffcreation.save`). Moving a row to a different project would
            # carry its old sequence number into a scope that may already use
            # it — `uniq_staff_id_per_company_project` then rejects the update.
            # Clearing it lets save() allocate a fresh number in the new scope.
            if (
                staff.company_id_id != getattr(company, "pk", None)
                or staff.project_id_id != getattr(project, "pk", None)
            ):
                staff.staff_id = None
            staff.company_id = company
            staff.project_id = project
            staff.save()
        return staff, created

    def run(self):
        staff_type = UserType.objects.filter(name__iexact="staff").first()
        if not staff_type:
            self.log("UserType 'staff' missing — run the role-assigns seed group first. Skipping.")
            return

        company, project = self._resolve_tenancy()
        if not company:
            self.log("Could not resolve a single company — skipping grievance staff.")
            return

        officer_role, _ = StaffUserType.objects.get_or_create(
            name=self.ROLE_NAME,
            usertype_id=staff_type,
            defaults={"is_active": True, "is_deleted": False},
        )
        manager_role, _ = StaffUserType.objects.get_or_create(
            name=self.MANAGER_ROLE_NAME,
            usertype_id=staff_type,
            defaults={"is_active": True, "is_deleted": False},
        )

        # The manager sits above every desk, so their team is the top of the
        # chain and needs to exist before the officers are wired to it.
        # Look up by code alone (see the note in `team_seeder.py`): keying on
        # the tenancy too would create a second Grievance Cell whenever the
        # existing row's project differs from the one resolved here.
        manager_team = ComplaintTeam.objects.filter(
            team_code="GRIEVANCE_CELL", is_deleted=False
        ).first()
        if manager_team is None:
            manager_team = ComplaintTeam.objects.create(
                team_code="GRIEVANCE_CELL",
                team_name="Grievance Cell",
                escalation_level=3,
                company_id=company,
                project_id=project,
                is_active=True,
                is_deleted=False,
            )
        else:
            manager_team.company_id = company
            manager_team.project_id = project
            manager_team.save(update_fields=["company_id", "project_id"])

        username, name, designation = self.MANAGER
        manager, _ = self._upsert_staff(
            username=username,
            name=name,
            designation=designation,
            role=manager_role,
            staff_type=staff_type,
            company=company,
            project=project,
        )
        manager_team.lead_staff = manager
        manager_team.save(update_fields=["lead_staff"])

        created_count = 0
        assigned_teams = 0
        for team_code, username, name, designation in self.OFFICERS:
            officer, created = self._upsert_staff(
                username=username,
                name=name,
                designation=designation,
                role=officer_role,
                staff_type=staff_type,
                company=company,
                project=project,
            )
            created_count += 1 if created else 0

            team = ComplaintTeam.objects.filter(
                team_code=team_code, is_deleted=False
            ).first()
            if not team:
                continue
            # One owner per desk, replacing the shared supervisor login, and
            # the project the masters live under.
            team.lead_staff = officer
            team.company_id = company
            team.project_id = project
            team.save(update_fields=["lead_staff", "company_id", "project_id"])
            assigned_teams += 1

        # Wire the chain last, once every team exists.
        wired = 0
        for source_code, target_code in self.ESCALATION_CHAIN.items():
            source = ComplaintTeam.objects.filter(
                team_code=source_code, is_deleted=False
            ).first()
            target = ComplaintTeam.objects.filter(
                team_code=target_code, is_deleted=False
            ).first()
            if not source or not target or source.pk == target.pk:
                continue
            if source.escalates_to_id != target.pk:
                source.escalates_to = target
                source.save(update_fields=["escalates_to"])
            wired += 1

        self.log(
            f"---Grievance staff seeded (+{created_count} new of "
            f"{len(self.OFFICERS) + 1} logins, password {self.PASSWORD}); "
            f"{assigned_teams} team(s) got their own lead; {wired} escalation "
            f"link(s) wired under project {getattr(project, 'name', '(none)')}---"
        )
