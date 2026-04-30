from __future__ import annotations

from src.indicators import (
    atr,
    ema,
    extract_closes,
    extract_highs,
    extract_lows,
    extract_volumes,
    rsi,
    sma,
)
from src.models.market_context import MarketContext


def _safe_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _last_numeric(values: list[float | None]) -> float | None:
    for value in reversed(values):
        if value is not None:
            return float(value)
    return None


def _previous_numeric(values: list[float | None]) -> float | None:
    found_latest = False
    for value in reversed(values):
        if value is None:
            continue
        if not found_latest:
            found_latest = True
            continue
        return float(value)
    return None


def _ratio(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator is None or denominator == 0:
        return None
    return float(numerator) / float(denominator)


def _trend_label(ema_fast_value: float | None, ema_slow_value: float | None) -> str:
    if ema_fast_value is None or ema_slow_value is None:
        return "UNKNOWN"
    if ema_fast_value > ema_slow_value:
        return "UP"
    if ema_fast_value < ema_slow_value:
        return "DOWN"
    return "FLAT"


def _candle_features(kline: dict) -> dict:
    open_price = _safe_float(kline.get("open"))
    high = _safe_float(kline.get("high"))
    low = _safe_float(kline.get("low"))
    close = _safe_float(kline.get("close"))
    candle_range = max(high - low, 0.0)
    candle_body = abs(close - open_price)
    body_ratio = candle_body / candle_range if candle_range > 0 else 0.0
    range_pct = candle_range / close if close > 0 else 0.0
    return {
        "open": open_price,
        "high": high,
        "low": low,
        "close": close,
        "candle_body_ratio": body_ratio,
        "candle_range_pct": range_pct,
        "spread_proxy_pct": range_pct,
        "spread_proxy_source": "entry_candle_high_low",
    }


def _timeframe_features(klines: list[dict], params: dict) -> dict:
    if not klines:
        return {
            "trend_bias": "UNKNOWN",
            "rsi": None,
            "ema_fast": None,
            "ema_slow": None,
            "ema_slope_pct": None,
            "ema_gap_pct": None,
            "atr": None,
            "atr_pct": None,
            "volume": None,
            "volume_sma": None,
            "volume_ratio": None,
        }

    closes = extract_closes(klines)
    highs = extract_highs(klines)
    lows = extract_lows(klines)
    volumes = extract_volumes(klines) if all("volume" in item for item in klines) else []

    ema_fast_series = ema(closes, int(params.get("ema_fast_period", 9)))
    ema_slow_series = ema(closes, int(params.get("ema_slow_period", 20)))
    rsi_series = rsi(closes, int(params.get("rsi_period", 14)))
    atr_series = atr(highs, lows, closes, int(params.get("atr_period", 14)))
    volume_sma_series = sma(volumes, int(params.get("volume_avg_period", 20))) if volumes else []

    close = closes[-1]
    ema_fast_value = _last_numeric(ema_fast_series)
    ema_fast_previous = _previous_numeric(ema_fast_series)
    ema_slow_value = _last_numeric(ema_slow_series)
    atr_value = _last_numeric(atr_series)
    volume = volumes[-1] if volumes else None
    volume_sma = _last_numeric(volume_sma_series)

    return {
        "trend_bias": _trend_label(ema_fast_value, ema_slow_value),
        "rsi": _last_numeric(rsi_series),
        "ema_fast": ema_fast_value,
        "ema_slow": ema_slow_value,
        "ema_slope_pct": _ratio(
            None if ema_fast_value is None or ema_fast_previous is None else ema_fast_value - ema_fast_previous,
            ema_fast_previous,
        ),
        "ema_gap_pct": _ratio(
            None if ema_fast_value is None or ema_slow_value is None else ema_fast_value - ema_slow_value,
            close,
        ),
        "atr": atr_value,
        "atr_pct": _ratio(atr_value, close),
        "volume": volume,
        "volume_sma": volume_sma,
        "volume_ratio": _ratio(volume, volume_sma),
    }


def build_market_feature_snapshot(context: MarketContext, params: dict) -> dict:
    entry_features = _timeframe_features(context.klines_entry, params)
    primary_features = _timeframe_features(context.klines_primary, params)
    candle = _candle_features(context.klines_entry[-1]) if context.klines_entry else {}
    primary_trend = str(primary_features.get("trend_bias", "UNKNOWN"))
    entry_trend = str(entry_features.get("trend_bias", "UNKNOWN"))

    return {
        "schema_version": "1.0",
        "symbol": context.symbol,
        "primary_interval": context.primary_interval,
        "entry_interval": context.entry_interval,
        "last_price": context.last_price,
        "orderbook": context.orderbook_snapshot
        or {
            "usable": False,
            "reason": "not_collected",
            "imbalance": context.orderbook_imbalance,
        },
        "multi_timeframe_trend": f"PRIMARY_{primary_trend}_ENTRY_{entry_trend}",
        "primary": primary_features,
        "entry": {
            **entry_features,
            **candle,
        },
    }
