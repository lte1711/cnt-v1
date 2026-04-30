from __future__ import annotations

import unittest

from src.order_validator import auto_adjust_order_inputs


class OrderValidatorTests(unittest.TestCase):
    def test_adjusts_qty_to_clear_min_notional_at_reference_price(self) -> None:
        filters = {
            "price_filter": {
                "min_price": "0.01000000",
                "max_price": "1000000.00000000",
                "tick_size": "0.01000000",
            },
            "lot_size_filter": {
                "min_qty": "0.00010000",
                "max_qty": "9000.00000000",
                "step_size": "0.00010000",
            },
            "notional_filter": {
                "filter_type": "NOTIONAL",
                "min_notional": "5.00000000",
                "max_notional": "9000000.00000000",
            },
        }

        result = auto_adjust_order_inputs(
            price=2273.28,
            qty=0.001,
            filters=filters,
            min_notional_reference_price=2269.87008,
        )

        self.assertEqual(result["adjusted_qty"], 0.0023)
        self.assertGreaterEqual(2269.87008 * result["adjusted_qty"], 5.0)
        self.assertTrue(result["final_validation"]["all_valid"])


if __name__ == "__main__":
    unittest.main()
