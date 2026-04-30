---
title: CNT Orderbook Applicability Review 20260430
created: 2026-04-30
project: CNT
status: REVIEW
mode: BINANCE_SPOT_TESTNET
---

# CNT Orderbook Applicability Review 20260430

## 1. Scope

This review evaluates whether orderbook data can be applied to CNT-V1 under the current Binance Spot Testnet operation rules.

Source basis:

- User-provided orderbook usage summary.
- Local CNT code inspection.
- Current CNT operation baseline after the minimum trade quantity policy change.

This review does not approve a runtime strategy parameter change or live execution change.

## 2. Current Project Facts

FACT:

- CNT currently runs Binance Spot Testnet.
- Current active strategy is `pullback_v1`.
- Current active strategy set contains only `pullback_v1`.
- `MarketContext` already has a reserved `orderbook_imbalance` field.
- Current `strategy_manager` builds `MarketContext` from:
  - closed klines,
  - latest price,
  - configured symbol and intervals.
- Current `market_feature_snapshot` records candle, trend, RSI, EMA, ATR, and volume-derived features.
- Current runtime does not have an orderbook collector module.
- Current runtime does not have WebSocket depth ingestion.
- Current runtime does not have trade stream ingestion for spoofing or cancellation filtering.
- Current entry flow separates:
  - signal generation,
  - entry gate,
  - execution decision,
  - risk guard,
  - order validation.
- Current operation state is post-min-trade observation.
- Current official live gate remains failed because historical expectancy is non-positive.
- Current risk state has reached the daily loss count guard threshold.

VERIFIED local code references:

- `src/models/market_context.py`
- `src/strategy_manager.py`
- `src/market/feature_snapshot.py`
- `src/entry_gate.py`
- `src/execution_decider.py`
- `config.py`

## 3. User Proposal Assessment

The user-provided statement is directionally compatible with CNT:

```text
USE_ORDERBOOK = YES
USE_ALONE = NO
BEST_USAGE = FILTER + TIMING TOOL
```

FACT:

- CNT's current strategy weakness is not order submission mechanics only. Recent analysis found negative expectancy under the active strategy sample.
- Orderbook data can improve entry timing and liquidity awareness.
- Orderbook data cannot by itself prove future price direction.

Therefore, the proposal is applicable only as an additional context and filter layer, not as a standalone signal generator.

## 4. Compatibility With CNT Architecture

### 4.1 Direct Compatibility

FACT:

- `MarketContext.orderbook_imbalance` already exists.
- `StrategySignal.market_features` can carry additional observational data.
- `entry_gate` already accepts a `StrategySignal` and can block based on signal reason.
- `execution_decider` already owns execution/no-execution decision and validation handoff.

Assessment:

- CNT can accept orderbook features without changing the state machine.
- CNT can record orderbook metrics inside `market_features`.
- CNT can later use orderbook metrics as an entry filter if validated.

### 4.2 Missing Runtime Components

FACT:

- There is no orderbook collector.
- There is no depth snapshot parser.
- There is no rolling orderbook cache.
- There is no trade stream confirmation layer.
- There is no persistence file for orderbook-derived metrics.
- There is no dashboard section for orderbook quality or freshness.

Assessment:

- The project is structurally ready for an orderbook feature, but not implementation-complete.

## 5. Recommended Application Model

The correct CNT model is:

```text
strategy signal
  -> orderbook observational context
  -> entry filter candidate
  -> execution_decider
  -> existing risk and validation guards
```

Orderbook must not bypass:

- pending order checks,
- open trade checks,
- live gate status,
- risk guard,
- portfolio risk guard,
- exchange filter validation,
- minimum notional validation,
- minimum trade quantity policy.

## 6. Proposed Data Contract

Recommended orderbook metric object:

```json
{
  "schema_version": "1.0",
  "symbol": "ETHUSDT",
  "source": "binance_spot_testnet_depth",
  "timestamp": "2026-04-30T00:00:00Z",
  "best_bid": 0.0,
  "best_ask": 0.0,
  "spread": 0.0,
  "spread_pct": 0.0,
  "bid_depth_notional": 0.0,
  "ask_depth_notional": 0.0,
  "imbalance": 0.0,
  "depth_limit": 100,
  "freshness_ms": 0,
  "usable": false,
  "reason": "not_collected"
}
```

Recommended file:

```text
data/orderbook_snapshot.json
```

Recommended log:

```text
logs/orderbook.log
```

## 7. Strategy Usage Evaluation

### 7.1 Pullback V1

Applicable use:

- Block weak pullback entries when ask-side pressure is high.
- Confirm that bid-side depth is not materially weaker than ask-side depth before BUY LIMIT placement.
- Reject entries when spread is abnormal.

Recommended initial policy:

```text
observation_only = true
entry_blocking = false
```

Reason:

- Current live gate is failed.
- Current daily loss guard is already at the configured threshold.
- Post-policy sample count is not yet sufficient.

### 7.2 Breakout V3 Shadow

Applicable use:

- Add shadow-only orderbook metrics to compare breakout candidates against depth imbalance.
- Do not activate as runtime execution filter until shadow evidence exists.

### 7.3 Mean Reversion

Applicable use:

- Potentially useful for detecting exhaustion.

Restriction:

- Not recommended for immediate integration because `mean_reversion_v1` is inactive by default.

## 8. Implementation Boundary

Recommended modules:

- `src/market/orderbook_snapshot.py`: REST depth snapshot parsing and metric calculation.
- `src/market/orderbook_store.py`: optional snapshot load/save helper.
- `src/strategy_manager.py`: attach latest usable orderbook metric to `MarketContext`.
- `src/market/feature_snapshot.py`: include orderbook section in `market_features`.
- `docs/cnt_operations_dashboard.html`: display orderbook freshness, spread, imbalance, and usable status.

Do not modify first:

- `src/order_executor.py`
- `src/order_payload_builder.py`
- `src/order_query.py`
- shared signing path
- state machine flow
- exit manager

Reason:

- Orderbook should start as market context, not order submission logic.

## 9. Validation Requirements

Before runtime filtering:

1. Confirm REST depth endpoint works on Binance Spot Testnet.
2. Record depth snapshots without affecting entry decisions.
3. Add tests for spread and imbalance calculation.
4. Add dashboard visibility.
5. Run post-policy observation until minimum sample is reached.
6. Compare win/loss outcomes against orderbook metrics.
7. Only then promote to entry filter candidate.

Minimum safe validation:

```text
observation samples >= 50 signals
closed post-policy trades >= 10
orderbook freshness <= configured max age
spread_pct threshold validated from observed data
imbalance threshold validated from observed data
```

## 10. Risk Review

FACT:

- Orderbook walls can be canceled.
- REST depth snapshots are not sufficient to prove wall persistence.
- Trade stream confirmation is needed before treating wall data as strong evidence.
- CNT currently runs one-shot mode, not a persistent event loop.

Assessment:

- REST depth is suitable for initial observation and dashboard metrics.
- WebSocket depth is more suitable for production-grade timing.
- A persistent WebSocket collector is a larger architecture change than a REST snapshot feature.

## 11. Decision

Decision:

```text
APPLICABLE = YES
IMMEDIATE_EXECUTION_FILTER = NO
FIRST_STAGE = OBSERVATION_ONLY
BEST_INSERTION_POINT = MarketContext + market_features + dashboard
```

Reason:

- The architecture already has an orderbook field reservation.
- The active strategy can use orderbook as a secondary filter.
- Current live gate and risk state do not support immediate execution tightening or loosening without new evidence.
- Observation-first integration preserves CNT's verify-first and exchange-truth rules.

## 12. Recommended Next Step

Implement Stage 1 only:

```text
1. Add REST depth snapshot metric module.
2. Save data/orderbook_snapshot.json.
3. Attach orderbook metrics to market_features.
4. Add dashboard orderbook panel.
5. Keep entry decisions unchanged.
```

After Stage 1 evidence:

```text
Stage 2: add non-executing filter simulation.
Stage 3: promote validated filter to entry_gate or strategy signal reason.
Stage 4: evaluate WebSocket collector only if REST snapshot evidence is useful.
```

## 13. Record

2026-04-30: Orderbook applicability was reviewed against CNT-V1 architecture and current operation state. The feature is applicable as an observation and timing-quality metric. It is not approved as an immediate live execution filter. The first compatible implementation is a REST depth snapshot metric connected to `MarketContext`, `market_features`, and the dashboard without changing order execution behavior.
