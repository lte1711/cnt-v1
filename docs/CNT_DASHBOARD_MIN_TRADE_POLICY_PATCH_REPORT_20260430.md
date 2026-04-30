---
tags:
  - cnt
  - type/report
  - dashboard
  - order-validation
created: 2026-04-30
---

# CNT Dashboard Min Trade Policy Patch Report 20260430

```text
PROJECT = CNT
REPORT_TIME = 2026-04-30
REPORT_RULE = FACT / VERIFIED / UNKNOWN
```

## Design Summary

The operations dashboard now reflects the current runtime state and the new minimum trade quantity policy.

The dashboard adds visible policy checks for:

- new entry minimum quantity `0.01 ETH`
- minimum notional guard `5.00 USDT`
- existing open trade quantity below the new policy
- existing open trade stop-notional risk

This is a display and observability patch only. It does not change runtime order behavior.

## Validation Result

```text
DASHBOARD_FILE = docs/cnt_operations_dashboard.html
LOCAL_HTTP_STATUS = 200
SCRIPT_SYNTAX_CHECK = PASS
COMMAND = node -e "extract dashboard script and compile with vm.Script"
RUNTIME_DATA_REFLECTED = TRUE
CURRENT_LIVE_GATE = FAIL / NON_POSITIVE_EXPECTANCY
CURRENT_OPEN_TRADE_QTY = 0.0022
PROJECT_MIN_TRADE_QTY = 0.01
CURRENT_OPEN_TRADE_POLICY_CLASSIFICATION = LEGACY
```

## Record Text

```text
DASHBOARD_MIN_TRADE_POLICY_DISPLAY = APPLIED
DASHBOARD_LEGACY_OPEN_TRADE_WARNING = APPLIED
DASHBOARD_STOP_NOTIONAL_RISK_WARNING = APPLIED
RUNTIME_ORDER_POLICY_CHANGED = FALSE
ENTRY_CHAIN_CHANGED = FALSE
VALIDATION_STATUS = VERIFIED_BY_LOCAL_HTTP_AND_SCRIPT_SYNTAX
```
