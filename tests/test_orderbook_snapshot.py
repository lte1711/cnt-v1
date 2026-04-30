from __future__ import annotations

import unittest

from src.market.orderbook_snapshot import parse_depth_snapshot


class OrderbookSnapshotTests(unittest.TestCase):
    def test_parse_depth_snapshot_calculates_spread_and_imbalance(self) -> None:
        snapshot = parse_depth_snapshot(
            "ETHUSDT",
            {
                "bids": [["100.00", "1.0"], ["99.90", "2.0"]],
                "asks": [["100.10", "1.0"], ["100.20", "1.0"]],
            },
            top_levels=2,
            max_spread_pct=0.01,
        )

        self.assertTrue(snapshot["usable"])
        self.assertEqual(snapshot["best_bid"], 100.0)
        self.assertEqual(snapshot["best_ask"], 100.1)
        self.assertAlmostEqual(snapshot["spread"], 0.1)
        self.assertAlmostEqual(snapshot["bid_depth_notional"], 299.8)
        self.assertAlmostEqual(snapshot["ask_depth_notional"], 200.3)
        self.assertAlmostEqual(snapshot["imbalance"], 299.8 / 200.3)

    def test_parse_depth_snapshot_marks_empty_depth_unusable(self) -> None:
        snapshot = parse_depth_snapshot("ETHUSDT", {"bids": [], "asks": []})

        self.assertFalse(snapshot["usable"])
        self.assertEqual(snapshot["reason"], "empty_depth")


if __name__ == "__main__":
    unittest.main()
