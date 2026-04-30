---
tags:
  - cnt
  - type/report
  - runtime
  - order-validation
created: 2026-04-30
---

# CNT Min Notional Entry Quantity Patch Report 20260430

```text
PROJECT = CNT
REPORT_TIME = 2026-04-30
REPORT_RULE = FACT / VERIFIED / UNKNOWN
```

## Design Summary

The runtime open trade review found that an entry quantity can pass `MIN_NOTIONAL` at the BUY entry price but later fail protective SELL MARKET notional validation after price falls toward the stop price.

The patch changes entry quantity adjustment so the execution decision can use the signal stop price as an additional `MIN_NOTIONAL` reference. This keeps the submitted BUY quantity high enough that the full position should still clear minimum notional at the deterministic stop price.

The follow-up patch adds a project-level minimum trade quantity:

```text
MIN_TRADE_QTY = 0.01
```

Entry execution now enforces the greater value between the requested quantity and `MIN_TRADE_QTY`. The engine and order roundtrip helper both use the same config value instead of the previous `0.001` default.

Changed files:

- `config.py`
- `src/engine.py`
- `src/order_validator.py`
- `src/execution_decider.py`
- `src/order_roundtrip.py`
- `tests/test_order_validator.py`
- `tests/test_execution_decider_min_notional.py`
- `tests/test_order_roundtrip.py`

## Validation Result

```text
TARGETED_TEST_COMMAND = python -m pytest tests\test_order_validator.py tests\test_execution_decider_min_notional.py -q
TARGETED_TEST_RESULT = 2 passed in 0.03s

FULL_TEST_COMMAND = python -m pytest -q
FULL_TEST_RESULT = 70 passed in 0.34s

PY_COMPILE_COMMAND = python -m py_compile config.py src\order_validator.py src\execution_decider.py src\engine.py src\order_roundtrip.py
PY_COMPILE_RESULT = PASS
```

## Record Text

```text
ENTRY_MIN_NOTIONAL_REFERENCE_PATCH = APPLIED
PROJECT_MIN_TRADE_QTY = 0.01
PROJECT_MIN_TRADE_QTY_PATCH = APPLIED
REFERENCE_PRICE_SOURCE = StrategySignal.exit_model.stop_price
ORDER_POLICY_CHANGED = FALSE
SIGNED_REQUEST_PATH_CHANGED = FALSE
ENTRY_CHAIN_CHANGED = FALSE
PROTECTIVE_SELL_MARKET_POLICY_CHANGED = FALSE
VALIDATION_STATUS = VERIFIED_BY_TESTS
```

## Notes

This patch prevents the same class of future undersized entries. It does not forcibly close or mutate the currently open local trade.
