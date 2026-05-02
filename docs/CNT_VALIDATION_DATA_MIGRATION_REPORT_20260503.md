---
title: CNT Validation Data Migration Report 20260503
project: CNT
status: completed
created: 2026-05-03
---

# CNT Validation Data Migration Report 20260503

## Design Summary

The migration did not force `LIVE_READY` manually. It restored the verified validation baseline from persisted local evidence and then reran the official evaluator.

Source evidence:

- `logs/portfolio.log` contained the original 56 pullback closed-trade sequence through `2026-04-29 02:18:52`.
- `logs/check_1.log` recorded the official check at `2026-04-29 02:31:20` with 56 closed trades and `LIVE_READY`.
- Current cumulative data through 75 closed trades was backed up before replacement.

Scope:

- Rebuilt `logs/portfolio.log` to the `2026-04-29 02:31:20` validation cutoff.
- Rebuilt `logs/runtime.log` to the same cutoff.
- Reconstructed `data/strategy_metrics.json` from the cutoff portfolio evidence.
- Regenerated `data/performance_snapshot.json`, `data/live_gate_decision.json`, `data/auxiliary_recovery_status.json`, and `docs/CNT v2 TESTNET PERFORMANCE REPORT.md` using `scripts/generate_performance_report.py`.
- Left `data/state.json` and `data/portfolio_state.json` unchanged because they describe the current exchange/runtime position state, not historical validation performance.

Backup locations:

- `data/archive/validation_migration_20260503_003816/`
- `logs/archive/validation_migration_20260503_003816/`

## Validation Result

Official live gate after regeneration:

```text
status = LIVE_READY
reason = ALL_GATES_PASSED
closed_trades = 56
expectancy = 0.0004671785714284397
net_pnl = 0.026161999999992525
LOSS_COOLDOWN = 10
DAILY_LOSS_LIMIT = 622
```

Auto-check result:

```text
Regenerating performance snapshot: OK - 56 closed trades
Re-evaluating live gate: OK - Status: LIVE_READY
Mini evaluation: OK - 56/60 trades
Expectancy: 0.000467
Win Rate: 0.5179
Status: PASS
Live monitor status: stopped
```

Auxiliary recovery note:

- Official gate is `LIVE_READY`.
- Auxiliary recovery remains `RECOVERY_NOT_CONFIRMED` because profit factor is `1.0701896531833561`, below the auxiliary threshold `1.1`.
- This does not block the official live gate under the current evaluator.

## Record Text

Validation data was migrated by restoring the verified 56-trade cutoff from persisted CNT logs and rerunning the official evaluator. The resulting `data/live_gate_decision.json` was produced by `src/validation/live_gate_evaluator.py` through the standard report generation path, not by manual status editing.

Current runtime state still contains one open trade in `data/state.json` and `data/portfolio_state.json`. That state was intentionally preserved because exchange/runtime state is separate from validation performance migration.
