---
title: CNT Multi Symbol Validation Next Step Review 20260430
created: 2026-04-30
project: CNT
status: REVIEW
mode: BINANCE_SPOT_TESTNET
---

# CNT Multi Symbol Validation Next Step Review 20260430

## 1. Scope

This review evaluates the next step of checking multiple symbols, finding higher win-rate candidates, and validating whether CNT should proceed to symbol expansion.

## 2. Current Verified State

FACT:

- Runtime symbol is configured as `ETHUSDT`.
- Current runtime supports one configured symbol through `config.SYMBOL`.
- Current active strategy is `pullback_v1`.
- Current active strategy set contains only `pullback_v1`.
- Current local strategy metrics are based on existing CNT runtime history, not a broad multi-symbol comparison.
- Current `strategy_metrics.json` contains `pullback_v1` and legacy `breakout_v1` metrics, not per-symbol candidate metrics.
- Current `portfolio.log` evidence is dominated by `ETHUSDT`.
- Current official gate remains failed because cumulative expectancy is non-positive.
- Current daily loss guard has reached the configured threshold.
- Current minimum trade quantity is `0.01`, which is compatible with the current ETHUSDT operation but is not automatically a universal quantity for every symbol.

VERIFIED references:

- `config.py`
- `data/strategy_metrics.json`
- `logs/portfolio.log`
- `src/strategy_manager.py`
- `src/models/market_context.py`

## 3. Main Finding

Checking other symbols is applicable, but it must be done as offline validation first.

It is not correct to pick a symbol from raw recent win rate alone because:

- CNT does not yet have per-symbol live trade samples.
- A high win rate can still have negative expectancy if average loss is larger than average win.
- Some symbols may pass strategy logic but fail liquidity, spread, minimum notional, or lot-size practicality.
- `MIN_TRADE_QTY = 0.01` is not a universal multi-symbol sizing rule.
- Current operation state is risk pause and live gate fail.

## 4. Required Candidate Filters

Before any symbol is considered for runtime operation, it should pass:

1. Binance Spot Testnet availability.
2. `USDT` quote asset.
3. Trading status active.
4. Valid `PRICE_FILTER`.
5. Valid `LOT_SIZE`.
6. Valid `MIN_NOTIONAL` or `NOTIONAL`.
7. Sufficient 1m and 5m kline history.
8. Reasonable spread and depth from orderbook snapshot.
9. Sizing feasibility under the current minimum notional rule.
10. No requirement to bypass single-position operation.

## 5. Recommended Offline Scoring

Candidate symbols should be scored with at least:

```text
trades_closed
win_rate
expectancy
profit_factor
max_loss
average_win
average_loss
signal_count
rejected_signal_count
spread_pct
orderbook_imbalance
depth_notional
min_notional_pass
lot_size_pass
```

Minimum acceptance rule:

```text
sample_trades >= 20
win_rate > 0.52
expectancy > 0
profit_factor > 1.10
valid_order_filters = true
spread_pct within observed safe range
```

For early exploration, a candidate can be labeled watchlist with fewer trades, but it must not be promoted to runtime operation.

## 6. Correct Next Step

The correct next step is not live symbol switching.

The correct next step is:

```text
1. Build read-only symbol candidate scanner.
2. Pull exchangeInfo for USDT spot symbols.
3. Replay pullback_v1 on recent 1m and 5m klines per symbol.
4. Apply the same target and stop model.
5. Check order filters and practical sizing.
6. Include orderbook auxiliary metrics.
7. Write data/symbol_candidate_report.json.
8. Display top candidates on dashboard as observation only.
9. Review results before changing config.SYMBOL.
```

## 7. Runtime Boundary

Runtime must remain:

```text
SINGLE_POSITION_ONLY = TRUE
ONE_PENDING_ONLY = TRUE
one active execution symbol at a time
```

Multi-symbol research can run read-only, but live execution must not become multi-symbol without a separate architecture change.

## 8. Quantity Policy Warning

FACT:

- `MIN_TRADE_QTY = 0.01` was added for the current ETHUSDT minimum-notional problem.

Risk:

- `0.01 BTC` is a much larger notional than `0.01 ETH`.
- `0.01` of a low-price asset may be below minimum notional.

Therefore, symbol validation should use:

```text
per-symbol exchange filters
min notional target
step size aligned quantity
optional symbol-specific minimum base quantity
```

The project should not assume `0.01` is valid for all symbols.

## 9. Decision

Decision:

```text
MULTI_SYMBOL_RESEARCH = YES
LIVE_SYMBOL_SWITCH_NOW = NO
FIRST_STAGE = READ_ONLY_SYMBOL_SCANNER
RUNTIME_MULTI_SYMBOL = FORBIDDEN_UNTIL_APPROVED
```

## 10. Record

2026-04-30: Multi-symbol validation was reviewed. CNT can proceed with a read-only symbol candidate scanner and dashboard observation. Current evidence does not support immediate live symbol switching or multi-symbol execution.
