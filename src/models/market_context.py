from __future__ import annotations

from dataclasses import dataclass


@dataclass
class MarketContext:
    symbol: str
    primary_interval: str
    entry_interval: str
    klines_primary: list[dict]
    klines_entry: list[dict]
    last_price: float
    funding_rate: float | None = None
    open_interest: float | None = None
    long_short_ratio: float | None = None
    orderbook_imbalance: float | None = None
    orderbook_snapshot: dict | None = None
