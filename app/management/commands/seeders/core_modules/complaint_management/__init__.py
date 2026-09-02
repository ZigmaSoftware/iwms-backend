from .main_category_seeder import MainCategorySeeder
from .sub_category_seeder import SubCategorySeeder
from .ticket_module_seeder import ComplaintModuleSeeder
from .ticket_source_seeder import ComplaintSourceSeeder
from .ticket_language_seeder import ComplaintLanguageSeeder
from .ticket_priority_seeder import ComplaintPrioritySeeder
from .ticket_status_seeder import ComplaintStatusSeeder
from .team_seeder import ComplaintTeamSeeder
from .ticket_category_seeder import ComplaintCategorySeeder
from .ticket_subcategory_seeder import ComplaintSubcategorySeeder
from .sla_rule_seeder import ComplaintSlaRuleSeeder
from .routing_rule_seeder import ComplaintRoutingRuleSeeder
from .grievance_staff_seeder import ComplaintGrievanceStaffSeeder
from .sample_ticket_seeder import ComplaintSampleTicketSeeder

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
#   2b. subcategories — each row looks up its parent category by code.
#   3. sla_rule — routing_rule looks up the SLA rule this seeder creates.
#   4. routing_rule — needs everything above.
#   5. grievance_staff — one officer per team plus a manager above them, and
#      the escalates_to chain that links them. Must precede sample_ticket so
#      seeded tickets route to a team that has a real owner.
#   6. sample_ticket — demo rows; runs `apply_routing_and_sla`, so it needs
#      the routing and SLA rules to already exist.
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
    ComplaintSubcategorySeeder,
    ComplaintSlaRuleSeeder,
    ComplaintRoutingRuleSeeder,
    ComplaintGrievanceStaffSeeder,
    ComplaintSampleTicketSeeder,
]
