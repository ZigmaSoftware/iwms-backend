from .main_category_seeder import MainCategorySeeder
from .sub_category_seeder import SubCategorySeeder
from .ticket_module_seeder import ComplaintModuleSeeder
from .ticket_source_seeder import ComplaintSourceSeeder
from .ticket_language_seeder import ComplaintLanguageSeeder
from .ticket_priority_seeder import ComplaintPrioritySeeder
from .ticket_status_seeder import ComplaintStatusSeeder
from .ticket_category_seeder import ComplaintCategorySeeder
from .ticket_subcategory_seeder import ComplaintSubcategorySeeder
from .sla_rule_seeder import ComplaintSlaRuleSeeder
from .routing_rule_seeder import ComplaintRoutingRuleSeeder
from .current_ticket_seeder import ComplaintCurrentTicketSeeder

GRIEVANCE_SEEDERS = [
    MainCategorySeeder,
    SubCategorySeeder,
]

# Ticketed complaint workflow (app.models.complaint_management.ComplaintTicket).
# Order matters:
#   1. modules/sources/languages/priorities/statuses — categories look up
#      default_priority/module by code.
#   2. categories — sla_rule looks up category.default_priority.
#   2b. subcategories — each row looks up its parent category by code.
#   3. sla_rule — routing_rule looks up the SLA rule this seeder creates.
#   4. routing_rule — needs the SLA rules to already exist.
#   5. current_ticket — a snapshot of the tickets that existed in the dev DB
#      on 2026-09-07 (replaces the old hardcoded ComplaintSampleTicketSeeder
#      demo set — that seeder is kept in the repo but no longer runs by
#      default, same convention as team_seeder.py/grievance_staff_seeder.py).
#      Runs `apply_routing_and_sla`, which assigns each ticket from the
#      project's hierarchy level 0 (ProjectStaffHierarchy) — that must exist
#      first, or seeded tickets land unassigned.
TICKET_SEEDERS = [
    ComplaintModuleSeeder,
    ComplaintSourceSeeder,
    ComplaintLanguageSeeder,
    ComplaintPrioritySeeder,
    ComplaintStatusSeeder,
    ComplaintCategorySeeder,
    ComplaintSubcategorySeeder,
    ComplaintSlaRuleSeeder,
    ComplaintRoutingRuleSeeder,
    ComplaintCurrentTicketSeeder,
]
