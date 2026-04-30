from __future__ import annotations

import unittest

from src.risk.enhanced_exit_manager import evaluate_exit


class ExitManagerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.filters = {
            "lot_size_filter": {
                "min_qty": "0.0001",
                "max_qty": "9000.00000000",
                "step_size": "0.00010000",
            }
        }

    def test_stop_exit_is_triggered_when_price_is_below_stop(self) -> None:
        open_trade = {
            "entry_price": 100.0,
            "entry_qty": 1.0,
            "stop_price": 99.0,
            "target_price": 101.0,
            "highest_price_since_entry": 100.5,
        }

        exit_signal = evaluate_exit(open_trade, 98.5, {}, self.filters)

        self.assertTrue(exit_signal.should_exit)
        self.assertEqual(exit_signal.exit_type, "STOP")
        self.assertEqual(exit_signal.reason, "stop_price_triggered")

    def test_partial_exit_levels_are_ignored_when_feature_is_disabled(self) -> None:
        open_trade = {
            "entry_price": 100.0,
            "entry_qty": 1.0,
            "stop_price": 99.0,
            "target_price": 103.0,
            "highest_price_since_entry": 101.2,
            "partial_exit_levels": [
                {"qty_ratio": 0.5, "target_price": 101.0},
            ],
            "partial_exit_progress": 0,
        }

        exit_signal = evaluate_exit(open_trade, 101.0, {}, self.filters)

        self.assertFalse(exit_signal.should_exit)
        self.assertEqual(exit_signal.exit_type, "NONE")
        self.assertEqual(exit_signal.reason, "no_exit_condition_met")

    def test_partial_exit_min_qty_path_is_inactive_when_feature_is_disabled(self) -> None:
        open_trade = {
            "entry_price": 100.0,
            "entry_qty": 0.0001,
            "stop_price": 99.0,
            "target_price": 103.0,
            "highest_price_since_entry": 101.2,
            "partial_exit_levels": [
                {"qty_ratio": 0.2, "target_price": 101.0},
            ],
            "partial_exit_progress": 0,
        }

        exit_signal = evaluate_exit(open_trade, 101.0, {}, self.filters)

        self.assertFalse(exit_signal.should_exit)
        self.assertEqual(exit_signal.reason, "no_exit_condition_met")


if __name__ == "__main__":
    unittest.main()
