from __future__ import annotations

import unittest

from src.execution_decider import decide_execution
from src.models.strategy_signal import StrategySignal
from src.risk.exit_models import ExitModel


class ExecutionDeciderMinTradeQtyTests(unittest.TestCase):
    def test_entry_qty_respects_project_min_trade_qty(self) -> None:
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
        signal = StrategySignal(
            strategy_name="pullback_v1",
            symbol="ETHUSDT",
            decision_id="test-decision",
            signal_timestamp="2026-04-30 22:00:00",
            signal_age_limit_sec=-1,
            entry_allowed=True,
            side="BUY",
            trigger="test",
            reason="test",
            confidence=0.64,
            market_state="test",
            trend_bias="UP",
            volatility_state="normal",
            entry_price_hint=2273.28,
            exit_model=ExitModel(
                stop_price=2269.87008,
                target_price=2277.371904,
                trailing_stop_pct=None,
                partial_exit_levels=None,
                time_based_exit_minutes=None,
            ),
            market_features={},
        )

        decision = decide_execution(
            signal=signal,
            state={},
            balance={},
            filters=filters,
            requested_qty=0.001,
        )

        self.assertTrue(decision.execute)
        self.assertEqual(decision.validated_qty, 0.01)
        self.assertGreaterEqual(2269.87008 * decision.validated_qty, 5.0)


if __name__ == "__main__":
    unittest.main()
