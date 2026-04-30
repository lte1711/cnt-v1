from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from config import SYMBOL_VALIDATION_LOG_FILE, SYMBOL_VALIDATION_REPORT_FILE


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _load_jsonl(log_file: Path) -> list[dict]:
    if not log_file.exists():
        return []

    events: list[dict] = []
    for raw_line in log_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            events.append(payload)
    return events


def _profit_factor(gross_profit: float, gross_loss: float) -> float:
    if gross_loss <= 0:
        return 999999.0 if gross_profit > 0 else 0.0
    return gross_profit / gross_loss


def _max_consecutive_losses(pnls: list[float]) -> int:
    current = 0
    maximum = 0
    for pnl in pnls:
        if pnl < 0:
            current += 1
            maximum = max(maximum, current)
        else:
            current = 0
    return maximum


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2.0


def build_symbol_validation_report(
    log_file: str | Path = SYMBOL_VALIDATION_LOG_FILE,
    *,
    symbol: str | None = None,
) -> dict:
    events = _load_jsonl(Path(log_file))
    if symbol:
        events = [event for event in events if event.get("symbol") == symbol]

    order_events = [
        event
        for event in events
        if event.get("event") in {"order_result", "order_rejected", "entry_order_result", "exit_order_result"}
    ]
    close_events = [
        event
        for event in events
        if event.get("close_pnl_estimate") is not None or event.get("realized_pnl") is not None
    ]

    pnls = [
        _safe_float(event.get("close_pnl_estimate", event.get("realized_pnl")))
        for event in close_events
    ]
    wins = [pnl for pnl in pnls if pnl > 0]
    losses = [pnl for pnl in pnls if pnl <= 0]
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    slippages = [
        _safe_float(event.get("slippage_pct"))
        for event in order_events
        if event.get("slippage_pct") is not None
    ]
    reject_count = sum(1 for event in order_events if bool(event.get("order_reject_flag")))
    partial_fill_count = sum(1 for event in order_events if bool(event.get("partial_fill_flag")))
    orderbook_events = [event for event in order_events if isinstance(event.get("orderbook"), dict)]
    usable_orderbook_count = sum(1 for event in orderbook_events if event.get("orderbook", {}).get("usable") is True)

    closed_trades = len(pnls)
    order_count = len(order_events)
    symbols = sorted({str(event.get("symbol")) for event in events if event.get("symbol")})

    return {
        "schema_version": "1.0",
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "mode": "READ_ONLY_REPORT",
        "source_log": str(log_file),
        "symbol_filter": symbol,
        "symbols": symbols,
        "event_count": len(events),
        "order_count": order_count,
        "closed_trades": closed_trades,
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": len(wins) / closed_trades if closed_trades else 0.0,
        "gross_profit": gross_profit,
        "gross_loss": gross_loss,
        "net_pnl": gross_profit - gross_loss,
        "avg_win": gross_profit / len(wins) if wins else 0.0,
        "avg_loss": gross_loss / len(losses) if losses else 0.0,
        "realized_expectancy": (gross_profit - gross_loss) / closed_trades if closed_trades else 0.0,
        "realized_profit_factor": _profit_factor(gross_profit, gross_loss),
        "max_consecutive_losses": _max_consecutive_losses(pnls),
        "order_reject_count": reject_count,
        "order_reject_rate": reject_count / order_count if order_count else 0.0,
        "partial_fill_count": partial_fill_count,
        "partial_fill_rate": partial_fill_count / order_count if order_count else 0.0,
        "slippage": {
            "sample_count": len(slippages),
            "avg_pct": sum(slippages) / len(slippages) if slippages else None,
            "median_pct": _median(slippages),
            "max_abs_pct": max((abs(value) for value in slippages), default=None),
        },
        "orderbook": {
            "sample_count": len(orderbook_events),
            "usable_count": usable_orderbook_count,
            "usable_rate": usable_orderbook_count / len(orderbook_events) if orderbook_events else 0.0,
            "avg_spread_pct": (
                sum(_safe_float(event.get("orderbook", {}).get("spread_pct")) for event in orderbook_events)
                / len(orderbook_events)
                if orderbook_events
                else None
            ),
            "avg_imbalance": (
                sum(_safe_float(event.get("orderbook", {}).get("imbalance")) for event in orderbook_events)
                / len(orderbook_events)
                if orderbook_events
                else None
            ),
        },
        "promotion_checks": {
            "closed_trades_ge_30": closed_trades >= 30,
            "realized_pf_ge_1_3": _profit_factor(gross_profit, gross_loss) >= 1.3,
            "realized_expectancy_positive": ((gross_profit - gross_loss) / closed_trades if closed_trades else 0.0) > 0,
            "order_reject_rate_lt_2pct": (reject_count / order_count if order_count else 0.0) < 0.02,
            "max_consecutive_losses_lte_3": _max_consecutive_losses(pnls) <= 3,
        },
        "decision": "review_required_before_symbol_promotion",
    }


def save_symbol_validation_report(
    report: dict,
    report_file: str | Path = SYMBOL_VALIDATION_REPORT_FILE,
) -> None:
    target = Path(report_file)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def generate_and_save_symbol_validation_report(
    *,
    log_file: str | Path = SYMBOL_VALIDATION_LOG_FILE,
    report_file: str | Path = SYMBOL_VALIDATION_REPORT_FILE,
    symbol: str | None = None,
) -> dict:
    report = build_symbol_validation_report(log_file, symbol=symbol)
    save_symbol_validation_report(report, report_file)
    return report
