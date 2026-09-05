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
from .department_roster_seeder import ComplaintDepartmentRosterSeeder
from .sample_ticket_seeder import ComplaintSampleTicketSeeder

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
#   4. department_roster — the Customer Care department + its 1 supervisor/5
#      member roster, and the default_department every category routes to.
#      Must precede routing_rule (which routes by default_department) and
#      sample_ticket (so seeded tickets route to a real member via the
#      round-robin picker instead of landing unassigned).
#   5. routing_rule — needs the SLA rules and every category's
#      default_department to already exist.
#   6. sample_ticket — demo rows; runs `apply_routing_and_sla`, so it needs
#      the routing/SLA rules and the department roster to already exist.
TICKET_SEEDERS = [
    ComplaintModuleSeeder,
    ComplaintSourceSeeder,
    ComplaintLanguageSeeder,
    ComplaintPrioritySeeder,
    ComplaintStatusSeeder,
    ComplaintCategorySeeder,
    ComplaintSubcategorySeeder,
    ComplaintSlaRuleSeeder,
    ComplaintDepartmentRosterSeeder,
    ComplaintRoutingRuleSeeder,
    ComplaintSampleTicketSeeder,
]
