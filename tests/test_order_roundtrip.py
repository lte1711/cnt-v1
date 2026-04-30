from __future__ import annotations

import unittest

from config import MIN_TRADE_QTY
from src.order_roundtrip import decide_base_quantity


class OrderRoundtripTests(unittest.TestCase):
    def test_default_buy_quantity_uses_project_min_trade_qty(self) -> None:
        self.assertEqual(decide_base_quantity({}, "BUY"), MIN_TRADE_QTY)

    def test_sell_quantity_uses_previous_filled_buy_quantity(self) -> None:
        state = {
            "live_order_response": {
                "side": "BUY",
                "status": "FILLED",
                "executedQty": "0.0123",
            }
        }

        self.assertEqual(decide_base_quantity(state, "SELL"), 0.0123)


if __name__ == "__main__":
    unittest.main()
