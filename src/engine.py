from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from requests import HTTPError

from binance_client import (
    extract_symbol_filters,
    get_price,
    get_server_time,
    get_symbol_info,
    has_api_credentials,
    ping,
)
from config import (
    ACTIVE_STRATEGY,
    AUXILIARY_RECOVERY_STATUS_FILE,
    BINANCE_BASE_URL,
    ENABLE_PARTIAL_EXIT,
    ENABLE_TEST_ORDER_VALIDATION,
    LIVE_GATE_DECISION_FILE,
    LOG_FILE,
    PERFORMANCE_SNAPSHOT_FILE,
    PORTFOLIO_LOG_FILE,
    PORTFOLIO_STATE_FILE,
    SHADOW_BREAKOUT_V2_LOG_FILE,
    SHADOW_BREAKOUT_V2_SNAPSHOT_FILE,
    SHADOW_BREAKOUT_V3_LOG_FILE,
    SHADOW_BREAKOUT_V3_SNAPSHOT_FILE,
    STATE_FILE,
    STRATEGY_METRICS_FILE,
    STRATEGY_PARAMS,
    MIN_TRADE_QTY,
    SYMBOL,
    TIME_EXIT_MINUTES,
    TRAILING_STOP_PCT,
)
from src.analytics.auxiliary_recovery_status import (
    build_auxiliary_recovery_status,
    save_auxiliary_recovery_status,
)
from src.analytics.performance_report import generate_performance_report
from src.analytics.performance_snapshot import generate_and_save_performance_snapshot
from src.analytics.strategy_metrics import (
    build_expectancy_snapshot,
    increment_signals_selected,
    load_strategy_metrics,
    record_closed_trade,
    save_strategy_metrics,
)
from src.account_reader import get_account_info
from src.balance_reader import extract_asset_balance
from src.execution_decider import decide_execution
from src.entry_gate import evaluate_entry_gate_from_signal
from src.logging.portfolio_logger import append_portfolio_log
from src.log_writer import append_log
from src.models.exit_signal import ExitSignal
from src.models.strategy_signal import StrategySignal
from src.order_cancel import cancel_order
from src.order_executor import send_live_testnet_order, send_test_order
from src.order_payload_builder import build_limit_order_payload
from src.order_query import get_open_orders, get_order
from src.order_validator import (
    auto_adjust_order_inputs,
    validate_order,
    validate_quantity,
)
from src.portfolio.strategy_orchestrator import get_ranked_signal_selection
from src.risk.enhanced_exit_manager import evaluate_exit
from src.shadow_eval import append_shadow_log, evaluate_breakout_v2_shadow, update_shadow_snapshot
from src.shadow.breakout_v3_shadow_eval import (
    append_breakout_v3_shadow_log,
    evaluate_breakout_v3_shadow_for_symbol,
    update_breakout_v3_shadow_snapshot,
)
from src.state.state_manager import build_portfolio_state, load_portfolio_state, save_portfolio_state
from src.state_writer import write_state
from src.validation.live_gate_evaluator import evaluate_live_gate, save_live_gate_decision


SCHEMA_VERSION = "1.0"


def should_stop(price: float, stop_price: float) -> bool:
    return price <= stop_price


def should_exit_long(price: float, target_price: float) -> bool:
    return price >= target_price


def _default_risk_metrics() -> dict:
    return {
        "daily_loss_count": 0,
        "consecutive_losses": 0,
        "last_loss_time": None,
    }


def _normalize_risk_metrics(risk_metrics: dict | None) -> dict:
    if not isinstance(risk_metrics, dict):
        return _default_risk_metrics()

    return {
        "daily_loss_count": int(risk_metrics.get("daily_loss_count", 0) or 0),
        "consecutive_losses": int(risk_metrics.get("consecutive_losses", 0) or 0),
        "last_loss_time": risk_metrics.get("last_loss_time"),
    }


def _reset_daily_loss_count_if_needed(risk_metrics: dict | None, timestamp: str) -> dict:
    normalized = _normalize_risk_metrics(risk_metrics)
    last_loss_time = normalized.get("last_loss_time")
    if not isinstance(last_loss_time, str):
        return normalized

    try:
        current_day = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S").date()
        last_loss_day = datetime.strptime(last_loss_time, "%Y-%m-%d %H:%M:%S").date()
    except ValueError:
        return normalized

    if current_day != last_loss_day:
        normalized["daily_loss_count"] = 0

    return normalized


def _mark_loss(risk_metrics: dict | None, timestamp: str) -> dict:
    updated = _reset_daily_loss_count_if_needed(risk_metrics, timestamp)
    updated["daily_loss_count"] += 1
    updated["consecutive_losses"] += 1
    updated["last_loss_time"] = timestamp
    return updated


def _mark_profit(risk_metrics: dict | None, timestamp: str) -> dict:
    updated = _reset_daily_loss_count_if_needed(risk_metrics, timestamp)
    updated["consecutive_losses"] = 0
    return updated


def _update_risk_metrics_for_close(
    *,
    action: str,
    open_trade: dict | None,
    fill_price: float,
    risk_metrics: dict | None,
    timestamp: str,
) -> dict:
    if action in {"STOP_MARKET_FILLED", "TRAILING_STOP_FILLED"}:
        return _mark_loss(risk_metrics, timestamp)

    if action == "SELL_FILLED" and isinstance(open_trade, dict):
        entry_price = float(open_trade.get("entry_price", 0.0) or 0.0)
        if entry_price > 0 and fill_price > 0 and fill_price < entry_price:
            return _mark_loss(risk_metrics, timestamp)
        return _mark_profit(risk_metrics, timestamp)

    return _reset_daily_loss_count_if_needed(risk_metrics, timestamp)


def _load_state(path: Path) -> dict:
    if not path.exists():
        return {}

    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            return {}

        loaded.setdefault("schema_version", SCHEMA_VERSION)
        loaded.setdefault("strategy_name", ACTIVE_STRATEGY)
        loaded["risk_metrics"] = _normalize_risk_metrics(loaded.get("risk_metrics"))
        return loaded
    except Exception:
        return {}


def _normalize_pending_order(pending: dict | None) -> dict | None:
    if not isinstance(pending, dict):
        return None

    required = {"orderId", "status", "side"}
    if not required.issubset(pending):
        return None

    order_id = int(pending["orderId"])
    if order_id <= 0:
        return None

    normalized = {
        "orderId": order_id,
        "status": str(pending["status"]).upper(),
        "side": str(pending["side"]).upper(),
    }

    if "strategy_name" in pending:
        normalized["strategy_name"] = str(pending["strategy_name"])

    if "decision_id" in pending and pending["decision_id"] is not None:
        normalized["decision_id"] = str(pending["decision_id"])

    if "market_features" in pending and isinstance(pending["market_features"], dict):
        normalized["market_features"] = pending["market_features"]

    if "stop_price" in pending and pending["stop_price"] is not None:
        normalized["stop_price"] = float(pending["stop_price"])

    if "target_price" in pending and pending["target_price"] is not None:
        normalized["target_price"] = float(pending["target_price"])

    if "trailing_stop_pct" in pending and pending["trailing_stop_pct"] is not None:
        normalized["trailing_stop_pct"] = float(pending["trailing_stop_pct"])

    if "time_based_exit_minutes" in pending and pending["time_based_exit_minutes"] is not None:
        normalized["time_based_exit_minutes"] = int(pending["time_based_exit_minutes"])

    if "partial_exit_levels" in pending and pending["partial_exit_levels"] is not None:
        normalized["partial_exit_levels"] = [
            {
                "qty_ratio": float(item["qty_ratio"]),
                "target_price": float(item["target_price"]),
            }
            for item in pending["partial_exit_levels"]
        ]

    if "exit_type" in pending:
        normalized["exit_type"] = str(pending["exit_type"]).upper()

    if "partial_qty" in pending and pending["partial_qty"] is not None:
        normalized["partial_qty"] = float(pending["partial_qty"])

    return normalized


def _build_exit_model_from_strategy(strategy_name: str, entry_price: float) -> tuple[float | None, float | None]:
    params = STRATEGY_PARAMS.get(strategy_name, {})
    target_pct = params.get("target_pct")
    stop_loss_pct = params.get("stop_loss_pct")

    if target_pct is None or stop_loss_pct is None:
        return None, None

    target_price = entry_price * (1 + float(target_pct))
    stop_price = entry_price * (1 - float(stop_loss_pct))
    return stop_price, target_price


def _select_exit_limit_price(exit_signal: ExitSignal, current_price: float) -> float:
    if exit_signal.exit_type in {"TARGET", "PARTIAL"}:
        if exit_signal.target_price is None:
            raise ValueError(f"missing target_price for {exit_signal.exit_type} limit exit")
        return float(exit_signal.target_price)

    return current_price


def _normalize_open_trade(open_trade: dict | None) -> dict | None:
    if not isinstance(open_trade, dict):
        return None

    required = {"status", "entry_price", "entry_qty", "entry_order_id", "entry_side"}
    if not required.issubset(open_trade):
        return None

    strategy_name = str(open_trade.get("strategy_name") or ACTIVE_STRATEGY)
    entry_price = float(open_trade["entry_price"])
    entry_order_id = int(open_trade["entry_order_id"])
    if entry_order_id <= 0:
        return None

    stop_price = open_trade.get("stop_price")
    target_price = open_trade.get("target_price")

    if stop_price is None or target_price is None:
        stop_price, target_price = _build_exit_model_from_strategy(strategy_name, entry_price)

    normalized = {
        "status": str(open_trade["status"]),
        "entry_price": entry_price,
        "entry_qty": float(open_trade["entry_qty"]),
        "entry_order_id": entry_order_id,
        "entry_side": str(open_trade["entry_side"]).upper(),
        "strategy_name": strategy_name,
        "stop_price": stop_price,
        "target_price": target_price,
        "trailing_stop_pct": (
            float(open_trade["trailing_stop_pct"])
            if open_trade.get("trailing_stop_pct") is not None
            else None
        ),
        "partial_exit_levels": [
            {
                "qty_ratio": float(item["qty_ratio"]),
                "target_price": float(item["target_price"]),
            }
            for item in (open_trade.get("partial_exit_levels") or [])
        ],
        "time_based_exit_minutes": (
            int(open_trade["time_based_exit_minutes"])
            if open_trade.get("time_based_exit_minutes") is not None
            else None
        ),
        "highest_price_since_entry": float(
            open_trade.get("highest_price_since_entry", entry_price) or entry_price
        ),
        "entry_time": open_trade.get("entry_time"),
        "partial_exit_progress": int(open_trade.get("partial_exit_progress", 0) or 0),
    }

    if open_trade.get("decision_id") is not None:
        normalized["decision_id"] = str(open_trade["decision_id"])

    if isinstance(open_trade.get("market_features"), dict):
        normalized["market_features"] = open_trade["market_features"]

    return normalized


def _resolve_strategy_name(pending: dict | None, open_trade: dict | None) -> str:
    if isinstance(open_trade, dict) and open_trade.get("strategy_name"):
        return str(open_trade["strategy_name"])

    if isinstance(pending, dict) and pending.get("strategy_name"):
        return str(pending["strategy_name"])

    return ACTIVE_STRATEGY


def _build_state(
    *,
    timestamp: str,
    action: str,
    price: float,
    pending: dict | None,
    open_trade: dict | None,
    risk_metrics: dict | None = None,
    strategy_name_override: str | None = None,
) -> dict:
    normalized_pending = _normalize_pending_order(pending)
    normalized_open_trade = _normalize_open_trade(open_trade)

    return {
        "schema_version": SCHEMA_VERSION,
        "strategy_name": (
            str(strategy_name_override)
            if strategy_name_override
            else _resolve_strategy_name(normalized_pending, normalized_open_trade)
        ),
        "last_run_time": timestamp,
        "status": "stopped",
        "symbol": SYMBOL,
        "pending_order": normalized_pending,
        "open_trade": normalized_open_trade,
        "action": action,
        "price": price,
        "risk_metrics": _normalize_risk_metrics(risk_metrics),
    }


def _save_and_finish(
    *,
    state_file: Path,
    log_file: Path,
    state: dict,
    timestamp: str,
    action: str,
    price: float,
    pending: dict | None,
    open_trade: dict | None,
    reason: str = "ok",
    risk_metrics: dict | None = None,
    portfolio_state_file: Path | None = None,
    cash_balance: float = 0.0,
    strategy_name_override: str | None = None,
) -> None:
    next_state = _build_state(
        timestamp=timestamp,
        action=action,
        price=price,
        pending=pending,
        open_trade=open_trade,
        risk_metrics=risk_metrics,
        strategy_name_override=strategy_name_override,
    )
    state.clear()
    state.update(next_state)

    write_state(state_file, next_state)
    if portfolio_state_file is not None:
        save_portfolio_state(portfolio_state_file, build_portfolio_state(next_state, cash_balance=cash_balance))

    append_log(
        log_file,
        (
            f"[{timestamp}] action={action} price={price} pending={pending} "
            f"open_trade={open_trade} strategy_name={next_state['strategy_name']} reason={reason}"
        ),
    )

    try:
        project_root = state_file.parent.parent
        snapshot = generate_and_save_performance_snapshot(
            metrics_file=project_root / STRATEGY_METRICS_FILE,
            portfolio_log_file=project_root / PORTFOLIO_LOG_FILE,
            snapshot_file=project_root / PERFORMANCE_SNAPSHOT_FILE,
            runtime_log_file=project_root / LOG_FILE,
            portfolio_state_file=project_root / PORTFOLIO_STATE_FILE,
        )
        generate_performance_report(
            project_root / "docs/CNT v2 TESTNET PERFORMANCE REPORT.md",
            snapshot,
        )
        live_gate_decision = evaluate_live_gate(snapshot)
        save_live_gate_decision(
            project_root / LIVE_GATE_DECISION_FILE,
            live_gate_decision,
        )
        save_auxiliary_recovery_status(
            project_root / AUXILIARY_RECOVERY_STATUS_FILE,
            build_auxiliary_recovery_status(
                snapshot=snapshot,
                strategy_metrics=load_strategy_metrics(project_root / STRATEGY_METRICS_FILE),
                state=next_state,
                portfolio_state=load_portfolio_state(project_root / PORTFOLIO_STATE_FILE),
                live_gate_decision=live_gate_decision,
            ),
        )
    except Exception:
        pass


def _run_breakout_v2_shadow(*, project_root: Path, symbol: str) -> None:
    params = STRATEGY_PARAMS.get("breakout_v2")
    if not isinstance(params, dict):
        return

    try:
        event = evaluate_breakout_v2_shadow(symbol, params)
    except Exception:
        return

    try:
        append_shadow_log(project_root / SHADOW_BREAKOUT_V2_LOG_FILE, event)
    except Exception:
        pass

    try:
        update_shadow_snapshot(project_root / SHADOW_BREAKOUT_V2_SNAPSHOT_FILE, event)
    except Exception:
        pass


def _run_breakout_v3_shadow(*, project_root: Path, symbol: str) -> None:
    params = STRATEGY_PARAMS.get("breakout_v3")
    if not isinstance(params, dict):
        return

    try:
        event = evaluate_breakout_v3_shadow_for_symbol(symbol, params)
    except Exception:
        return

    log_file = project_root / SHADOW_BREAKOUT_V3_LOG_FILE
    snapshot_file = project_root / SHADOW_BREAKOUT_V3_SNAPSHOT_FILE

    try:
        append_breakout_v3_shadow_log(log_file, event)
    except Exception:
        pass

    try:
        update_breakout_v3_shadow_snapshot(snapshot_file, log_file)
    except Exception:
        pass


def _estimate_close_pnl(open_trade: dict | None, fill_price: float) -> float:
    if not isinstance(open_trade, dict):
        return 0.0

    entry_price = float(open_trade.get("entry_price", 0.0) or 0.0)
    entry_qty = float(open_trade.get("entry_qty", 0.0) or 0.0)
    if entry_price <= 0 or entry_qty <= 0 or fill_price <= 0:
        return 0.0

    return (fill_price - entry_price) * entry_qty


def _find_open_order_by_id(open_orders: list, order_id: int) -> dict | None:
    for item in open_orders:
        if int(item.get("orderId", 0)) == int(order_id):
            return item
    return None


def _is_missing_order_error(error: Exception) -> bool:
    message = str(error).lower()
    return "code=-2013" in message or "order does not exist" in message


def _extract_fill_price(order_info: dict) -> float:
    order_price = float(order_info.get("price", 0) or 0)
    if order_price > 0:
        return order_price

    executed_qty = float(order_info.get("executedQty", 0) or 0)
    cumulative_quote_qty = float(order_info.get("cummulativeQuoteQty", 0) or 0)

    if executed_qty > 0 and cumulative_quote_qty > 0:
        return cumulative_quote_qty / executed_qty

    return 0.0


def _align_quantity_to_step(qty: float, filters: dict) -> float:
    lot_size_filter = filters.get("lot_size_filter", {})
    quantity_check = validate_quantity(qty, lot_size_filter)
    return float(quantity_check.get("aligned_qty", qty))


def _serialize_partial_exit_levels(partial_exit_levels) -> list[dict] | None:
    if not partial_exit_levels:
        return None

    serialized: list[dict] = []
    for item in partial_exit_levels:
        if isinstance(item, dict):
            serialized.append(
                {
                    "qty_ratio": float(item["qty_ratio"]),
                    "target_price": float(item["target_price"]),
                }
            )
        else:
            serialized.append(
                {
                    "qty_ratio": float(item.qty_ratio),
                    "target_price": float(item.target_price),
                }
            )
    return serialized


def _build_exit_extension_fields(signal_exit_model, entry_price: float) -> dict:
    trailing_stop_pct = TRAILING_STOP_PCT
    time_based_exit_minutes = TIME_EXIT_MINUTES
    partial_exit_levels = None

    if signal_exit_model is not None:
        if signal_exit_model.trailing_stop_pct is not None:
            trailing_stop_pct = float(signal_exit_model.trailing_stop_pct)
        if signal_exit_model.time_based_exit_minutes is not None:
            time_based_exit_minutes = int(signal_exit_model.time_based_exit_minutes)
        if ENABLE_PARTIAL_EXIT:
            partial_exit_levels = _serialize_partial_exit_levels(signal_exit_model.partial_exit_levels)

    return {
        "trailing_stop_pct": trailing_stop_pct,
        "partial_exit_levels": partial_exit_levels if ENABLE_PARTIAL_EXIT else None,
        "time_based_exit_minutes": time_based_exit_minutes,
        "highest_price_since_entry": entry_price,
        "entry_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "partial_exit_progress": 0,
    }


def _compact_json(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _market_context_label(market_features: dict | None) -> str:
    if not isinstance(market_features, dict):
        return "UNKNOWN"
    return str(market_features.get("multi_timeframe_trend") or "UNKNOWN")


def _signal_observability_fields(signal: StrategySignal) -> str:
    market_features = signal.market_features if isinstance(signal.market_features, dict) else {}
    return (
        f"decision_id={signal.decision_id or 'UNKNOWN'} "
        f"market_context={_market_context_label(market_features)} "
        f"market_features={_compact_json(market_features)}"
    )


def _trade_observability_fields(open_trade: dict | None) -> str:
    if not isinstance(open_trade, dict):
        return "decision_id=UNKNOWN market_context=UNKNOWN market_features={}"
    market_features = open_trade.get("market_features") if isinstance(open_trade.get("market_features"), dict) else {}
    return (
        f"decision_id={open_trade.get('decision_id') or 'UNKNOWN'} "
        f"market_context={_market_context_label(market_features)} "
        f"market_features={_compact_json(market_features)}"
    )


def _build_pending_order_from_response(
    order_response: dict,
    side: str,
    strategy_name: str | None = None,
    stop_price: float | None = None,
    target_price: float | None = None,
    trailing_stop_pct: float | None = None,
    partial_exit_levels: list[dict] | None = None,
    time_based_exit_minutes: int | None = None,
    exit_type: str | None = None,
    partial_qty: float | None = None,
    decision_id: str | None = None,
    market_features: dict | None = None,
) -> dict:
    pending = {
        "orderId": int(order_response["orderId"]),
        "status": str(order_response["status"]).upper(),
        "side": side.upper(),
    }

    if strategy_name is not None:
        pending["strategy_name"] = strategy_name

    if decision_id is not None:
        pending["decision_id"] = decision_id

    if isinstance(market_features, dict):
        pending["market_features"] = market_features

    if stop_price is not None:
        pending["stop_price"] = stop_price

    if target_price is not None:
        pending["target_price"] = target_price

    if trailing_stop_pct is not None:
        pending["trailing_stop_pct"] = trailing_stop_pct

    if partial_exit_levels is not None:
        pending["partial_exit_levels"] = partial_exit_levels

    if time_based_exit_minutes is not None:
        pending["time_based_exit_minutes"] = time_based_exit_minutes

    if exit_type is not None:
        pending["exit_type"] = exit_type.upper()

    if partial_qty is not None:
        pending["partial_qty"] = partial_qty

    return pending


def _is_pending_limit_exit(pending: dict | None) -> bool:
    normalized_pending = _normalize_pending_order(pending)
    if normalized_pending is None:
        return False

    if normalized_pending.get("side") != "SELL":
        return False

    return str(normalized_pending.get("exit_type") or "").upper() in {"TARGET", "TIME_EXIT", "PARTIAL"}


def _cancel_pending_exit_order(symbol: str, pending: dict) -> tuple[bool, str]:
    normalized_pending = _normalize_pending_order(pending)
    if normalized_pending is None:
        return False, "invalid_pending_exit_state"

    order_id = int(normalized_pending["orderId"])

    try:
        cancel_response = cancel_order(symbol, order_id)
    except HTTPError as exc:
        detail = str(exc)
        if "code=-2011" in detail:
            return True, "pending_exit_missing_assumed_cleared"
        return False, f"pending_exit_cancel_failed:{detail}"

    cancel_status = str(cancel_response.get("status", "")).upper()
    if cancel_status in {"CANCELED", "CANCELLED", "EXPIRED", "PENDING_CANCEL"}:
        return True, "pending_exit_canceled_for_protective_override"

    if int(cancel_response.get("orderId", 0) or 0) == order_id:
        return True, "pending_exit_cancel_acknowledged"

    return False, "pending_exit_cancel_not_confirmed"


def _execute_protective_exit(
    *,
    symbol: str,
    price: float,
    timestamp: str,
    open_trade: dict,
    exit_signal: ExitSignal,
    filters: dict,
    risk_metrics: dict,
    strategy_metrics: dict,
    strategy_metrics_file: Path,
    portfolio_log_file: Path,
) -> tuple[str, dict | None, dict | None, str, dict]:
    entry_qty = float(open_trade["entry_qty"])
    aligned_stop_qty = _align_quantity_to_step(entry_qty, filters)

    if aligned_stop_qty <= 0:
        return (
            "STOP_REJECTED_INVALID_QTY",
            None,
            open_trade,
            "stop_market_qty_not_valid",
            risk_metrics,
        )

    payload = {
        "symbol": symbol,
        "side": "SELL",
        "type": "MARKET",
        "quantity": str(aligned_stop_qty),
    }

    order_response = send_live_testnet_order(payload)
    order_status = str(order_response.get("status", "")).upper()

    if order_status == "FILLED":
        fill_price = _extract_fill_price(order_response) or price
        filled_action = (
            "TRAILING_STOP_FILLED"
            if exit_signal.exit_type == "TRAILING_STOP"
            else "STOP_MARKET_FILLED"
        )
        strategy_name = str((open_trade or {}).get("strategy_name") or ACTIVE_STRATEGY)
        close_pnl_estimate = _estimate_close_pnl(open_trade, fill_price)
        record_closed_trade(strategy_metrics, strategy_name, close_pnl_estimate)
        save_strategy_metrics(strategy_metrics_file, strategy_metrics)
        append_portfolio_log(
            portfolio_log_file,
            (
                f"symbol={symbol} selected_strategy={strategy_name} close_action={filled_action} "
                f"close_pnl_estimate={close_pnl_estimate} "
                f"{_trade_observability_fields(open_trade)} "
                f"strategy_expectancy_snapshot={build_expectancy_snapshot(strategy_metrics, strategy_name)}"
            ),
        )
        updated_risk_metrics = _update_risk_metrics_for_close(
            action=filled_action,
            open_trade=open_trade,
            fill_price=fill_price,
            risk_metrics=risk_metrics,
            timestamp=timestamp,
        )
        return (
            filled_action,
            None,
            None,
            (
                "trailing_stop_market_filled"
                if exit_signal.exit_type == "TRAILING_STOP"
                else "protective_stop_market_filled"
            ),
            updated_risk_metrics,
        )

    pending = _build_pending_order_from_response(
        order_response,
        "SELL",
        exit_type=exit_signal.exit_type,
    )

    return (
        "TRAILING_STOP_SUBMITTED" if exit_signal.exit_type == "TRAILING_STOP" else "STOP_MARKET_SUBMITTED",
        pending,
        open_trade,
        (
            "trailing_stop_market_submitted"
            if exit_signal.exit_type == "TRAILING_STOP"
            else "protective_stop_market_submitted"
        ),
        risk_metrics,
    )


def _build_open_trade_from_order(order_info: dict, pending: dict | None = None) -> dict:
    entry_price = _extract_fill_price(order_info)
    strategy_name = ACTIVE_STRATEGY
    stop_price = None
    target_price = None
    trailing_stop_pct = TRAILING_STOP_PCT
    partial_exit_levels = None
    time_based_exit_minutes = TIME_EXIT_MINUTES
    entry_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    partial_exit_progress = 0
    decision_id = None
    market_features = None

    if isinstance(pending, dict):
        strategy_name = str(pending.get("strategy_name") or ACTIVE_STRATEGY)
        stop_price = pending.get("stop_price")
        target_price = pending.get("target_price")
        trailing_stop_pct = pending.get("trailing_stop_pct", TRAILING_STOP_PCT)
        partial_exit_levels = pending.get("partial_exit_levels")
        time_based_exit_minutes = pending.get("time_based_exit_minutes", TIME_EXIT_MINUTES)
        entry_time = pending.get("entry_time", entry_time)
        partial_exit_progress = int(pending.get("partial_exit_progress", 0) or 0)
        decision_id = pending.get("decision_id")
        market_features = pending.get("market_features") if isinstance(pending.get("market_features"), dict) else None

    if stop_price is None or target_price is None:
        stop_price, target_price = _build_exit_model_from_strategy(strategy_name, entry_price)

    open_trade = {
        "status": "OPEN",
        "entry_price": entry_price,
        "entry_qty": float(order_info["executedQty"]),
        "entry_order_id": int(order_info["orderId"]),
        "entry_side": "BUY",
        "strategy_name": strategy_name,
        "stop_price": stop_price,
        "target_price": target_price,
        "trailing_stop_pct": trailing_stop_pct,
        "partial_exit_levels": partial_exit_levels,
        "time_based_exit_minutes": time_based_exit_minutes,
        "highest_price_since_entry": entry_price,
        "entry_time": entry_time,
        "partial_exit_progress": partial_exit_progress,
    }

    if decision_id is not None:
        open_trade["decision_id"] = str(decision_id)

    if isinstance(market_features, dict):
        open_trade["market_features"] = market_features

    return open_trade


def _update_open_trade_runtime_fields(open_trade: dict, current_price: float) -> dict:
    normalized = dict(open_trade)
    previous_highest = float(normalized.get("highest_price_since_entry", normalized.get("entry_price", current_price)))
    normalized["highest_price_since_entry"] = max(previous_highest, current_price)
    normalized.setdefault("entry_time", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    normalized.setdefault("partial_exit_progress", 0)
    return normalized


def _apply_partial_exit_fill(open_trade: dict, partial_qty: float) -> dict | None:
    updated = dict(open_trade)
    remaining_qty = float(updated["entry_qty"]) - float(partial_qty)
    updated["entry_qty"] = max(remaining_qty, 0.0)
    updated["partial_exit_progress"] = int(updated.get("partial_exit_progress", 0) or 0) + 1

    if updated["entry_qty"] <= 0:
        return None

    return updated


def _reconcile_open_trade(
    *,
    symbol: str,
    symbol_info: dict,
    open_trade: dict,
) -> tuple[str, dict | None]:
    normalized_open_trade = _normalize_open_trade(open_trade)
    if normalized_open_trade is None:
        return "INVALID_OPEN_TRADE_CLEARED", None

    entry_order_id = int(normalized_open_trade["entry_order_id"])
    try:
        entry_order = get_order(symbol, entry_order_id, BINANCE_BASE_URL)
    except HTTPError as error:
        if _is_missing_order_error(error):
            return "STALE_OPEN_TRADE_CLEARED", None
        return "OPEN_TRADE_RECONCILE_ERROR_KEEP", normalized_open_trade
    except Exception:
        return "OPEN_TRADE_RECONCILE_ERROR_KEEP", normalized_open_trade

    order_status = str(entry_order.get("status", "")).upper()
    order_side = str(entry_order.get("side", "")).upper()
    executed_qty = float(entry_order.get("executedQty", 0) or 0)

    if order_status != "FILLED" or order_side != "BUY" or executed_qty <= 0:
        return "STALE_OPEN_TRADE_CLEARED", None

    account_info = get_account_info()
    base_asset = str(symbol_info.get("baseAsset", ""))
    asset_balance = extract_asset_balance(account_info, base_asset)
    held_qty = float(asset_balance.get("total", 0.0))
    entry_qty = float(normalized_open_trade["entry_qty"])

    if held_qty <= 0 or held_qty + 1e-12 < entry_qty:
        return "STALE_OPEN_TRADE_CLEARED", None

    confirmed_open_trade = _build_open_trade_from_order(entry_order, normalized_open_trade)
    return "OPEN_TRADE_CONFIRMED", confirmed_open_trade


def _reconcile_pending_order(
    *,
    symbol: str,
    pending: dict,
    open_trade: dict | None,
) -> tuple[str, dict | None, dict | None, dict | None]:
    normalized_pending = _normalize_pending_order(pending)
    if normalized_pending is None:
        return "STALE_PENDING_ORDER_CLEARED", None, None, None

    order_id = int(normalized_pending["orderId"])

    try:
        order_info = get_order(symbol, order_id, BINANCE_BASE_URL)
        status = str(order_info.get("status", "")).upper()

        if status == "FILLED":
            if normalized_pending.get("side") == "BUY":
                open_trade = _build_open_trade_from_order(order_info, normalized_pending)
                return "PROMOTE_TO_OPEN_TRADE", None, open_trade, None
            if normalized_pending.get("exit_type") == "PARTIAL" and isinstance(open_trade, dict):
                updated_open_trade = _apply_partial_exit_fill(
                    open_trade,
                    float(normalized_pending.get("partial_qty", 0.0) or 0.0),
                )
                if updated_open_trade is None:
                    return "SELL_FILLED", None, None, order_info
                return "PARTIAL_EXIT_FILLED", None, updated_open_trade, order_info
            if normalized_pending.get("exit_type") == "TRAILING_STOP":
                return "TRAILING_STOP_FILLED", None, None, order_info
            if normalized_pending.get("exit_type") == "STOP":
                return "STOP_MARKET_FILLED", None, None, order_info
            return "SELL_FILLED", None, None, order_info

        if status in {"NEW", "PARTIALLY_FILLED", "PENDING_NEW"}:
            normalized_pending["status"] = status
            return "PENDING_CONFIRMED", normalized_pending, None, None

        return "PENDING_CLEARED", None, None, None

    except HTTPError as error:
        if _is_missing_order_error(error):
            open_orders = get_open_orders(symbol)
            matched_order = _find_open_order_by_id(open_orders, order_id)

            if matched_order:
                normalized_pending["status"] = str(
                    matched_order.get("status", normalized_pending.get("status"))
                ).upper()
                return "PENDING_CONFIRMED_FROM_OPEN_ORDERS", normalized_pending, None, None

            return "STALE_PENDING_ORDER_CLEARED", None, None, None

        return "PENDING_RECONCILE_ERROR_KEEP", normalized_pending, None, None
    except Exception:
        return "PENDING_RECONCILE_ERROR_KEEP", normalized_pending, None, None


def _validate_limit_order_before_live(payload: dict) -> None:
    if not ENABLE_TEST_ORDER_VALIDATION:
        return

    send_test_order(payload)


def start_engine() -> None:
    project_root = Path(__file__).resolve().parent.parent
    log_file = project_root / LOG_FILE
    state_file = project_root / STATE_FILE
    portfolio_state_file = project_root / PORTFOLIO_STATE_FILE
    portfolio_log_file = project_root / PORTFOLIO_LOG_FILE
    strategy_metrics_file = project_root / STRATEGY_METRICS_FILE

    print("engine strategy v1 started")

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    state: dict = {}
    price = 0.0
    pending = None
    open_trade = None
    risk_metrics = _default_risk_metrics()
    cash_balance = 0.0

    try:
        state = _load_state(state_file)
        risk_metrics = _reset_daily_loss_count_if_needed(state.get("risk_metrics"), timestamp)
        portfolio_state = load_portfolio_state(portfolio_state_file)
        strategy_metrics = load_strategy_metrics(strategy_metrics_file)

        ping()
        get_server_time()
        symbol_info = get_symbol_info(SYMBOL)
        filters = extract_symbol_filters(symbol_info)
        price = get_price(SYMBOL)

        if not has_api_credentials():
            _save_and_finish(
                state_file=state_file,
                log_file=log_file,
                state=state,
                timestamp=timestamp,
                action="CREDENTIALS_MISSING",
                price=price,
                pending=None,
                open_trade=None,
                reason="missing_api_credentials",
                risk_metrics=risk_metrics,
                portfolio_state_file=portfolio_state_file,
                cash_balance=cash_balance,
            )
            return

        pending = state.get("pending_order")
        open_trade = state.get("open_trade")

        if pending:
            action, pending_after, open_trade_after, pending_fill_order = _reconcile_pending_order(
                symbol=SYMBOL,
                pending=pending,
                open_trade=open_trade,
            )

            if action == "PROMOTE_TO_OPEN_TRADE":
                _save_and_finish(
                    state_file=state_file,
                    log_file=log_file,
                    state=state,
                    timestamp=timestamp,
                    action=action,
                    price=price,
                    pending=None,
                    open_trade=open_trade_after,
                    reason="pending_buy_filled_promoted_to_open_trade",
                    risk_metrics=risk_metrics,
                    portfolio_state_file=portfolio_state_file,
                    cash_balance=cash_balance,
                    strategy_name_override=str((open_trade_after or {}).get("strategy_name") or ACTIVE_STRATEGY),
                )
                return

            if action == "PARTIAL_EXIT_FILLED":
                _save_and_finish(
                    state_file=state_file,
                    log_file=log_file,
                    state=state,
                    timestamp=timestamp,
                    action=action,
                    price=price,
                    pending=None,
                    open_trade=open_trade_after,
                    reason="partial_exit_filled",
                    risk_metrics=risk_metrics,
                    portfolio_state_file=portfolio_state_file,
                    cash_balance=cash_balance,
                    strategy_name_override=str((open_trade_after or {}).get("strategy_name") or ACTIVE_STRATEGY),
                )
                return

            if action in {"SELL_FILLED", "STOP_MARKET_FILLED", "TRAILING_STOP_FILLED"}:
                fill_price = _extract_fill_price(pending_fill_order or {}) or price
                strategy_name = str((open_trade or {}).get("strategy_name") or ACTIVE_STRATEGY)
                close_pnl_estimate = _estimate_close_pnl(open_trade, fill_price)
                record_closed_trade(strategy_metrics, strategy_name, close_pnl_estimate)
                save_strategy_metrics(strategy_metrics_file, strategy_metrics)
                append_portfolio_log(
                    portfolio_log_file,
                    (
                        f"symbol={SYMBOL} selected_strategy={strategy_name} close_action={action} "
                        f"close_pnl_estimate={close_pnl_estimate} "
                        f"{_trade_observability_fields(open_trade)} "
                        f"strategy_expectancy_snapshot={build_expectancy_snapshot(strategy_metrics, strategy_name)}"
                    ),
                )
                risk_metrics = _update_risk_metrics_for_close(
                    action=action,
                    open_trade=open_trade,
                    fill_price=fill_price,
                    risk_metrics=risk_metrics,
                    timestamp=timestamp,
                )
                _save_and_finish(
                    state_file=state_file,
                    log_file=log_file,
                    state=state,
                    timestamp=timestamp,
                    action=action,
                    price=price,
                    pending=None,
                    open_trade=None,
                    reason=action.lower(),
                    risk_metrics=risk_metrics,
                    portfolio_state_file=portfolio_state_file,
                    cash_balance=cash_balance,
                    strategy_name_override=strategy_name,
                )
                return

            if (
                open_trade
                and pending_after
                and _is_pending_limit_exit(pending_after)
            ):
                monitored_open_trade = _update_open_trade_runtime_fields(open_trade, price)
                protective_exit_signal = evaluate_exit(monitored_open_trade, price, state, filters)

                if protective_exit_signal.should_exit and protective_exit_signal.exit_type in {"STOP", "TRAILING_STOP"}:
                    cancel_ok, cancel_reason = _cancel_pending_exit_order(SYMBOL, pending_after)
                    if not cancel_ok:
                        _save_and_finish(
                            state_file=state_file,
                            log_file=log_file,
                            state=state,
                            timestamp=timestamp,
                            action="PROTECTIVE_EXIT_CANCEL_FAILED",
                            price=price,
                            pending=pending_after,
                            open_trade=monitored_open_trade,
                            reason=cancel_reason,
                            risk_metrics=risk_metrics,
                            portfolio_state_file=portfolio_state_file,
                            cash_balance=cash_balance,
                            strategy_name_override=str((monitored_open_trade or {}).get("strategy_name") or ACTIVE_STRATEGY),
                        )
                        return

                    (
                        protective_action,
                        protective_pending,
                        protective_open_trade,
                        protective_reason,
                        risk_metrics,
                    ) = _execute_protective_exit(
                        symbol=SYMBOL,
                        price=price,
                        timestamp=timestamp,
                        open_trade=monitored_open_trade,
                        exit_signal=protective_exit_signal,
                        filters=filters,
                        risk_metrics=risk_metrics,
                        strategy_metrics=strategy_metrics,
                        strategy_metrics_file=strategy_metrics_file,
                        portfolio_log_file=portfolio_log_file,
                    )
                    _save_and_finish(
                        state_file=state_file,
                        log_file=log_file,
                        state=state,
                        timestamp=timestamp,
                        action=protective_action,
                        price=price,
                        pending=protective_pending,
                        open_trade=protective_open_trade,
                        reason=f"{cancel_reason}|{protective_reason}",
                        risk_metrics=risk_metrics,
                        portfolio_state_file=portfolio_state_file,
                        cash_balance=cash_balance,
                        strategy_name_override=str((monitored_open_trade or {}).get("strategy_name") or ACTIVE_STRATEGY),
                    )
                    return

            _save_and_finish(
                state_file=state_file,
                log_file=log_file,
                state=state,
                timestamp=timestamp,
                action=action,
                price=price,
                pending=pending_after,
                open_trade=open_trade,
                reason=action.lower(),
                risk_metrics=risk_metrics,
                portfolio_state_file=portfolio_state_file,
                cash_balance=cash_balance,
                strategy_name_override=str((open_trade or {}).get("strategy_name") or (pending_after or {}).get("strategy_name") or ACTIVE_STRATEGY),
            )
            return

        if open_trade:
            open_trade_action, open_trade_after = _reconcile_open_trade(
                symbol=SYMBOL,
                symbol_info=symbol_info,
                open_trade=open_trade,
            )

            if open_trade_action != "OPEN_TRADE_CONFIRMED":
                _save_and_finish(
                    state_file=state_file,
                    log_file=log_file,
                    state=state,
                    timestamp=timestamp,
                    action=open_trade_action,
                    price=price,
                    pending=None,
                    open_trade=open_trade_after,
                    reason=(
                        "invalid_or_stale_open_trade_state"
                        if open_trade_action == "INVALID_OPEN_TRADE_CLEARED"
                        else open_trade_action.lower()
                    ),
                    risk_metrics=risk_metrics,
                    portfolio_state_file=portfolio_state_file,
                    cash_balance=cash_balance,
                )
                return

            open_trade = open_trade_after
            open_trade = _update_open_trade_runtime_fields(open_trade, price)
            exit_signal = evaluate_exit(open_trade, price, state, filters)

            if not exit_signal.should_exit:
                _save_and_finish(
                    state_file=state_file,
                    log_file=log_file,
                    state=state,
                    timestamp=timestamp,
                    action="HOLD_OPEN_TRADE",
                    price=price,
                    pending=None,
                    open_trade=open_trade,
                    reason=exit_signal.reason,
                    risk_metrics=risk_metrics,
                    portfolio_state_file=portfolio_state_file,
                    cash_balance=cash_balance,
                )
                return

            entry_qty = float(open_trade["entry_qty"])
            if exit_signal.exit_type in {"TARGET", "PARTIAL", "TIME_EXIT"}:
                exit_qty = entry_qty if exit_signal.exit_type != "PARTIAL" else float(exit_signal.partial_qty or 0.0)
                exit_limit_price = _select_exit_limit_price(exit_signal, price)
                adjusted_exit = auto_adjust_order_inputs(exit_limit_price, exit_qty, filters)
                adjusted_exit_qty = min(entry_qty, float(adjusted_exit["adjusted_qty"]))

                exit_validation = validate_order(
                    float(adjusted_exit["adjusted_price"]),
                    adjusted_exit_qty,
                    filters,
                )

                if not exit_validation.get("all_valid", False):
                    _save_and_finish(
                        state_file=state_file,
                        log_file=log_file,
                        state=state,
                        timestamp=timestamp,
                        action="SELL_REJECTED_BY_VALIDATION",
                        price=price,
                        pending=None,
                        open_trade=open_trade,
                        reason="sell_limit_validation_failed",
                        risk_metrics=risk_metrics,
                        portfolio_state_file=portfolio_state_file,
                        cash_balance=cash_balance,
                    )
                    return

                payload = build_limit_order_payload(
                    symbol=SYMBOL,
                    side="SELL",
                    price=float(adjusted_exit["adjusted_price"]),
                    quantity=adjusted_exit_qty,
                )

                _validate_limit_order_before_live(payload)
                order_response = send_live_testnet_order(payload)
                order_status = str(order_response.get("status", "")).upper()

                if order_status == "FILLED":
                    if exit_signal.exit_type == "PARTIAL":
                        updated_open_trade = _apply_partial_exit_fill(open_trade, adjusted_exit_qty)
                        _save_and_finish(
                            state_file=state_file,
                            log_file=log_file,
                            state=state,
                            timestamp=timestamp,
                            action="PARTIAL_EXIT_FILLED",
                            price=price,
                            pending=None,
                            open_trade=updated_open_trade,
                            reason="partial_exit_limit_filled",
                            risk_metrics=risk_metrics,
                            portfolio_state_file=portfolio_state_file,
                            cash_balance=cash_balance,
                        )
                        return

                    fill_price = _extract_fill_price(order_response) or price
                    strategy_name = str((open_trade or {}).get("strategy_name") or ACTIVE_STRATEGY)
                    close_pnl_estimate = _estimate_close_pnl(open_trade, fill_price)
                    record_closed_trade(strategy_metrics, strategy_name, close_pnl_estimate)
                    save_strategy_metrics(strategy_metrics_file, strategy_metrics)
                    append_portfolio_log(
                        portfolio_log_file,
                        (
                            f"symbol={SYMBOL} selected_strategy={strategy_name} close_action=SELL_FILLED "
                            f"close_pnl_estimate={close_pnl_estimate} "
                            f"{_trade_observability_fields(open_trade)} "
                            f"strategy_expectancy_snapshot={build_expectancy_snapshot(strategy_metrics, strategy_name)}"
                        ),
                    )
                    risk_metrics = _update_risk_metrics_for_close(
                        action="SELL_FILLED",
                        open_trade=open_trade,
                        fill_price=fill_price,
                        risk_metrics=risk_metrics,
                        timestamp=timestamp,
                    )
                    _save_and_finish(
                        state_file=state_file,
                        log_file=log_file,
                        state=state,
                        timestamp=timestamp,
                        action="SELL_FILLED",
                        price=price,
                        pending=None,
                        open_trade=None,
                        reason="target_exit_limit_filled",
                        risk_metrics=risk_metrics,
                        portfolio_state_file=portfolio_state_file,
                        cash_balance=cash_balance,
                        strategy_name_override=strategy_name,
                    )
                    return

                pending = _build_pending_order_from_response(
                    order_response,
                    "SELL",
                    exit_type=exit_signal.exit_type,
                    partial_qty=adjusted_exit_qty if exit_signal.exit_type == "PARTIAL" else None,
                )

                _save_and_finish(
                    state_file=state_file,
                    log_file=log_file,
                    state=state,
                    timestamp=timestamp,
                    action="PARTIAL_EXIT_SUBMITTED" if exit_signal.exit_type == "PARTIAL" else "SELL_SUBMITTED",
                    price=price,
                    pending=pending,
                    open_trade=open_trade,
                    reason=(
                        "partial_exit_limit_submitted"
                        if exit_signal.exit_type == "PARTIAL"
                        else (
                            "time_exit_limit_submitted"
                            if exit_signal.exit_type == "TIME_EXIT"
                            else "target_exit_limit_submitted"
                        )
                    ),
                    risk_metrics=risk_metrics,
                    portfolio_state_file=portfolio_state_file,
                    cash_balance=cash_balance,
                    strategy_name_override=str((open_trade or {}).get("strategy_name") or ACTIVE_STRATEGY),
                )
                return

            if exit_signal.exit_type in {"STOP", "TRAILING_STOP"}:
                action, pending, open_trade_after, reason, risk_metrics = _execute_protective_exit(
                    symbol=SYMBOL,
                    price=price,
                    timestamp=timestamp,
                    open_trade=open_trade,
                    exit_signal=exit_signal,
                    filters=filters,
                    risk_metrics=risk_metrics,
                    strategy_metrics=strategy_metrics,
                    strategy_metrics_file=strategy_metrics_file,
                    portfolio_log_file=portfolio_log_file,
                )
                _save_and_finish(
                    state_file=state_file,
                    log_file=log_file,
                    state=state,
                    timestamp=timestamp,
                    action=action,
                    price=price,
                    pending=pending,
                    open_trade=open_trade_after,
                    reason=reason,
                    risk_metrics=risk_metrics,
                    portfolio_state_file=portfolio_state_file,
                    cash_balance=cash_balance,
                    strategy_name_override=str((open_trade or {}).get("strategy_name") or ACTIVE_STRATEGY),
                )
                return

        ranked_selection = get_ranked_signal_selection(SYMBOL, strategy_metrics=strategy_metrics)
        save_strategy_metrics(strategy_metrics_file, strategy_metrics)
        _run_breakout_v2_shadow(
            project_root=state_file.parent.parent,
            symbol=SYMBOL,
        )
        _run_breakout_v3_shadow(
            project_root=state_file.parent.parent,
            symbol=SYMBOL,
        )
        signal = ranked_selection.selected_signal
        if signal is None:
            append_portfolio_log(
                portfolio_log_file,
                (
                    f"symbol={SYMBOL} selected_strategy=NONE reason=no_ranked_signal "
                    f"rank_score=0.0 rank_score_components={{}} blocked_by_policy=no_ranked_signal "
                    f"blocked_detail={ranked_selection.no_ranked_signal_detail} "
                    f"total_signals={ranked_selection.total_signals} candidate_count={ranked_selection.candidate_count} "
                    f"rejected_reasons={ranked_selection.rejected_reasons}"
                ),
            )
            _save_and_finish(
                state_file=state_file,
                log_file=log_file,
                state=state,
                timestamp=timestamp,
                action="NO_ENTRY_SIGNAL",
                price=price,
                pending=None,
                open_trade=None,
                reason="no_ranked_signal",
                risk_metrics=risk_metrics,
                portfolio_state_file=portfolio_state_file,
                cash_balance=cash_balance,
            )
            return

        increment_signals_selected(strategy_metrics, signal.strategy_name)
        save_strategy_metrics(strategy_metrics_file, strategy_metrics)
        append_portfolio_log(
            portfolio_log_file,
            (
                f"symbol={SYMBOL} selected_strategy={signal.strategy_name} confidence={signal.confidence} "
                f"selection_reason=highest_score total_signals={ranked_selection.total_signals} "
                f"candidate_count={ranked_selection.candidate_count} rejected_reasons={ranked_selection.rejected_reasons} "
                f"reason={signal.reason} rank_score={ranked_selection.rank_score} "
                f"{_signal_observability_fields(signal)} "
                f"rank_score_components={ranked_selection.rank_score_components} "
                f"strategy_expectancy_snapshot={ranked_selection.strategy_expectancy_snapshot} "
                f"rank_candidates={ranked_selection.candidate_details}"
            ),
        )
        entry_action, entry_reason = evaluate_entry_gate_from_signal(signal)

        if entry_action != "ENTRY_ALLOWED":
            append_portfolio_log(
                portfolio_log_file,
                (
                    f"symbol={SYMBOL} selected_strategy={signal.strategy_name} blocked_by_policy=entry_gate "
                    f"blocked_detail={entry_reason} total_signals={ranked_selection.total_signals} "
                    f"{_signal_observability_fields(signal)} "
                    f"candidate_count={ranked_selection.candidate_count} rejected_reasons={ranked_selection.rejected_reasons}"
                ),
            )
            _save_and_finish(
                state_file=state_file,
                log_file=log_file,
                state=state,
                timestamp=timestamp,
                action=entry_action,
                price=price,
                pending=None,
                open_trade=None,
                reason=entry_reason,
                risk_metrics=risk_metrics,
                portfolio_state_file=portfolio_state_file,
                cash_balance=cash_balance,
            )
            return

        if signal.exit_model is None:
            _save_and_finish(
                state_file=state_file,
                log_file=log_file,
                state=state,
                timestamp=timestamp,
                action="BUY_REJECTED_MISSING_EXIT_MODEL",
                price=price,
                pending=None,
                open_trade=None,
                reason="missing_exit_model",
                risk_metrics=risk_metrics,
                portfolio_state_file=portfolio_state_file,
                cash_balance=cash_balance,
            )
            return

        quote_asset = str(symbol_info.get("quoteAsset", ""))
        account_info = get_account_info()
        quote_balance = extract_asset_balance(account_info, quote_asset)
        cash_balance = float(quote_balance.get("total", 0.0))
        decision = decide_execution(
            signal=signal,
            state=state,
            balance=quote_balance,
            filters=filters,
            requested_qty=MIN_TRADE_QTY,
            portfolio_state=portfolio_state,
        )

        if not decision.execute:
            append_portfolio_log(
                portfolio_log_file,
                (
                    f"symbol={SYMBOL} selected_strategy={signal.strategy_name} blocked_by_policy={decision.reason} "
                    f"requested_notional={decision.notional_value} rank_score={ranked_selection.rank_score} "
                    f"{_signal_observability_fields(signal)} "
                    f"rank_score_components={ranked_selection.rank_score_components}"
                ),
            )
            _save_and_finish(
                state_file=state_file,
                log_file=log_file,
                state=state,
                timestamp=timestamp,
                action=decision.action,
                price=price,
                pending=None,
                open_trade=None,
                reason=decision.reason,
                risk_metrics=risk_metrics,
                portfolio_state_file=portfolio_state_file,
                cash_balance=cash_balance,
            )
            return

        adj = auto_adjust_order_inputs(
            float(decision.validated_price or price),
            float(decision.validated_qty or MIN_TRADE_QTY),
            filters,
        )
        final_validation = adj.get("final_validation", {})

        if not final_validation.get("all_valid", False):
            _save_and_finish(
                state_file=state_file,
                log_file=log_file,
                state=state,
                timestamp=timestamp,
                action="BUY_REJECTED_BY_VALIDATION",
                price=price,
                pending=None,
                open_trade=None,
                reason="buy_limit_validation_failed",
                risk_metrics=risk_metrics,
                portfolio_state_file=portfolio_state_file,
                cash_balance=cash_balance,
            )
            return

        payload = build_limit_order_payload(
            symbol=SYMBOL,
            side="BUY",
            price=adj["adjusted_price"],
            quantity=adj["adjusted_qty"],
        )

        _validate_limit_order_before_live(payload)
        order_response = send_live_testnet_order(payload)
        order_status = str(order_response.get("status", "")).upper()

        if order_status == "FILLED":
            exit_extensions = _build_exit_extension_fields(signal.exit_model, _extract_fill_price(order_response))
            open_trade = {
                "status": "OPEN",
                "entry_price": _extract_fill_price(order_response),
                "entry_qty": float(order_response["executedQty"]),
                "entry_order_id": int(order_response["orderId"]),
                "entry_side": "BUY",
                "strategy_name": signal.strategy_name,
                "decision_id": signal.decision_id,
                "market_features": signal.market_features,
                "stop_price": signal.exit_model.stop_price,
                "target_price": signal.exit_model.target_price,
                **exit_extensions,
            }
            pending = None
            action = "BUY_FILLED"
        else:
            exit_extensions = _build_exit_extension_fields(signal.exit_model, float(adj["adjusted_price"]))
            pending = _build_pending_order_from_response(
                order_response,
                "BUY",
                strategy_name=signal.strategy_name,
                stop_price=signal.exit_model.stop_price,
                target_price=signal.exit_model.target_price,
                trailing_stop_pct=exit_extensions["trailing_stop_pct"],
                partial_exit_levels=exit_extensions["partial_exit_levels"],
                time_based_exit_minutes=exit_extensions["time_based_exit_minutes"],
                decision_id=signal.decision_id,
                market_features=signal.market_features,
            )
            open_trade = None
            action = "BUY_SUBMITTED"

        _save_and_finish(
            state_file=state_file,
            log_file=log_file,
            state=state,
            timestamp=timestamp,
            action=action,
            price=price,
            pending=pending,
            open_trade=open_trade,
            reason=action.lower(),
            risk_metrics=risk_metrics,
            portfolio_state_file=portfolio_state_file,
            cash_balance=cash_balance,
            strategy_name_override=signal.strategy_name,
        )

    except Exception as error:
        try:
            _save_and_finish(
                state_file=state_file,
                log_file=log_file,
                state=state,
                timestamp=timestamp,
                action="ERROR",
                price=price,
                pending=pending,
                open_trade=open_trade,
                reason=str(error),
                risk_metrics=risk_metrics,
                portfolio_state_file=portfolio_state_file,
                cash_balance=cash_balance,
            )
        except Exception:
            pass
        print(f"ERROR: {error}")
