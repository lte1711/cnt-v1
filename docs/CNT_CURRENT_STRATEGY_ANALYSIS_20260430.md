---
tags:
  - cnt
  - type/analysis
  - strategy
  - runtime
created: 2026-04-30
---

# CNT Current Strategy Analysis 20260430

```text
PROJECT = CNT
REPORT_TIME = 2026-04-30
REPORT_RULE = FACT / VERIFIED / UNKNOWN
```

## Design Summary

This analysis verifies the currently active strategy from local repository configuration, strategy implementation, runtime state, strategy metrics, performance snapshot, live gate decision, runtime log, and signal log.

## Validation Result

```text
ACTIVE_STRATEGY = pullback_v1
ACTIVE_STRATEGIES = ["pullback_v1"]
SYMBOL = ETHUSDT
LIVE_GATE = FAIL / NON_POSITIVE_EXPECTANCY
OPEN_TRADE = TRUE
CURRENT_ACTION = ERROR
RECENT_ERROR = Binance NOTIONAL filter failure on existing undersized open trade
CODE_CHANGE_MADE = FALSE
```

## Strategy Summary

`pullback_v1` is a trend pullback re-entry strategy. It evaluates 1-minute entry interval indicators using EMA fast, EMA slow, and RSI. A BUY signal is generated when the short-term trend is up or near trend recovery and RSI is inside the configured pullback range.

Entry conditions:

- Core trend re-entry: `ema_fast > ema_slow` and RSI between `40` and `52`
- Relaxed RSI re-entry: `ema_fast > ema_slow` and RSI between `38` and `56`
- Near-trend re-entry: EMA fast is slightly below EMA slow but within `0.0008` tolerance, and RSI is in the core range

Exit model:

- Target price is entry price plus `0.18%`
- Stop price is entry price minus `0.15%`
- Trailing stop pct is supplied by runtime extension
- Time exit is supplied by runtime extension
- Partial exit is disabled by current config

## Current Runtime Evidence

```text
state.last_run_time = 2026-04-30 22:34:00
state.strategy_name = pullback_v1
state.action = ERROR
state.pending_order = null
state.open_trade.entry_price = 2273.28
state.open_trade.entry_qty = 0.0022
state.open_trade.stop_price = 2269.87008
state.open_trade.target_price = 2277.371904
state.price = 2260.58
```

The current open trade predates the new `MIN_TRADE_QTY = 0.01` policy and remains below that policy size.

## Performance Evidence

```text
closed_trades = 62
wins = 32
losses = 30
win_rate = 0.5161290323
expectancy = -0.0000799355
profit_factor = 0.9883365457
net_pnl = -0.004956
```

## Assessment

`pullback_v1` is still the only active execution strategy, but current evidence does not support live readiness. The strategy has a slightly positive win rate, but average loss is larger than average win, so expectancy and net PnL are negative. The official live gate correctly fails with `NON_POSITIVE_EXPECTANCY`.

The immediate operational issue is not signal generation. The current open trade is undersized relative to Binance notional requirements after price dropped, causing repeated protective exit errors. The committed `MIN_TRADE_QTY = 0.01` policy prevents this for future entries, but it does not mutate the current open trade.

## Record Text

```text
CURRENT_STRATEGY_ANALYSIS_COMPLETED = TRUE
ACTIVE_EXECUTION_STRATEGY = pullback_v1
STRATEGY_STATUS = ACTIVE_BUT_NOT_LIVE_READY
PRIMARY_WEAKNESS = EXPECTANCY_AND_NET_PNL_NEGATIVE
IMMEDIATE_RUNTIME_RISK = EXISTING_UNDERSIZED_OPEN_TRADE_NOTIONAL_FAILURE
PARAMETER_CHANGE_RECOMMENDED_NOW = FALSE
NEXT_ACTION = RESOLVE_CURRENT_OPEN_TRADE_AND_CONTINUE_OBSERVATION_AFTER_MIN_TRADE_QTY_POLICY
```
