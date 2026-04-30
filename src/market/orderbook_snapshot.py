from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import requests

from config import (
    BINANCE_BASE_URL,
    ORDERBOOK_DEPTH_LIMIT,
    ORDERBOOK_MAX_SPREAD_PCT,
    ORDERBOOK_SNAPSHOT_FILE,
    ORDERBOOK_TOP_LEVELS,
    REQUEST_TIMEOUT,
)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _depth_notional(levels: list, top_levels: int) -> float:
    total = 0.0
    for item in levels[:top_levels]:
        if not isinstance(item, list) or len(item) < 2:
            continue
        price = _safe_float(item[0])
        qty = _safe_float(item[1])
        total += price * qty
    return total


def build_unusable_orderbook_snapshot(symbol: str, reason: str) -> dict:
    return {
        "schema_version": "1.0",
        "symbol": symbol,
        "source": "binance_spot_testnet_depth",
        "timestamp_ms": int(time.time() * 1000),
        "best_bid": None,
        "best_ask": None,
        "spread": None,
        "spread_pct": None,
        "bid_depth_notional": None,
        "ask_depth_notional": None,
        "imbalance": None,
        "depth_limit": ORDERBOOK_DEPTH_LIMIT,
        "top_levels": ORDERBOOK_TOP_LEVELS,
        "freshness_ms": 0,
        "usable": False,
        "reason": reason,
    }


def parse_depth_snapshot(
    symbol: str,
    raw_depth: dict,
    *,
    depth_limit: int = ORDERBOOK_DEPTH_LIMIT,
    top_levels: int = ORDERBOOK_TOP_LEVELS,
    max_spread_pct: float = ORDERBOOK_MAX_SPREAD_PCT,
) -> dict:
    bids = raw_depth.get("bids") if isinstance(raw_depth, dict) else None
    asks = raw_depth.get("asks") if isinstance(raw_depth, dict) else None

    if not isinstance(bids, list) or not isinstance(asks, list) or not bids or not asks:
        return build_unusable_orderbook_snapshot(symbol, "empty_depth")

    best_bid = _safe_float(bids[0][0] if isinstance(bids[0], list) and bids[0] else None)
    best_ask = _safe_float(asks[0][0] if isinstance(asks[0], list) and asks[0] else None)

    if best_bid <= 0 or best_ask <= 0 or best_ask < best_bid:
        return build_unusable_orderbook_snapshot(symbol, "invalid_best_levels")

    spread = best_ask - best_bid
    midpoint = (best_ask + best_bid) / 2.0
    spread_pct = spread / midpoint if midpoint > 0 else None
    bid_depth_notional = _depth_notional(bids, top_levels)
    ask_depth_notional = _depth_notional(asks, top_levels)
    imbalance = bid_depth_notional / ask_depth_notional if ask_depth_notional > 0 else None
    usable = (
        spread_pct is not None
        and spread_pct <= max_spread_pct
        and bid_depth_notional > 0
        and ask_depth_notional > 0
        and imbalance is not None
    )

    return {
        "schema_version": "1.0",
        "symbol": symbol,
        "source": "binance_spot_testnet_depth",
        "timestamp_ms": int(time.time() * 1000),
        "best_bid": best_bid,
        "best_ask": best_ask,
        "spread": spread,
        "spread_pct": spread_pct,
        "bid_depth_notional": bid_depth_notional,
        "ask_depth_notional": ask_depth_notional,
        "imbalance": imbalance,
        "depth_limit": depth_limit,
        "top_levels": top_levels,
        "freshness_ms": 0,
        "usable": usable,
        "reason": "ok" if usable else "spread_or_depth_not_usable",
    }


def fetch_orderbook_snapshot(symbol: str) -> dict:
    if not symbol:
        raise ValueError("symbol is required")

    started_ms = int(time.time() * 1000)
    response = requests.get(
        f"{BINANCE_BASE_URL}/api/v3/depth",
        params={"symbol": symbol, "limit": ORDERBOOK_DEPTH_LIMIT},
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    snapshot = parse_depth_snapshot(symbol, response.json())
    snapshot["freshness_ms"] = max(0, int(time.time() * 1000) - started_ms)
    return snapshot


def save_orderbook_snapshot(snapshot: dict, path: str | Path = ORDERBOOK_SNAPSHOT_FILE) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def get_orderbook_snapshot_safely(symbol: str) -> dict:
    try:
        snapshot = fetch_orderbook_snapshot(symbol)
    except Exception as error:
        snapshot = build_unusable_orderbook_snapshot(symbol, f"fetch_error:{error.__class__.__name__}")

    save_orderbook_snapshot(snapshot)
    return snapshot
