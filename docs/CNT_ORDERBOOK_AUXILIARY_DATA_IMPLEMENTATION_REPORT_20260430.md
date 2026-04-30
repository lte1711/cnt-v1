---
title: CNT Orderbook Auxiliary Data Implementation Report 20260430
created: 2026-04-30
project: CNT
status: IMPLEMENTED
mode: BINANCE_SPOT_TESTNET
---

# CNT Orderbook Auxiliary Data Implementation Report 20260430

## 1. Design Summary

Orderbook data was added as auxiliary market context only.

The implementation does not change:

- strategy parameters,
- entry permission logic,
- risk guard logic,
- portfolio guard logic,
- order validation,
- order submission,
- exit logic,
- state machine flow.

The implementation adds REST depth snapshot collection and exposes the result to:

- `data/orderbook_snapshot.json`,
- `MarketContext`,
- `market_features`,
- operations dashboard.

## 2. Runtime Boundary

FACT:

- The collector uses Binance Spot Testnet `/api/v3/depth`.
- The collector is fail-soft. Fetch failure writes an unusable snapshot instead of failing strategy generation.
- `pullback_v1` does not use orderbook data to approve entries.
- The dashboard displays orderbook status as auxiliary observation only.

## 3. Added Files

- `src/market/orderbook_snapshot.py`
- `data/orderbook_snapshot.json`
- `tests/test_orderbook_snapshot.py`

## 4. Modified Files

- `config.py`
- `src/models/market_context.py`
- `src/market/feature_snapshot.py`
- `src/strategy_manager.py`
- `docs/cnt_operations_dashboard.html`
- `tests/test_market_feature_snapshot.py`

## 5. Data Contract

Current snapshot fields:

```json
{
  "schema_version": "1.0",
  "symbol": "ETHUSDT",
  "source": "binance_spot_testnet_depth",
  "timestamp_ms": 0,
  "best_bid": null,
  "best_ask": null,
  "spread": null,
  "spread_pct": null,
  "bid_depth_notional": null,
  "ask_depth_notional": null,
  "imbalance": null,
  "depth_limit": 100,
  "top_levels": 20,
  "freshness_ms": 0,
  "usable": false,
  "reason": "not_collected"
}
```

## 6. Current Collection Result

VERIFIED:

- A live Binance Spot Testnet depth snapshot was collected for `ETHUSDT`.
- The snapshot was written to `data/orderbook_snapshot.json`.
- The observed snapshot was marked usable.

Observed values at collection time:

```text
usable=true
reason=ok
best_bid=2259.38
best_ask=2259.52
imbalance=0.5907594355234715
```

Interpretation:

- The orderbook was readable.
- The spread was within the configured auxiliary threshold.
- Ask-side depth was larger than bid-side depth in the configured top levels at the time of collection.

This is not an entry block and not an entry approval.

## 7. Validation Result

VERIFIED:

```text
python -m pytest -q
72 passed
```

VERIFIED:

```text
python -m py_compile src\market\orderbook_snapshot.py src\strategy_manager.py src\market\feature_snapshot.py src\models\market_context.py
PASS
```

VERIFIED:

```text
data/orderbook_snapshot.json
JSON parse PASS
```

VERIFIED:

```text
docs/cnt_operations_dashboard.html
script syntax PASS
```

## 8. Operational Use

The correct use is:

```text
observe orderbook
record into market_features
display on dashboard
compare later against signal outcomes
do not execute from orderbook alone
```

Promotion to a blocking filter requires a separate evidence review.

## 9. Record

2026-04-30: CNT orderbook auxiliary data collection was implemented. The feature is active as observation data only and does not alter execution behavior.
