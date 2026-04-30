from __future__ import annotations

from config import MIN_TRADE_QTY


def decide_next_side(previous_state: dict) -> str:
    live_order_response = previous_state.get("live_order_response")

    if not isinstance(live_order_response, dict):
        return "BUY"

    previous_side = str(live_order_response.get("side", "")).upper()
    previous_status = str(live_order_response.get("status", "")).upper()

    if previous_side == "BUY" and previous_status == "FILLED":
        return "SELL"

    return "BUY"


def decide_base_quantity(previous_state: dict, next_side: str) -> float:
    live_order_response = previous_state.get("live_order_response")

    if next_side == "SELL" and isinstance(live_order_response, dict):
        executed_qty = live_order_response.get("executedQty")

        if executed_qty not in (None, "", "0", 0):
            return float(executed_qty)

    return MIN_TRADE_QTY
