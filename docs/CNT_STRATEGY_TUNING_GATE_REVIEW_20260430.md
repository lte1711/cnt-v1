---
tags:
  - cnt
  - type/review
  - strategy
  - tuning
created: 2026-04-30
---

# CNT Strategy Tuning Gate Review 20260430

```text
PROJECT = CNT
REPORT_TIME = 2026-04-30 22:41:51
REPORT_RULE = FACT / VERIFIED / UNKNOWN
```

## Design Summary

This review checks whether `pullback_v1` should be modified immediately after resolving the existing undersized open trade.

## Validation Result

```text
ACTIVE_STRATEGY = pullback_v1
LIVE_GATE = FAIL / NON_POSITIVE_EXPECTANCY
POST_POLICY_CLOSED_TRADES = 0
MINIMUM_REVIEW_SAMPLE = 10
TUNING_DECISION = DEFER
CODE_CHANGE_MADE = FALSE
```

## Review

Current aggregate performance is negative:

```text
closed_trades = 63
expectancy = -0.0003192698
profit_factor = 0.9542941544
net_pnl = -0.020114
```

However, the latest closed trade was a legacy undersized position that required manual protective resolution. It should not be treated as evidence about the new `MIN_TRADE_QTY = 0.01` policy.

Immediate parameter tuning is rejected because there are no closed post-policy trades yet.

## Tuning Gate

```text
TUNING_ALLOWED_WHEN:
1. at least 10 closed trades opened after 2026-04-30 22:41:51
2. no exchange NOTIONAL failures on post-policy exits
3. expectancy remains <= 0
4. market-context split identifies a repeatable weak branch
```

Candidate areas for later review, not applied now:

- relaxed RSI branch
- near-trend branch
- PRIMARY_UP_ENTRY_UP context
- low-volume entry context

## Record Text

```text
STRATEGY_TUNING_REVIEW_COMPLETED = TRUE
TUNING_APPLIED = FALSE
TUNING_REASON = INSUFFICIENT_POST_POLICY_SAMPLE
NEXT_ACTION = CONTINUE_OBSERVATION
```
