---
title: CNT Symbol Validation Reporting Implementation 20260430
created: 2026-04-30
project: CNT
status: IMPLEMENTED
mode: BINANCE_SPOT_TESTNET
---

# CNT Symbol Validation Reporting Implementation 20260430

## 1. Design Summary

The ALGOUSDT validation reporting layer was added as an analysis layer only.

The implementation does not change:

- runtime symbol,
- entry gate,
- risk guard,
- live gate,
- order validation,
- order submission,
- state machine flow.

The implementation adds:

- JSONL event schema for `logs/symbol_validation.log`,
- slippage calculation,
- reject and partial-fill flags,
- orderbook-at-entry payload support,
- realized performance aggregation,
- `data/symbol_validation_report.json`,
- dashboard validation panel.

## 2. Added Files

- `src/logging/symbol_validation_logger.py`
- `src/analytics/symbol_validation_report.py`
- `tools/generate_symbol_validation_report.py`
- `data/symbol_validation_report.json`
- `tests/test_symbol_validation_report.py`

## 3. Modified Files

- `config.py`
- `docs/cnt_operations_dashboard.html`

## 4. Log Schema

Target log:

```text
logs/symbol_validation.log
```

Format:

```text
JSONL
```

Each event can include:

- `signal_price`
- `validated_price`
- `validated_qty`
- `notional_value`
- `exchange.fill_price`
- `exchange.executed_qty`
- `slippage_pct`
- `order_reject_flag`
- `partial_fill_flag`
- `orderbook.spread_pct`
- `orderbook.imbalance`
- `orderbook.bid_depth_notional`
- `orderbook.ask_depth_notional`
- `close_pnl_estimate`

## 5. Report Metrics

The report generator calculates:

- order count,
- closed trades,
- wins,
- losses,
- win rate,
- gross profit,
- gross loss,
- net PnL,
- average win,
- average loss,
- realized expectancy,
- realized profit factor,
- max consecutive losses,
- order reject rate,
- partial fill rate,
- average and median slippage,
- orderbook usable rate,
- average spread,
- average imbalance.

## 6. Promotion Checks

The generated report exposes:

```text
closed_trades_ge_30
realized_pf_ge_1_3
realized_expectancy_positive
order_reject_rate_lt_2pct
max_consecutive_losses_lte_3
```

These are reporting checks only. They do not approve runtime symbol promotion.

## 7. Current Report State

VERIFIED:

```text
symbol_filter = ALGOUSDT
event_count = 0
order_count = 0
closed_trades = 0
decision = review_required_before_symbol_promotion
```

Interpretation:

- The reporting pipeline is ready.
- No ALGOUSDT execution-quality events have been collected yet.

## 8. Validation Result

VERIFIED:

```text
python -m pytest -q
77 passed
```

VERIFIED:

```text
python -m py_compile src\logging\symbol_validation_logger.py src\analytics\symbol_validation_report.py tools\generate_symbol_validation_report.py
PASS
```

VERIFIED:

```text
python -m json.tool data\symbol_validation_report.json
PASS
```

VERIFIED:

```text
docs/cnt_operations_dashboard.html script syntax
PASS
```

## 9. Record

2026-04-30: Symbol validation reporting was implemented for ALGOUSDT validation preparation. The system now has a read-only path from `logs/symbol_validation.log` to `data/symbol_validation_report.json` and the operations dashboard.
