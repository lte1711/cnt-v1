from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from binance_client import extract_symbol_filters
from config import (
    BINANCE_BASE_URL,
    ENTRY_INTERVAL,
    KLINES_LIMIT,
    MIN_TRADE_QTY,
    ORDERBOOK_MAX_SPREAD_PCT,
    PRIMARY_INTERVAL,
    REQUEST_TIMEOUT,
    STRATEGY_PARAMS,
    SYMBOL_CANDIDATE_REPORT_FILE,
    SYMBOL_SCANNER_KLINE_LIMIT,
    SYMBOL_SCANNER_MAX_SYMBOLS,
    SYMBOL_SCANNER_MIN_PROFIT_FACTOR,
    SYMBOL_SCANNER_MIN_SAMPLE_TRADES,
    SYMBOL_SCANNER_MIN_WIN_RATE,
)
from src.market.orderbook_snapshot import fetch_orderbook_snapshot
from src.market_data import fetch_klines
from src.models.market_context import MarketContext
from src.order_validator import auto_adjust_order_inputs
from src.strategies.pullback_v1 import PullbackV1Strategy


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def fetch_exchange_info() -> dict:
    response = requests.get(f"{BINANCE_BASE_URL}/api/v3/exchangeInfo", timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict) or not isinstance(payload.get("symbols"), list):
        raise ValueError("invalid exchangeInfo response")
    return payload


def fetch_24h_tickers() -> dict[str, dict]:
    response = requests.get(f"{BINANCE_BASE_URL}/api/v3/ticker/24hr", timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, list):
        return {}
    return {str(item.get("symbol")): item for item in payload if isinstance(item, dict)}


def list_usdt_spot_symbols(exchange_info: dict, tickers: dict[str, dict]) -> list[dict]:
    candidates = []
    for item in exchange_info.get("symbols", []):
        if not isinstance(item, dict):
            continue
        symbol = str(item.get("symbol", ""))
        if item.get("quoteAsset") != "USDT":
            continue
        if item.get("status") != "TRADING":
            continue
        if item.get("isSpotTradingAllowed") is False:
            continue
        ticker = tickers.get(symbol, {})
        candidates.append(
            {
                "symbol": symbol,
                "symbol_info": item,
                "quote_volume": _safe_float(ticker.get("quoteVolume")),
                "last_price": _safe_float(ticker.get("lastPrice")),
            }
        )
    return sorted(candidates, key=lambda row: row["quote_volume"], reverse=True)


def _primary_window(primary_klines: list[dict], entry_close_time: int) -> list[dict]:
    eligible = [item for item in primary_klines if int(item.get("close_time", 0)) <= entry_close_time]
    return eligible[-KLINES_LIMIT:]


def _profit_factor(gross_profit: float, gross_loss: float) -> float:
    if gross_loss <= 0:
        return 999999.0 if gross_profit > 0 else 0.0
    return gross_profit / gross_loss


def replay_pullback_v1(symbol: str, entry_klines: list[dict], primary_klines: list[dict]) -> dict:
    strategy = PullbackV1Strategy(STRATEGY_PARAMS["pullback_v1"])
    strategy.validate_params(STRATEGY_PARAMS["pullback_v1"])

    trades = []
    signal_count = 0
    rejected_reasons: dict[str, int] = {}
    index = KLINES_LIMIT

    while index < len(entry_klines) - 1:
        entry_window = entry_klines[index - KLINES_LIMIT : index]
        primary_window = _primary_window(primary_klines, int(entry_klines[index - 1]["close_time"]))
        if len(entry_window) < KLINES_LIMIT or len(primary_window) < min(20, KLINES_LIMIT):
            index += 1
            continue

        last_price = float(entry_window[-1]["close"])
        context = MarketContext(
            symbol=symbol,
            primary_interval=PRIMARY_INTERVAL,
            entry_interval=ENTRY_INTERVAL,
            klines_primary=primary_window,
            klines_entry=entry_window,
            last_price=last_price,
        )
        signal = strategy.evaluate(context)
        signal_count += 1

        if not signal.entry_allowed or signal.exit_model is None:
            rejected_reasons[signal.reason] = rejected_reasons.get(signal.reason, 0) + 1
            index += 1
            continue

        entry_price = float(signal.entry_price_hint or last_price)
        stop_price = float(signal.exit_model.stop_price or 0)
        target_price = float(signal.exit_model.target_price or 0)
        close_index = None
        close_price = None
        close_reason = "unresolved"

        for exit_index in range(index + 1, len(entry_klines)):
            candle = entry_klines[exit_index]
            low = float(candle["low"])
            high = float(candle["high"])
            if low <= stop_price:
                close_index = exit_index
                close_price = stop_price
                close_reason = "stop"
                break
            if high >= target_price:
                close_index = exit_index
                close_price = target_price
                close_reason = "target"
                break

        if close_index is None or close_price is None:
            index += 1
            continue

        pnl_pct = (close_price - entry_price) / entry_price if entry_price > 0 else 0.0
        trades.append(
            {
                "entry_time": entry_klines[index - 1].get("close_time"),
                "close_time": entry_klines[close_index].get("close_time"),
                "entry_price": entry_price,
                "close_price": close_price,
                "close_reason": close_reason,
                "pnl_pct": pnl_pct,
                "signal_reason": signal.reason,
            }
        )
        index = close_index + 1

    wins = [trade for trade in trades if trade["pnl_pct"] > 0]
    losses = [trade for trade in trades if trade["pnl_pct"] <= 0]
    gross_profit = sum(trade["pnl_pct"] for trade in wins)
    gross_loss = abs(sum(trade["pnl_pct"] for trade in losses))
    total = len(trades)

    return {
        "signal_count": signal_count,
        "rejected_signal_count": sum(rejected_reasons.values()),
        "rejected_reasons": rejected_reasons,
        "trades_closed": total,
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": len(wins) / total if total else 0.0,
        "gross_profit_pct": gross_profit,
        "gross_loss_pct": gross_loss,
        "avg_win_pct": gross_profit / len(wins) if wins else 0.0,
        "avg_loss_pct": gross_loss / len(losses) if losses else 0.0,
        "expectancy_pct": (gross_profit - gross_loss) / total if total else 0.0,
        "profit_factor": _profit_factor(gross_profit, gross_loss),
        "sample_trades": trades[:5],
    }


def evaluate_filters(symbol_info: dict, last_price: float) -> dict:
    filters = extract_symbol_filters(symbol_info)
    stop_reference = last_price * (1 - float(STRATEGY_PARAMS["pullback_v1"]["stop_loss_pct"]))
    adjusted = auto_adjust_order_inputs(
        last_price,
        MIN_TRADE_QTY,
        filters,
        min_notional_reference_price=stop_reference,
    )
    final_validation = adjusted.get("final_validation", {})
    return {
        "filters_present": {
            "price_filter": bool(filters.get("price_filter")),
            "lot_size_filter": bool(filters.get("lot_size_filter")),
            "notional_filter": bool(filters.get("notional_filter")),
        },
        "requested_qty": MIN_TRADE_QTY,
        "validated_price": adjusted.get("adjusted_price"),
        "validated_qty": adjusted.get("adjusted_qty"),
        "notional_value": float(adjusted.get("adjusted_price", 0) or 0)
        * float(adjusted.get("adjusted_qty", 0) or 0),
        "all_valid": bool(final_validation.get("all_valid")),
        "validation": final_validation,
    }


def evaluate_symbol(candidate: dict) -> dict:
    symbol = candidate["symbol"]
    symbol_info = candidate["symbol_info"]
    try:
        entry_klines = fetch_klines(symbol, ENTRY_INTERVAL, SYMBOL_SCANNER_KLINE_LIMIT)
        primary_klines = fetch_klines(symbol, PRIMARY_INTERVAL, SYMBOL_SCANNER_KLINE_LIMIT)
        last_price = float(entry_klines[-1]["close"]) if entry_klines else float(candidate.get("last_price") or 0)
        replay = replay_pullback_v1(symbol, entry_klines, primary_klines)
        filter_result = evaluate_filters(symbol_info, last_price)
        try:
            orderbook = fetch_orderbook_snapshot(symbol)
        except Exception as error:
            orderbook = {"usable": False, "reason": f"fetch_error:{error.__class__.__name__}"}

        pass_rules = (
            replay["trades_closed"] >= SYMBOL_SCANNER_MIN_SAMPLE_TRADES
            and replay["win_rate"] > SYMBOL_SCANNER_MIN_WIN_RATE
            and replay["expectancy_pct"] > 0
            and replay["profit_factor"] > SYMBOL_SCANNER_MIN_PROFIT_FACTOR
            and filter_result["all_valid"]
            and bool(orderbook.get("usable"))
            and _safe_float(orderbook.get("spread_pct"), 1.0) <= ORDERBOOK_MAX_SPREAD_PCT
        )
        return {
            "symbol": symbol,
            "status": "OK",
            "quote_volume": candidate.get("quote_volume", 0.0),
            "last_price": last_price,
            "replay": replay,
            "filter_check": filter_result,
            "orderbook": orderbook,
            "promotion_candidate": pass_rules,
            "promotion_reason": "passes_thresholds" if pass_rules else "thresholds_not_met",
        }
    except Exception as error:
        return {
            "symbol": symbol,
            "status": "ERROR",
            "error": f"{error.__class__.__name__}: {error}",
            "promotion_candidate": False,
            "promotion_reason": "scan_error",
        }


def build_symbol_candidate_report(max_symbols: int = SYMBOL_SCANNER_MAX_SYMBOLS) -> dict:
    exchange_info = fetch_exchange_info()
    tickers = fetch_24h_tickers()
    all_usdt_candidates = list_usdt_spot_symbols(exchange_info, tickers)
    candidates = all_usdt_candidates[:max_symbols]
    results = [evaluate_symbol(candidate) for candidate in candidates]
    ranked = sorted(
        results,
        key=lambda item: (
            bool(item.get("promotion_candidate")),
            _safe_float(item.get("replay", {}).get("trades_closed")) >= SYMBOL_SCANNER_MIN_SAMPLE_TRADES,
            _safe_float(item.get("replay", {}).get("expectancy_pct")),
            _safe_float(item.get("replay", {}).get("profit_factor")),
            _safe_float(item.get("replay", {}).get("win_rate")),
        ),
        reverse=True,
    )
    return {
        "schema_version": "1.0",
        "generated_at_ms": int(time.time() * 1000),
        "mode": "READ_ONLY",
        "strategy": "pullback_v1",
        "source": "Binance Spot Testnet public API",
        "available_usdt_symbol_count": len(all_usdt_candidates),
        "candidate_count": len(candidates),
        "max_symbols": max_symbols,
        "thresholds": {
            "min_sample_trades": SYMBOL_SCANNER_MIN_SAMPLE_TRADES,
            "min_win_rate": SYMBOL_SCANNER_MIN_WIN_RATE,
            "min_profit_factor": SYMBOL_SCANNER_MIN_PROFIT_FACTOR,
            "expectancy_must_be_positive": True,
            "orderbook_max_spread_pct": ORDERBOOK_MAX_SPREAD_PCT,
        },
        "summary": {
            "promotion_candidate_count": sum(1 for item in results if item.get("promotion_candidate")),
            "sample_ready_count": sum(
                1
                for item in results
                if _safe_float(item.get("replay", {}).get("trades_closed")) >= SYMBOL_SCANNER_MIN_SAMPLE_TRADES
            ),
            "positive_expectancy_count": sum(
                1 for item in results if _safe_float(item.get("replay", {}).get("expectancy_pct")) > 0
            ),
            "filter_pass_count": sum(1 for item in results if item.get("filter_check", {}).get("all_valid")),
            "orderbook_usable_count": sum(1 for item in results if item.get("orderbook", {}).get("usable")),
        },
        "top_candidates": ranked[:10],
        "all_candidates": ranked,
        "decision": "review_required_before_symbol_change",
    }


def save_report(report: dict, output_path: str | Path = SYMBOL_CANDIDATE_REPORT_FILE) -> None:
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only CNT symbol candidate scanner")
    parser.add_argument("--max-symbols", type=int, default=SYMBOL_SCANNER_MAX_SYMBOLS)
    parser.add_argument("--output", default=SYMBOL_CANDIDATE_REPORT_FILE)
    args = parser.parse_args()

    report = build_symbol_candidate_report(max_symbols=args.max_symbols)
    save_report(report, args.output)
    print(json.dumps({"output": args.output, "candidate_count": report["candidate_count"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
