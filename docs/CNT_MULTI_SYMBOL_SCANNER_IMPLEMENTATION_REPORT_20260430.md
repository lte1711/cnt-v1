---
title: CNT Multi Symbol Scanner Implementation Report 20260430
created: 2026-04-30
project: CNT
status: IMPLEMENTED
mode: BINANCE_SPOT_TESTNET
---

# CNT Multi Symbol Scanner Implementation Report 20260430

## 1. Backup Record

VERIFIED:

```text
git stash push -u -m "멀티진행 이전"
```

The current worktree state before multi-symbol implementation was saved as a git stash entry named `멀티진행 이전`.

The stash was applied back to the working tree before implementation continued, so local work remained available.

## 2. Design Summary

A read-only multi-symbol scanner was added.

The scanner:

- reads Binance Spot Testnet public `exchangeInfo`,
- filters active `USDT` spot symbols,
- ranks scan candidates by 24h quote volume,
- fetches 1m and 5m klines,
- replays `pullback_v1` offline,
- evaluates win rate, expectancy, profit factor, average win, and average loss,
- validates symbol filters, minimum notional, lot size, and adjusted quantity,
- checks orderbook spread and depth usability,
- writes `data/symbol_candidate_report.json`.

The scanner does not:

- submit orders,
- change `config.SYMBOL`,
- change strategy parameters,
- change risk guard,
- change live gate,
- change entry gate,
- change state files used by live execution.

## 3. Added Files

- `tools/symbol_candidate_scanner.py`
- `data/symbol_candidate_report.json`
- `tests/test_symbol_candidate_scanner.py`

## 4. Modified Files

- `config.py`
- `docs/cnt_operations_dashboard.html`

## 5. Scan Result

VERIFIED:

```text
available_usdt_symbol_count = 439
candidate_count = 50
promotion_candidate_count = 2
sample_ready_count = 3
positive_expectancy_count = 11
filter_pass_count = 50
orderbook_usable_count = 37
```

The report is stored at:

```text
data/symbol_candidate_report.json
```

## 6. Promotion Candidate Review

### 6.1 ALGOUSDT

VERIFIED:

```text
symbol = ALGOUSDT
promotion_candidate = true
trades_closed = 39
win_rate = 0.5641
expectancy_pct = 0.000362
profit_factor = 1.5529
filter_check = true
orderbook_usable = true
spread_pct = 0.0009004952723998456
```

Assessment:

- ALGOUSDT is the strongest current candidate by the configured thresholds.
- It has enough sample trades under the scanner rule.
- It passes filter and orderbook checks.

### 6.2 CHZUSDT

VERIFIED:

```text
symbol = CHZUSDT
promotion_candidate = true
trades_closed = 32
win_rate = 0.5625
expectancy_pct = 0.000356
profit_factor = 1.5429
filter_check = true
orderbook_usable = true
spread_pct = 0.0002434570906876719
```

Assessment:

- CHZUSDT also passes the configured thresholds.
- It has lower spread than ALGOUSDT in the collected snapshot.
- Its sample count is lower than ALGOUSDT but still above the minimum scanner rule.

## 7. One Symbol Promotion Review

Decision:

```text
PRIMARY_REVIEW_CANDIDATE = ALGOUSDT
SECONDARY_REVIEW_CANDIDATE = CHZUSDT
CONFIG_SYMBOL_CHANGE = NOT_APPLIED
LIVE_OPERATION_CHANGE = NOT_APPLIED
```

Reason:

- ALGOUSDT has the larger replay sample among the two promoted candidates.
- CHZUSDT remains a valid backup candidate.
- The project is currently in risk pause and official gate fail state, so direct symbol switching is not applied.

## 8. Validation Result

VERIFIED:

```text
python -m pytest -q
74 passed
```

VERIFIED:

```text
python -m py_compile tools\symbol_candidate_scanner.py
PASS
```

VERIFIED:

```text
python -m json.tool data\symbol_candidate_report.json
PASS
```

VERIFIED:

```text
docs/cnt_operations_dashboard.html script syntax
PASS
```

## 9. Record

2026-04-30: A read-only multi-symbol scanner was implemented and executed against Binance Spot Testnet public data. The scanner reviewed 50 high-quote-volume USDT symbols from 439 available USDT spot symbols. ALGOUSDT and CHZUSDT passed the configured observation thresholds. No runtime symbol switch was applied.
