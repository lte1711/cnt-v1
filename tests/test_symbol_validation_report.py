from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.analytics.symbol_validation_report import build_symbol_validation_report
from src.logging.symbol_validation_logger import build_symbol_validation_event, calculate_slippage_pct


class SymbolValidationReportTests(unittest.TestCase):
    def test_calculate_buy_slippage_pct(self) -> None:
        self.assertAlmostEqual(calculate_slippage_pct(100.0, 101.0, "BUY"), 0.01)

    def test_calculate_sell_slippage_pct(self) -> None:
        self.assertAlmostEqual(calculate_slippage_pct(100.0, 99.0, "SELL"), 0.01)

    def test_build_report_aggregates_pnl_slippage_and_order_quality(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_file = Path(tmp) / "symbol_validation.log"
            events = [
                build_symbol_validation_event(
                    event="order_result",
                    symbol="ALGOUSDT",
                    strategy_name="pullback_v1",
                    signal_price=100.0,
                    validated_qty=1.0,
                    orderbook={"usable": True, "spread_pct": 0.001, "imbalance": 1.2},
                    exchange={"status": "FILLED", "executed_qty": 1.0, "fill_price": 100.1},
                    close_pnl_estimate=0.3,
                ),
                build_symbol_validation_event(
                    event="order_result",
                    symbol="ALGOUSDT",
                    strategy_name="pullback_v1",
                    signal_price=100.0,
                    validated_qty=1.0,
                    orderbook={"usable": True, "spread_pct": 0.002, "imbalance": 0.8},
                    exchange={"status": "FILLED", "executed_qty": 1.0, "fill_price": 99.9},
                    close_pnl_estimate=-0.1,
                ),
            ]
            log_file.write_text(
                "\n".join(json.dumps(event) for event in events) + "\n",
                encoding="utf-8",
            )

            report = build_symbol_validation_report(log_file, symbol="ALGOUSDT")

        self.assertEqual(report["event_count"], 2)
        self.assertEqual(report["order_count"], 2)
        self.assertEqual(report["closed_trades"], 2)
        self.assertEqual(report["wins"], 1)
        self.assertEqual(report["losses"], 1)
        self.assertAlmostEqual(report["realized_expectancy"], 0.1)
        self.assertAlmostEqual(report["realized_profit_factor"], 3.0)
        self.assertEqual(report["order_reject_rate"], 0.0)
        self.assertEqual(report["orderbook"]["usable_rate"], 1.0)


if __name__ == "__main__":
    unittest.main()
