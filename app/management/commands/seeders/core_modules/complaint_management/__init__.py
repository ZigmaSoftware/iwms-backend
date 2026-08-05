from .main_category_seeder import MainCategorySeeder
from .sub_category_seeder import SubCategorySeeder
from .ticket_module_seeder import ComplaintModuleSeeder
from .ticket_source_seeder import ComplaintSourceSeeder
from .ticket_language_seeder import ComplaintLanguageSeeder
from .ticket_priority_seeder import ComplaintPrioritySeeder
from .ticket_status_seeder import ComplaintStatusSeeder
from .ticket_category_seeder import ComplaintCategorySeeder

GRIEVANCE_SEEDERS = [
    MainCategorySeeder,
    SubCategorySeeder,
]

# Ticketed complaint workflow (app.models.complaint_management.ComplaintTicket).
# Order matters: modules/sources/languages/priorities/statuses before
# categories, since categories look up default_priority/module by code.
TICKET_SEEDERS = [
    ComplaintModuleSeeder,
    ComplaintSourceSeeder,
    ComplaintLanguageSeeder,
    ComplaintPrioritySeeder,
    ComplaintStatusSeeder,
    ComplaintCategorySeeder,
]
