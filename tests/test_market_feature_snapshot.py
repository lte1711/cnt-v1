from __future__ import annotations

import unittest

from src.market.feature_snapshot import build_market_feature_snapshot
from src.models.market_context import MarketContext


def _kline(index: int, close: float) -> dict:
    return {
        "open": str(close - 1.0),
        "high": str(close + 2.0),
        "low": str(close - 2.0),
        "close": str(close),
        "volume": str(100.0 + index),
    }


class MarketFeatureSnapshotTests(unittest.TestCase):
    def test_build_market_feature_snapshot_contains_required_fields(self) -> None:
        klines = [_kline(index, 100.0 + index) for index in range(40)]
        context = MarketContext(
            symbol="ETHUSDT",
            primary_interval="1h",
            entry_interval="5m",
            klines_primary=klines,
            klines_entry=klines,
            last_price=139.0,
            orderbook_imbalance=1.25,
            orderbook_snapshot={
                "usable": True,
                "reason": "ok",
                "imbalance": 1.25,
                "spread_pct": 0.0001,
            },
        )

        snapshot = build_market_feature_snapshot(
            context,
            {
                "ema_fast_period": 9,
                "ema_slow_period": 20,
                "rsi_period": 14,
                "atr_period": 14,
                "volume_avg_period": 20,
            },
        )

        self.assertEqual(snapshot["schema_version"], "1.0")
        self.assertEqual(snapshot["symbol"], "ETHUSDT")
        self.assertIn("multi_timeframe_trend", snapshot)
        self.assertEqual(snapshot["orderbook"]["imbalance"], 1.25)
        self.assertTrue(snapshot["orderbook"]["usable"])
        self.assertIn("rsi", snapshot["entry"])
        self.assertIn("ema_slope_pct", snapshot["entry"])
        self.assertIn("atr_pct", snapshot["entry"])
        self.assertIn("volume_ratio", snapshot["entry"])
        self.assertIn("candle_body_ratio", snapshot["entry"])
        self.assertIn("spread_proxy_pct", snapshot["entry"])


if __name__ == "__main__":
    unittest.main()
