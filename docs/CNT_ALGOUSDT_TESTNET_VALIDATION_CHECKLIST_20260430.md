---
title: CNT ALGOUSDT Testnet Validation Checklist 20260430
created: 2026-04-30
project: CNT
status: PLAN
mode: BINANCE_SPOT_TESTNET
---

# CNT ALGOUSDT Testnet Validation Checklist 20260430

## 1. Scope

This checklist defines the required validation before `ALGOUSDT` can be considered for runtime symbol promotion.

This document does not approve a symbol switch.

## 2. Current Evidence

FACT:

- `ALGOUSDT` passed the read-only scanner thresholds.
- Scanner sample trades: `39`.
- Scanner win rate: `56.41%`.
- Scanner expectancy pct: `0.000362`.
- Scanner profit factor: `1.5529`.
- Scanner filter check passed.
- Scanner orderbook check passed.

UNKNOWN:

- Real testnet fill quality.
- Actual slippage.
- Partial fill behavior.
- Runtime rejection rate.
- Stability under scheduled one-shot execution.

## 3. Validation Mode

Required validation:

```text
symbol = ALGOUSDT
mode = BINANCE_SPOT_TESTNET
duration = 24 to 72 hours minimum
position_model = single position only
order_policy = existing CNT policy
execution_change = requires explicit approval before config.SYMBOL change
```

## 4. Required Metrics

Record every candidate signal and every submitted order with:

- decision_id
- symbol
- strategy_name
- signal_timestamp
- signal_price
- order_side
- order_type
- requested_qty
- validated_qty
- validated_price
- notional_value
- orderbook_best_bid
- orderbook_best_ask
- orderbook_spread_pct
- orderbook_imbalance
- orderbook_bid_depth_notional
- orderbook_ask_depth_notional
- submit_time
- exchange_order_id
- exchange_status
- fill_price
- fill_qty
- fill_quote_qty
- slippage_pct
- reject_reason
- close_action
- close_pnl_estimate
- realized_expectancy_source

## 5. Proposed Log File

Recommended file:

```text
logs/symbol_validation.log
```

Recommended JSONL payload:

```json
{
  "schema_version": "1.0",
  "event": "order_result",
  "timestamp": "2026-04-30 00:00:00",
  "symbol": "ALGOUSDT",
  "strategy_name": "pullback_v1",
  "decision_id": "ALGOUSDT-pullback_v1-0",
  "signal_price": 0.0,
  "validated_price": 0.0,
  "validated_qty": 0.0,
  "notional_value": 0.0,
  "orderbook": {
    "best_bid": 0.0,
    "best_ask": 0.0,
    "spread_pct": 0.0,
    "imbalance": 0.0,
    "bid_depth_notional": 0.0,
    "ask_depth_notional": 0.0
  },
  "exchange": {
    "order_id": null,
    "status": "UNKNOWN",
    "executed_qty": 0.0,
    "cummulative_quote_qty": 0.0,
    "fill_price": null
  },
  "slippage_pct": null,
  "reason": "not_recorded"
}
```

## 6. Promotion Criteria

Minimum required realized results:

```text
closed_trades >= 30
profit_factor >= 1.30
realized_expectancy > 0
order_reject_rate < 0.02
max_consecutive_losses <= 3
slippage_abs_pct median <= observed spread-adjusted threshold
```

Promotion remains blocked if:

- official live gate is failed,
- risk guard is active,
- open trade exists,
- pending order exists,
- exchange filter validation fails,
- orderbook snapshot is stale or unusable for repeated entries,
- realized metrics contradict scanner metrics.

## 7. Comparison Baseline

Compare ALGOUSDT against current ETHUSDT baseline:

- realized expectancy,
- profit factor,
- win rate,
- average win,
- average loss,
- maximum consecutive loss,
- order rejection rate,
- average slippage,
- spread and orderbook depth at entry.

## 8. Required Implementation Before Test

Before any testnet symbol switch:

1. Add symbol validation log writer.
2. Add slippage calculation from signal price and fill price.
3. Add dashboard validation panel.
4. Add explicit config change record for `SYMBOL`.
5. Confirm no open trade and no pending order.
6. Run one dry precheck using exchange filters only.

## 9. Decision

Decision:

```text
ALGOUSDT_RUNTIME_PROMOTION = NOT_APPROVED
NEXT_STEP = BUILD_VALIDATION_LOGGING_AND_DASHBOARD_OBSERVATION
```

## 10. Record

2026-04-30: ALGOUSDT was identified as the primary review candidate from read-only multi-symbol scanning. It requires live testnet validation with execution-quality logging before any runtime promotion.
