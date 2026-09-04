"""Complaint teams — ported from the government backend's team_seeder.py.

`lead_staff` is deliberately left unset here — `supervisor_user.py` wires
every team's `lead_staff` to `supervisor_user` once it (and this seeder)
have both run, so a public/citizen grievance that routes to one of these
teams surfaces in the supervisor app via
`_staff_ticket_scope`'s `assigned_team__lead_staff=user` match.

Must run BEFORE `supervisor_user` (see seed.py's SEED_GROUPS ordering) —
`ComplaintTeam.objects.filter(...).update(lead_staff=supervisor)` in that
seeder is a silent no-op over an empty queryset if no teams exist yet.
"""

from app.management.commands.seeders.base import BaseSeeder
from app.models.complaint_management import ComplaintTeam


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
        created = {}
        for code, name, level, _ in self.TEAMS:
            team, _created = ComplaintTeam.objects.get_or_create(
                team_code=code,
                defaults={
                    "team_name": name,
                    "escalation_level": level,
                    "is_active": True,
                    "is_deleted": False,
                },
            )
            created[code] = team

        # Wire escalation chain: SANITATION -> SANITATION_L2
        sanitation = created.get("SANITATION")
        sanitation_l2 = created.get("SANITATION_L2")
        if sanitation and sanitation_l2 and not sanitation.escalates_to_id:
            sanitation.escalates_to = sanitation_l2
            sanitation.save(update_fields=["escalates_to"])

        self.log(f"---Complaint teams seeded ({len(self.TEAMS)} records)---")
