---
tags:
  - cnt
  - status/active
  - type/analysis
  - runtime
  - live-gate
created: 2026-04-29
---

# CNT Project Status Analysis 20260429

```text
PROJECT = CNT
REPORT_TIME = 2026-04-29
SOURCE = local repository, data files, logs, docs, tests
REPORT_RULE = FACT / VERIFIED / UNKNOWN
```

## Design Summary

This analysis checks the current CNT repository state against the active project rules and the latest runtime evidence. It uses repository-local evidence only: `data/*.json`, `logs/*.log`, current source files, and current documentation.

## Validation Result

```text
PYTEST = PASS
TEST_COUNT = 66
COMMAND = python -m pytest -q
RESULT = 66 passed in 0.38s
```

## Current Status

### VERIFIED

- Runtime state is current through `2026-04-29 14:54:04`.
- Scheduler heartbeat reports `last_event=finish`, `exit_code=0`, and `gap_detected=false`.
- Active runtime strategy is `pullback_v1`.
- Current symbol is `ETHUSDT`.
- Current local state has no pending order and no open trade.
- Latest engine action is `NO_ENTRY_SIGNAL`.
- Latest portfolio state has `open_positions=[]` and `total_exposure=0.0`.
- Official live gate status is `LIVE_READY / ALL_GATES_PASSED`.
- Current performance snapshot shows:
  - `closed_trades=58`
  - `wins=30`
  - `losses=28`
  - `win_rate=0.5172413793`
  - `expectancy=0.0003630689655171092`
  - `profit_factor=1.0544335503816444`
  - `net_pnl=0.021057999999992305`
- Risk counters are active:
  - `daily_loss_count=3`
  - `consecutive_losses=1`
  - `last_loss_time=2026-04-29 11:34:01`
- Current risk blocks are real and recent. Runtime logs after `2026-04-29 11:54:01` include repeated `EXECUTION_BLOCKED_BY_RISK` with reason `DAILY_LOSS_LIMIT`.
- `breakout_v1` is deactivated from the strategy registry, but historical `breakout_v1` metrics remain in `data/strategy_metrics.json`.
- `breakout_v3` is running as a shadow evaluator, not as the active execution strategy.
- `breakout_v3` shadow snapshot currently shows `signal_count=380`, `allowed_signal_count=19`, and `allowed_signal_ratio=0.05`.
- Source entry chain remains `run.ps1 -> main.py -> src.engine.start_engine`.
- Test suite currently passes.

### FACT

- `config.py` sets `ACTIVE_STRATEGY="pullback_v1"` and `ACTIVE_STRATEGIES=["pullback_v1"]`.
- `src/strategy_registry.py` registers `breakout_v2`, `pullback_v1`, and `mean_reversion_v1`; `breakout_v1` is commented out.
- `src/validation/live_gate_evaluator.py` grants `LIVE_READY` when:
  - closed trades are at least 50,
  - expectancy is positive,
  - net PnL is positive,
  - max consecutive losses is not above 5,
  - risk guard triggers have been observed.
- The official gate does not require `profit_factor >= 1.1`.
- Auxiliary recovery status is more conservative than the official gate and says `RECOVERY_NOT_CONFIRMED` because `profit_factor_pass=false` at the auxiliary threshold `min_profit_factor=1.1`.
- Current docs contain two zero-byte files:
  - `docs/2026-04-29.md`
  - `docs/202604290305.md`
- Several recent Korean docs and `TRADE_VALIDATION_READY.txt` display mojibake in the current shell output, so documentation encoding/readability remains a maintenance issue.
- Git worktree is dirty before this report; modified and untracked files existed before this analysis.

### UNKNOWN

- Exchange-side account/order truth was not re-queried during this analysis.
- Binance Spot Testnet account balances are not verified in this report.
- Whether the most recent `DAILY_LOSS_LIMIT` block should prevent immediate live deployment depends on the intended operating policy. The code treats risk-guard observation as a positive live-gate criterion, while runtime risk guard currently prevents new entries after the daily loss limit.
- The exact intended status of partial exit is unresolved. The active project rule says `PARTIAL_EXIT=FORBIDDEN`, while current config and engine code include partial-exit support and `ENABLE_PARTIAL_EXIT=True`.

## Assessment

The project is no longer in early readiness. It has a working one-shot scheduled runtime, passing tests, current runtime evidence, positive pullback-only expectancy, and an official `LIVE_READY` gate.

However, it is not cleanly deployable without an operator decision because the runtime is currently under the daily loss limit and the auxiliary recovery gate is not confirmed. The strongest current strategy is `pullback_v1`, but its edge is thin: positive expectancy and net PnL are verified, while profit factor is only `1.0544`.

The current practical state is:

```text
OFFICIAL_GATE = LIVE_READY
RUNTIME_EXECUTION = BLOCKED_WHEN_SIGNAL_APPEARS_BY_DAILY_LOSS_LIMIT
ACTIVE_STRATEGY = pullback_v1
OPEN_RISK = PARTIAL_EXIT_RULE_CONFLICT, AUXILIARY_RECOVERY_NOT_CONFIRMED, DOC_ENCODING_HYGIENE
```

## Recommended Next Step

1. Do not change strategy parameters before resolving the rule conflict.
2. Decide whether `PARTIAL_EXIT=FORBIDDEN` remains authoritative; if yes, set runtime partial exit behavior to disabled and verify tests.
3. Treat `LIVE_READY` as official but not sufficient alone for real deployment while `daily_loss_count=3` is active.
4. Continue pullback-only observation until profit factor either clears the auxiliary `1.1` threshold or the auxiliary threshold is explicitly retired.
5. Clean zero-byte docs and encoding-damaged docs under a separate documentation maintenance task.

## Record Text

```text
STATUS_ANALYSIS_COMPLETED = TRUE
RUNTIME_EVIDENCE_VERIFIED = TRUE
TESTS_PASSED = TRUE
OFFICIAL_LIVE_GATE = LIVE_READY
IMMEDIATE_DEPLOYMENT_DECISION = NEEDS_OPERATOR_DECISION
PRIMARY_BLOCKERS = DAILY_LOSS_LIMIT_ACTIVE, PARTIAL_EXIT_RULE_CONFLICT, AUXILIARY_RECOVERY_NOT_CONFIRMED
```

## Obsidian Links

- [[00 Docs Index]]
- [[CNT v2 TESTNET PERFORMANCE REPORT]]
- [[CNT v2 LIVE READINESS GATE]]
- [[CNT LIVE_GATE_BREAKOUT_V1_REMOVAL_PLAN_20260428]]
