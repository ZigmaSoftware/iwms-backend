from .main_category_seeder import MainCategorySeeder
from .sub_category_seeder import SubCategorySeeder
from .ticket_module_seeder import ComplaintModuleSeeder
from .ticket_source_seeder import ComplaintSourceSeeder
from .ticket_language_seeder import ComplaintLanguageSeeder
from .ticket_priority_seeder import ComplaintPrioritySeeder
from .ticket_status_seeder import ComplaintStatusSeeder
from .team_seeder import ComplaintTeamSeeder
from .ticket_category_seeder import ComplaintCategorySeeder
from .sla_rule_seeder import ComplaintSlaRuleSeeder
from .routing_rule_seeder import ComplaintRoutingRuleSeeder

GRIEVANCE_SEEDERS = [
    MainCategorySeeder,
    SubCategorySeeder,
]

# Ticketed complaint workflow (app.models.complaint_management.ComplaintTicket).
# Order matters:
#   1. modules/sources/languages/priorities/statuses/teams — categories look
#      up default_priority/module/default_team by code.
#   2. categories — sla_rule/routing_rule look up category.default_priority
#      and category.default_team.
#   3. sla_rule — routing_rule looks up the SLA rule this seeder creates.
#   4. routing_rule — last, needs everything above.
# Run `supervisor-user` AFTER this group, or ComplaintTeamSeeder's rows won't
# exist yet for its `ComplaintTeam.objects.update(lead_staff=...)` to touch.
TICKET_SEEDERS = [
    ComplaintModuleSeeder,
    ComplaintSourceSeeder,
    ComplaintLanguageSeeder,
    ComplaintPrioritySeeder,
    ComplaintStatusSeeder,
    ComplaintTeamSeeder,
    ComplaintCategorySeeder,
    ComplaintSlaRuleSeeder,
    ComplaintRoutingRuleSeeder,
]
