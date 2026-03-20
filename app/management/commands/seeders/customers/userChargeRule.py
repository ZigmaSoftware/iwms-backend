from decimal import Decimal

from app.management.commands.seeders.base import BaseSeeder
from app.models.customers.userchargerule import UserChargeRule
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project
from app.models.waste_types.property import Property
from app.models.waste_types.subproperty import SubProperty


class UserChargeRuleSeeder(BaseSeeder):
    name = "user_charge_rule"

    def run(self):
        company = Company.objects.filter(is_deleted=False).first()
        if not company:
            self.log("No company found. Seed company data first.")
            return

        project = Project.objects.filter(
            company_id=company,
            is_deleted=False,
        ).first()

        property_obj = Property.objects.filter(
            property_name="Residential",
            is_deleted=False,
        ).first() or Property.objects.filter(is_deleted=False).first()

        if not property_obj:
            self.log("No property found. Seed assets/property data first.")
            return

        subproperty_obj = SubProperty.objects.filter(
            property_id=property_obj,
            is_deleted=False,
        ).order_by("sub_property_name").first()

        if not subproperty_obj:
            self.log("No subproperty found. Seed assets/subproperty data first.")
            return

        rules = [
            {
                "is_bulk_waste_generator": True,
                "min_sqmtr_value": None,
                "max_sqmtr_value": None,
                "charge_amount": Decimal("300.00"),
                "description": "Bulk waste generator fixed pricing",
            },
            {
                "is_bulk_waste_generator": False,
                "min_sqmtr_value": Decimal("0.00"),
                "max_sqmtr_value": Decimal("1200.00"),
                "charge_amount": Decimal("100.00"),
                "description": "0.00 to 1200.00 sq.mtr slab charge",
            },
            {
                "is_bulk_waste_generator": False,
                "min_sqmtr_value": Decimal("1200.01"),
                "max_sqmtr_value": Decimal("2500.00"),
                "charge_amount": Decimal("150.00"),
                "description": "1200.01 to 2500.00 sq.mtr slab charge",
            },
        ]

        for entry in rules:
            rule, created = UserChargeRule.objects.get_or_create(
                company_id=company,
                project_id=project,
                property_id=property_obj,
                subproperty_id=subproperty_obj,
                is_bulk_waste_generator=entry["is_bulk_waste_generator"],
                min_sqmtr_value=entry["min_sqmtr_value"],
                max_sqmtr_value=entry["max_sqmtr_value"],
                defaults={
                    "charge_amount": entry["charge_amount"],
                    "description": entry["description"],
                    "is_active": True,
                    "is_deleted": False,
                },
            )

            if created:
                self.log(f"UserChargeRule created: {rule.unique_id}")
                continue

            update_fields = []
            if rule.charge_amount != entry["charge_amount"]:
                rule.charge_amount = entry["charge_amount"]
                update_fields.append("charge_amount")
            if rule.description != entry["description"]:
                rule.description = entry["description"]
                update_fields.append("description")
            if rule.is_deleted:
                rule.is_deleted = False
                update_fields.append("is_deleted")
            if not rule.is_active:
                rule.is_active = True
                update_fields.append("is_active")

            if update_fields:
                rule.save(update_fields=update_fields)

        self.log("---UserChargeRule seeded successfully---")
