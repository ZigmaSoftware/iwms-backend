"""Complaint teams — ported from the government backend's team_seeder.py.

`lead_staff` is deliberately left unset here — `supervisor_user.py` wires
every team's `lead_staff` to `supervisor_user` once it (and this seeder)
have both run, so a public/citizen grievance that routes to one of these
teams surfaces in the supervisor app via
`_staff_ticket_scope`'s `assigned_team__lead_staff=user` match.

Must run BEFORE `supervisor_user` (see seed.py's SEED_GROUPS ordering) —
`ComplaintTeam.objects.filter(...).update(lead_staff=supervisor)` in that
seeder is a silent no-op over an empty queryset if no teams exist yet.

Teams are company/project-scoped (unlike every other complaint master, which
is global), so `team_code` is unique per company/project rather than globally
and the lookup below has to include the pair — otherwise a second tenant's
seed run would find the first tenant's team and skip creating its own.
"""

from app.management.commands.seeders.base import BaseSeeder
from app.models.complaint_management import ComplaintTeam
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project


class ComplaintTeamSeeder(BaseSeeder):
    name = "complaint_team"

    # (team_code, team_name, escalation_level, escalates_to_code)
    TEAMS = [
        ("SANITATION", "Sanitation Operations", 1, None),
        ("SANITATION_L2", "Sanitation Supervisor Desk", 2, None),
        ("BILLING", "Billing & Charges", 1, None),
        ("ADDRESS_DESK", "Address & Records Desk", 1, None),
        ("GENERAL", "General Grievance Desk", 1, None),
    ]

    def run(self):
        # Resolve the tenant rather than hardcoding a company name — this
        # deployment's company is "Blue Planet", and other deployments differ.
        # With exactly one active company the answer is unambiguous; with more
        # than one there is no safe default, so skip rather than misfile the
        # teams under whichever row happens to sort first.
        companies = list(Company.objects.filter(is_deleted=False, is_active=True)[:2])
        if len(companies) != 1:
            self.log(
                f"---Complaint teams skipped ({len(companies)} active companies; "
                "assign teams to a company manually)---"
            )
            return
        company = companies[0]

        # `project_id` stays NULL when the company runs several projects: teams
        # are company-level in every deployment seen so far, and guessing one of
        # several projects would hide them from the others' supervisors.
        projects = list(
            Project.objects.filter(company_id=company, is_deleted=False, is_active=True)[:2]
        )
        project = projects[0] if len(projects) == 1 else None

        created = {}
        for code, name, level, _ in self.TEAMS:
            # Look up by code alone, then stamp the tenancy. Keying
            # get_or_create on (code, company, project) instead would miss a
            # row that predates the scoping — or one whose project was set by
            # hand — and insert a second team with the same code.
            team = ComplaintTeam.objects.filter(
                team_code=code, is_deleted=False
            ).first()
            if team is None:
                team = ComplaintTeam.objects.create(
                    team_code=code,
                    team_name=name,
                    escalation_level=level,
                    company_id=company,
                    project_id=project,
                    is_active=True,
                    is_deleted=False,
                )
            elif not team.company_id_id or not team.project_id_id:
                team.company_id = company
                team.project_id = project
                team.save(update_fields=["company_id", "project_id"])
            created[code] = team

        # Wire escalation chain: SANITATION -> SANITATION_L2
        sanitation = created.get("SANITATION")
        sanitation_l2 = created.get("SANITATION_L2")
        if sanitation and sanitation_l2 and not sanitation.escalates_to_id:
            sanitation.escalates_to = sanitation_l2
            sanitation.save(update_fields=["escalates_to"])

        self.log(f"---Complaint teams seeded ({len(self.TEAMS)} records)---")
