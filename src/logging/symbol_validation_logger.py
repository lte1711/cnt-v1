from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from config import SYMBOL_VALIDATION_LOG_FILE


def calculate_slippage_pct(
    signal_price: float | None,
    fill_price: float | None,
    side: str = "BUY",
) -> float | None:
    if signal_price is None or fill_price is None:
        return None

    signal = float(signal_price)
    fill = float(fill_price)
    if signal <= 0 or fill <= 0:
        return None

    if side.upper() == "SELL":
        return (signal - fill) / signal

    return (fill - signal) / signal


def build_symbol_validation_event(
    *,
    event: str,
    symbol: str,
    strategy_name: str,
    decision_id: str | None = None,
    signal_price: float | None = None,
    validated_price: float | None = None,
    validated_qty: float | None = None,
    notional_value: float | None = None,
    side: str = "BUY",
    orderbook: dict | None = None,
    exchange: dict | None = None,
    reason: str | None = None,
    close_pnl_estimate: float | None = None,
) -> dict[str, Any]:
    exchange_payload = dict(exchange or {})
    fill_price = exchange_payload.get("fill_price")
    executed_qty = float(exchange_payload.get("executed_qty", 0.0) or 0.0)
    requested_qty = float(validated_qty or 0.0)
    exchange_status = str(exchange_payload.get("status", "UNKNOWN"))
    order_reject_flag = exchange_status in {"REJECTED", "EXPIRED"} or event == "order_rejected"
    partial_fill_flag = (
        executed_qty > 0
        and requested_qty > 0
        and executed_qty < requested_qty
        and exchange_status not in {"FILLED"}
    )

    return {
        "schema_version": "1.0",
        "event": event,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "symbol": symbol,
        "strategy_name": strategy_name,
        "decision_id": decision_id,
        "signal_price": signal_price,
        "validated_price": validated_price,
        "validated_qty": validated_qty,
        "notional_value": notional_value,
        "side": side.upper(),
        "orderbook": dict(orderbook or {}),
        "exchange": exchange_payload,
        "slippage_pct": calculate_slippage_pct(signal_price, fill_price, side),
        "order_reject_flag": order_reject_flag,
        "partial_fill_flag": partial_fill_flag,
        "close_pnl_estimate": close_pnl_estimate,
        "reason": reason or "not_recorded",
    }


def append_symbol_validation_event(
    event_payload: dict,
    log_file: str | Path = SYMBOL_VALIDATION_LOG_FILE,
) -> None:
    target = Path(log_file)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as file_handle:
        file_handle.write(json.dumps(event_payload, ensure_ascii=False, sort_keys=True) + "\n")
