from __future__ import annotations

import time
from pathlib import Path

from binance_client import get_price
from config import ACTIVE_STRATEGIES, ACTIVE_STRATEGY, ENTRY_INTERVAL, KLINES_LIMIT, PRIMARY_INTERVAL, SIGNAL_LOG_FILE, STRATEGY_PARAMS
from src.market.feature_snapshot import build_market_feature_snapshot
from src.market.orderbook_snapshot import get_orderbook_snapshot_safely
from src.market_data import get_recent_closed_klines
from src.models.market_context import MarketContext
from src.models.strategy_signal import StrategySignal
from src.signal_logger import append_signal_log
from src.strategy_registry import STRATEGY_REGISTRY


def _build_error_signal(symbol: str, strategy_name: str, message: str) -> StrategySignal:
    timestamp = time.time()
    return StrategySignal(
        strategy_name=strategy_name,
        symbol=symbol,
        signal_timestamp=timestamp,
        signal_age_limit_sec=-1,
        entry_allowed=False,
        side="NONE",
        trigger="ERROR",
        reason=f"strategy_error:{message}",
        confidence=0.0,
        market_state="UNKNOWN",
        volatility_state="UNKNOWN",
        entry_price_hint=None,
        exit_model=None,
        decision_id=f"{symbol}-{strategy_name}-{int(timestamp * 1000)}",
        market_features={},
    )


def _append_signal_log_safely(signal_log_file: Path, signal: StrategySignal) -> None:
    try:
        append_signal_log(signal_log_file, signal)
    except Exception:
        pass


def _ensure_decision_metadata(signal: StrategySignal, context: MarketContext, params: dict) -> StrategySignal:
    if not signal.decision_id:
        timestamp_ms = int(float(signal.signal_timestamp) * 1000)
        signal.decision_id = f"{signal.symbol}-{signal.strategy_name}-{timestamp_ms}"

    if not signal.market_features:
        signal.market_features = build_market_feature_snapshot(context, params)

    return signal


def _run_strategy(strategy_name: str, symbol: str, signal_log_file: Path) -> StrategySignal:
    try:
        strategy_class = STRATEGY_REGISTRY[strategy_name]
        params = dict(STRATEGY_PARAMS[strategy_name])
        strategy = strategy_class(params)
        strategy.validate_params(params)

        klines_primary = get_recent_closed_klines(
            symbol=symbol,
            interval=PRIMARY_INTERVAL,
            limit=KLINES_LIMIT,
        )
        klines_entry = get_recent_closed_klines(
            symbol=symbol,
            interval=ENTRY_INTERVAL,
            limit=KLINES_LIMIT,
        )
        last_price = get_price(symbol)
        orderbook_snapshot = get_orderbook_snapshot_safely(symbol)

        context = MarketContext(
            symbol=symbol,
            primary_interval=PRIMARY_INTERVAL,
            entry_interval=ENTRY_INTERVAL,
            klines_primary=klines_primary,
            klines_entry=klines_entry,
            last_price=last_price,
            orderbook_imbalance=orderbook_snapshot.get("imbalance"),
            orderbook_snapshot=orderbook_snapshot,
        )

        signal = _ensure_decision_metadata(strategy.evaluate(context), context, params)
        _append_signal_log_safely(signal_log_file, signal)
        return signal
    except Exception as error:
        signal = _build_error_signal(symbol, strategy_name, str(error))
        _append_signal_log_safely(signal_log_file, signal)
        return signal


def generate_strategy_signal(symbol: str) -> StrategySignal:
    project_root = Path(__file__).resolve().parent.parent
    signal_log_file = project_root / SIGNAL_LOG_FILE
    return _run_strategy(ACTIVE_STRATEGY, symbol, signal_log_file)


def generate_all_signals(symbol: str) -> list[StrategySignal]:
    project_root = Path(__file__).resolve().parent.parent
    signal_log_file = project_root / SIGNAL_LOG_FILE
    strategy_names = ACTIVE_STRATEGIES or [ACTIVE_STRATEGY]
    return [_run_strategy(strategy_name, symbol, signal_log_file) for strategy_name in strategy_names]
