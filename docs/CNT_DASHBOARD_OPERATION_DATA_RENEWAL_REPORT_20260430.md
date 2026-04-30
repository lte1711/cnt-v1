---
tags:
  - cnt
  - type/report
  - dashboard
  - operations
created: 2026-04-30
---

# CNT Dashboard Operation Data Renewal Report 20260430

```text
PROJECT = CNT
REPORT_TIME = 2026-04-30
REPORT_RULE = FACT / VERIFIED / UNKNOWN
```

## Design Summary

The operations dashboard was renewed for the new operating mode after the legacy undersized open trade was resolved and `MIN_TRADE_QTY = 0.01` became the active entry policy.

The dashboard now reads a dedicated baseline data file:

- `data/operation_baseline.json`

The dashboard now emphasizes:

- official live gate status
- post-policy observation phase
- post-policy closed trade sample count
- risk guard pause state
- flat position and pending-order state
- new minimum trade quantity policy
- cumulative performance as historical context only

Removed stale dashboard emphasis:

- auxiliary recovery as a primary panel
- legacy open-trade notional risk as an active condition
- V3 setup bottleneck deep-dive as a primary operating panel
- nested metric cards inside larger cards
- old "Operational Decision Console" wording

## Validation Result

```text
DASHBOARD_FILE = docs/cnt_operations_dashboard.html
BASELINE_FILE = data/operation_baseline.json
BASELINE_JSON_VALID = TRUE
LOCAL_HTTP_STATUS = 200
DASHBOARD_SCRIPT_SYNTAX = PASS
CURRENT_PHASE = RISK_PAUSE
CURRENT_OPEN_TRADE = null
CURRENT_PENDING_ORDER = null
POST_POLICY_CLOSED_TRADES = 0
MINIMUM_REVIEW_SAMPLE = 10
FULL_TEST_RESULT = 70 passed
```

## Record Text

```text
DASHBOARD_OPERATION_DATA_RENEWAL_COMPLETED = TRUE
POST_POLICY_BASELINE_DATA_ADDED = TRUE
RISK_GUARD_VISIBILITY_ADDED = TRUE
POST_POLICY_SAMPLE_VISIBILITY_ADDED = TRUE
STALE_DASHBOARD_SECTIONS_REMOVED = TRUE
RUNTIME_ORDER_POLICY_CHANGED = FALSE
VALIDATION_STATUS = VERIFIED
```
