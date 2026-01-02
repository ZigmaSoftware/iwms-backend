# core/management/commands/seeders/assets/__init__.py

from .main_category_seeder import MainCategorySeeder
from .sub_category_seeder import SubCategorySeeder


GRIEVANCE_SEEDERS = [
    MainCategorySeeder,
   SubCategorySeeder
]
    