from __future__ import annotations

from datetime import datetime

from config import ENABLE_PARTIAL_EXIT
from src.models.exit_signal import ExitSignal
from src.order_validator import prepare_partial_exit_quantity


def _no_exit(reason: str = "no_exit_condition_met") -> ExitSignal:
    return ExitSignal(
        should_exit=False,
        exit_type="NONE",
        reason=reason,
        target_price=None,
        stop_price=None,
        partial_qty=None,
    )


def evaluate_exit(open_trade: dict, current_price: float, state: dict, filters: dict) -> ExitSignal:
    del state

    stop_price = open_trade.get("stop_price")
    target_price = open_trade.get("target_price")
    highest_price = float(open_trade.get("highest_price_since_entry", open_trade.get("entry_price", current_price)))
    trailing_stop_pct = open_trade.get("trailing_stop_pct")
    entry_time = open_trade.get("entry_time")
    time_based_exit_minutes = open_trade.get("time_based_exit_minutes")
    partial_exit_levels = open_trade.get("partial_exit_levels") or []
    partial_exit_progress = int(open_trade.get("partial_exit_progress", 0) or 0)
    entry_qty = float(open_trade.get("entry_qty", 0.0) or 0.0)

    if stop_price is not None and current_price <= float(stop_price):
        return ExitSignal(True, "STOP", "stop_price_triggered", target_price, float(stop_price), None)

    if trailing_stop_pct is not None:
        trailing_price = highest_price * (1 - float(trailing_stop_pct))
        if current_price <= trailing_price:
            return ExitSignal(
                True,
                "TRAILING_STOP",
                "trailing_stop_triggered",
                target_price,
                trailing_price,
                None,
            )

    if target_price is not None and current_price >= float(target_price):
        return ExitSignal(True, "TARGET", "target_price_triggered", float(target_price), stop_price, None)

    if ENABLE_PARTIAL_EXIT and partial_exit_progress < len(partial_exit_levels):
        next_level = partial_exit_levels[partial_exit_progress]
        partial_target_price = float(next_level.get("target_price", 0) or 0)

        if partial_target_price > 0 and current_price >= partial_target_price:
            partial_qty_result = prepare_partial_exit_quantity(
                entry_qty=entry_qty,
                qty_ratio=float(next_level.get("qty_ratio", 0) or 0),
                lot_size_filter=filters.get("lot_size_filter", {}),
            )

            if partial_qty_result["valid"]:
                return ExitSignal(
                    True,
                    "PARTIAL",
                    "partial_exit_target_triggered",
                    partial_target_price,
                    stop_price,
                    float(partial_qty_result["adjusted_qty"]),
                )

            return _no_exit("partial_exit_qty_below_min_qty")

    if time_based_exit_minutes is not None and entry_time:
        try:
            entry_dt = datetime.strptime(str(entry_time), "%Y-%m-%d %H:%M:%S")
            elapsed_minutes = (datetime.now() - entry_dt).total_seconds() / 60.0
            if elapsed_minutes >= float(time_based_exit_minutes):
                return ExitSignal(True, "TIME_EXIT", "time_based_exit_triggered", target_price, stop_price, None)
        except ValueError:
            return _no_exit("invalid_entry_time")

    return _no_exit()
