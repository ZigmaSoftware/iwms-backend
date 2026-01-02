from api.management.commands.seeders.base import BaseSeeder
from api.apps.main_category_citizenGrievance import MainCategory
from api.apps.sub_category_citizenGrievance import SubCategory


class SubCategorySeeder(BaseSeeder):
    name = "sub_category"

    def run(self):
        category_map = {
            "Report issue": [
                "Missed Pickup",
                "Spillage / Overflow",
                "Broken Bin",
                "Staff Behavior",
                "Other",
            ],
            "Schedule pickup": [
                "Bulk Waste",
                "Garden Waste",
                "E-waste",
            ],
            "Pickup status": [
                "Track Pickup",
                "Track Complaint",
            ],
            "Waste tips": [
                "Recycling Tips",
                "Waste Segregation",
                "Composting Tips",
            ],
            "Collector info": [
                "Assigned Collector",
                "Collector Contact",
            ],
        }

        for main_name, sub_list in category_map.items():
            main_category = MainCategory.objects.get(
                main_categoryName=main_name  # ✅ CORRECT
            )

            for sub_name in sub_list:
                SubCategory.objects.get_or_create(
                    name=sub_name,            # ✅ CORRECT
                    mainCategory=main_category,  # ✅ CORRECT FK
                    defaults={
                        "is_active": True,
                        "is_deleted": False,
                    }
                )

        self.log("Sub categories seeded")
