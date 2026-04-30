---
tags:
  - cnt
  - config
  - risk
  - follow-up
  - status/active
  - type/documentation
  - type/validation
  - type/operation
  - type/analysis
---

# CNT Partial Exit Config Alignment Register 20260426

## Design Summary

- Scope: register the current `ENABLE_PARTIAL_EXIT` and `PARTIAL_EXIT=FORBIDDEN` mismatch as a follow-up item.
- No code, config, runtime state, or order behavior was changed in this step.
- Current decision: keep the running system unchanged for now, continue observation, and fix the mismatch before live readiness approval.
- 2026-04-29 update: follow-up alignment has been implemented in [[CNT_PARTIAL_EXIT_POLICY_ALIGNMENT_20260429]].

## Registered Item

```text
DATE=2026-04-26
TYPE=config
PATH=config.py
SUMMARY=ENABLE_PARTIAL_EXIT previously remained True while AGENTS.md forbids partial exit.
REASON=Current runtime has no open_trade and no pending_order, and DAILY_LOSS_LIMIT is blocking new entries. Immediate runtime risk is low, but the config and constitution are not aligned.
CURRENT_DECISION=resolved_2026_04_29
NEXT_ACTION=Keep partial exit disabled unless the active project rule is explicitly changed.
NOTE=Resolved by setting ENABLE_PARTIAL_EXIT=False and adding a runtime guard.
```

## Current Risk Judgment

```text
LEAVE_AS_IS_NOW              = RESOLVED
IMMEDIATE_RUNTIME_RISK       = LOW
CONSTITUTION_ALIGNMENT       = CLEAN_FOR_PARTIAL_EXIT_POLICY
ACTION_URGENCY              = COMPLETED
LIVE_APPROVAL_BLOCKER        = NO_FOR_PARTIAL_EXIT_POLICY
```

## Required Follow-Up

1. Reconfirm `data/state.json` has no `open_trade` and no `pending_order`. Completed 2026-04-29.
2. Change `config.py` from `ENABLE_PARTIAL_EXIT = True` to `ENABLE_PARTIAL_EXIT = False`. Completed 2026-04-29.
3. Add a runtime guard so existing `partial_exit_levels` are ignored when partial exits are disabled. Completed 2026-04-29.
4. Update or reclassify tests that currently expect partial exit execution. Completed 2026-04-29.
5. Run validation with `PYTHONPATH=.` and `pytest -q`. Completed 2026-04-29 with `python -m pytest -q`.
6. Record the result in a follow-up implementation report. Completed in [[CNT_PARTIAL_EXIT_POLICY_ALIGNMENT_20260429]].

## Validation Result

FACT:

- `config.py` currently contains `ENABLE_PARTIAL_EXIT = False`.
- `AGENTS.md` currently contains `PARTIAL_EXIT=FORBIDDEN`.
- Current local runtime state previously showed no open trade and no pending order at the latest reviewed checkpoint.

VERIFIED:

- Partial-exit runtime policy is now aligned with the active project rule.

## Record Text

The partial-exit mismatch was resolved on 2026-04-29. Runtime config now disables partial exit, and the exit manager ignores stored `partial_exit_levels` while the feature is disabled.

Related documents:

- [[AGENTS]]
- [[CNT_PRECISION_ANALYSIS_REPORT_20260426]]
- [[CNT_PROJECT_STATUS_REPORT_20260426]]
- [[CNT v2 LIVE READINESS GATE]]
- [[CNT_PARTIAL_EXIT_POLICY_ALIGNMENT_20260429]]
- [[00 Docs Index]]
