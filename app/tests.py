from decimal import Decimal

from django.test import SimpleTestCase

from app.models.customers.customercreation import exceeds_bulk_waste_threshold


class BulkWasteThresholdTests(SimpleTestCase):
    def test_accepts_decimal_strings_from_seed_data(self):
        self.assertFalse(
            exceeds_bulk_waste_threshold("1200.00", "240.00", "3.50")
        )

    def test_detects_bulk_waste_threshold_from_decimal_strings(self):
        self.assertTrue(
            exceeds_bulk_waste_threshold("21000.00", "45000.00", "110.00")
        )

    def test_accepts_decimal_values_and_none(self):
        self.assertFalse(
            exceeds_bulk_waste_threshold(
                Decimal("20000"),
                None,
                Decimal("100"),
            )
        )
