---
tags:
  - cnt
  - type/report
  - observation
  - min-trade-policy
created: 2026-04-30
---

# CNT Post Min Trade Observation Start 20260430

```text
PROJECT = CNT
REPORT_TIME = 2026-04-30 22:41:51
REPORT_RULE = FACT / VERIFIED / UNKNOWN
```

## Design Summary

This document starts the observation window after resolving the existing undersized open trade and after applying the `MIN_TRADE_QTY = 0.01` policy.

Only trades opened after this baseline should be used for judging whether the new minimum trade policy improves exit reliability and strategy performance.

## Validation Result

```text
BASELINE_TIMESTAMP = 2026-04-30 22:41:51
BASELINE_ACTION = STOP_MARKET_FILLED
BASELINE_REASON = manual_protective_exit_min_notional_override
OPEN_TRADE = null
PENDING_ORDER = null
PORTFOLIO_OPEN_POSITIONS = []
MIN_TRADE_QTY = 0.01
LIVE_GATE = FAIL / NON_POSITIVE_EXPECTANCY
DAILY_LOSS_COUNT = 3
CONSECUTIVE_LOSSES = 1
```

## Baseline Metrics

```text
closed_trades = 63
wins = 32
losses = 31
win_rate = 0.5079365079
expectancy = -0.0003192698
profit_factor = 0.9542941544
net_pnl = -0.020114
```

## Observation Rule

```text
POST_POLICY_OBSERVATION_START = 2026-04-30 22:41:51
INCLUDE_TRADES_OPENED_AFTER = 2026-04-30 22:41:51
EXCLUDE_LEGACY_UNDERSIZED_TRADES = TRUE
MINIMUM_REVIEW_SAMPLE = 10 closed post-policy trades
PARAMETER_CHANGE_DURING_OBSERVATION = FORBIDDEN
```

## Record Text

```text
POST_MIN_TRADE_OBSERVATION_STARTED = TRUE
CURRENT_LEGACY_OPEN_TRADE_RESOLVED = TRUE
NEW_POLICY_EFFECT_NOT_YET_MEASURABLE = TRUE
NEXT_REVIEW_CONDITION = AT_LEAST_10_CLOSED_POST_POLICY_TRADES
```
