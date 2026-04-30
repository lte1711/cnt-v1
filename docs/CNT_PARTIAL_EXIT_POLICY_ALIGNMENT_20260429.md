---
tags:
  - cnt
  - status/active
  - type/implementation
  - risk
  - partial-exit
created: 2026-04-29
---

# CNT Partial Exit Policy Alignment 20260429

```text
PROJECT = CNT
REPORT_TIME = 2026-04-29
REPORT_RULE = FACT / VERIFIED / UNKNOWN
```

## Design Summary

The active project rule says `PARTIAL_EXIT=FORBIDDEN`. Current runtime config previously had `ENABLE_PARTIAL_EXIT=True`, and the exit manager could produce `PARTIAL` exit signals if old or future state contained `partial_exit_levels`.

This change aligns runtime behavior with the active project rule.

## Implementation

```text
config.py
- ENABLE_PARTIAL_EXIT changed from True to False

src/risk/enhanced_exit_manager.py
- added ENABLE_PARTIAL_EXIT guard before partial-exit signal evaluation

tests/test_exit_manager.py
- updated partial-exit tests to verify partial levels are ignored while the feature is disabled
```

## Validation Result

```text
VALIDATION = PASS
COMMAND = python -m pytest -q
RESULT = 66 passed in 0.31s
```

## Record Text

```text
PARTIAL_EXIT_POLICY_ALIGNMENT = IMPLEMENTED
AUTHORITATIVE_RULE = PARTIAL_EXIT_FORBIDDEN
RUNTIME_CONFIG = ENABLE_PARTIAL_EXIT_FALSE
RUNTIME_GUARD = ACTIVE
```

## Obsidian Links

- [[00 Docs Index]]
- [[CNT_PARTIAL_EXIT_CONFIG_ALIGNMENT_REGISTER_20260426]]
- [[CNT_PROJECT_STATUS_ANALYSIS_20260429]]
