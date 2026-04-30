from __future__ import annotations

from config import MIN_TRADE_QTY
from src.models.execution_decision import ExecutionDecision
from src.models.portfolio_state import PortfolioState
from src.models.strategy_signal import StrategySignal
from src.order_validator import auto_adjust_order_inputs
from src.risk.portfolio_risk_manager import check_portfolio_risk
from src.risk.risk_guard import evaluate_risk


def decide_execution(
    signal: StrategySignal,
    state: dict | None,
    balance: dict | None,
    filters: dict,
    requested_qty: float = MIN_TRADE_QTY,
    portfolio_state: PortfolioState | None = None,
) -> ExecutionDecision:
    if not signal.entry_allowed:
        return ExecutionDecision(
            execute=False,
            action="NO_ENTRY_SIGNAL",
            reason="signal_not_entry_allowed",
            signal_reason=signal.reason,
            strategy_name=signal.strategy_name,
            symbol=signal.symbol,
            validated_qty=None,
            validated_price=None,
            notional_value=None,
            risk_check_passed=False,
            risk_rejection_reason="signal_not_entry_allowed",
            portfolio_rejection_reason=None,
            selected_priority=None,
            slippage_check_passed=True,
            slippage_rejection_reason=None,
        )

    candidate_price = float(signal.entry_price_hint) if signal.entry_price_hint is not None else 0.0
    if candidate_price <= 0:
        return ExecutionDecision(
            execute=False,
            action="BUY_REJECTED_INVALID_ENTRY_HINT",
            reason="invalid_entry_price_hint",
            signal_reason=signal.reason,
            strategy_name=signal.strategy_name,
            symbol=signal.symbol,
            validated_qty=None,
            validated_price=None,
            notional_value=None,
            risk_check_passed=True,
            risk_rejection_reason=None,
            portfolio_rejection_reason=None,
            selected_priority=1,
            slippage_check_passed=False,
            slippage_rejection_reason="invalid_entry_price_hint",
        )

    min_notional_reference_price = None
    if signal.exit_model is not None and signal.exit_model.stop_price is not None:
        min_notional_reference_price = float(signal.exit_model.stop_price)

    policy_qty = max(float(requested_qty), float(MIN_TRADE_QTY))

    adjusted = auto_adjust_order_inputs(
        candidate_price,
        policy_qty,
        filters,
        min_notional_reference_price=min_notional_reference_price,
    )
    adjusted_price = float(adjusted["adjusted_price"])
    adjusted_qty = float(adjusted["adjusted_qty"])
    requested_notional = adjusted_price * adjusted_qty

    if portfolio_state is not None:
        portfolio_passed, portfolio_reason = check_portfolio_risk(
            signal,
            portfolio_state,
            requested_notional,
        )
        if not portfolio_passed:
            return ExecutionDecision(
                execute=False,
                action="EXECUTION_BLOCKED_BY_PORTFOLIO_RISK",
                reason=portfolio_reason or "portfolio_risk_rejected",
                signal_reason=signal.reason,
                strategy_name=signal.strategy_name,
                symbol=signal.symbol,
                validated_qty=adjusted_qty,
                validated_price=adjusted_price,
                notional_value=requested_notional,
                risk_check_passed=True,
                risk_rejection_reason=None,
                portfolio_rejection_reason=portfolio_reason,
                selected_priority=1,
                slippage_check_passed=True,
                slippage_rejection_reason=None,
            )

    risk_result = evaluate_risk(signal, state, balance)
    if not risk_result.passed:
        return ExecutionDecision(
            execute=False,
            action="EXECUTION_BLOCKED_BY_RISK",
            reason=risk_result.reason,
            signal_reason=signal.reason,
            strategy_name=signal.strategy_name,
            symbol=signal.symbol,
            validated_qty=None,
            validated_price=None,
            notional_value=None,
            risk_check_passed=False,
            risk_rejection_reason=risk_result.reason,
            portfolio_rejection_reason=None,
            selected_priority=1,
            slippage_check_passed=True,
            slippage_rejection_reason=None,
        )
    final_validation = adjusted.get("final_validation", {})

    if not final_validation.get("all_valid", False):
        return ExecutionDecision(
            execute=False,
            action="BUY_REJECTED_BY_VALIDATION",
            reason="buy_limit_validation_failed",
            signal_reason=signal.reason,
            strategy_name=signal.strategy_name,
            symbol=signal.symbol,
            validated_qty=adjusted_qty,
            validated_price=adjusted_price,
            notional_value=adjusted_price * adjusted_qty,
            risk_check_passed=True,
            risk_rejection_reason=None,
            portfolio_rejection_reason=None,
            selected_priority=1,
            slippage_check_passed=False,
            slippage_rejection_reason="buy_limit_validation_failed",
        )

    return ExecutionDecision(
        execute=True,
        action="EXECUTION_ALLOWED",
        reason="ok",
        signal_reason=signal.reason,
        strategy_name=signal.strategy_name,
        symbol=signal.symbol,
        validated_qty=adjusted_qty,
        validated_price=adjusted_price,
        notional_value=adjusted_price * adjusted_qty,
        risk_check_passed=True,
        risk_rejection_reason=None,
        portfolio_rejection_reason=None,
        selected_priority=1,
        slippage_check_passed=True,
        slippage_rejection_reason=None,
    )
