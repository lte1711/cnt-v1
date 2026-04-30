from __future__ import annotations

from decimal import Decimal, ROUND_UP


def _to_decimal(value: str | float | int) -> Decimal:
    return Decimal(str(value))


def _floor_to_step(value: float, step: str) -> float:
    value_dec = _to_decimal(value)
    step_dec = _to_decimal(step)

    aligned = (value_dec // step_dec) * step_dec
    return float(aligned)


def _ceil_to_step(value: float, step: str) -> float:
    value_dec = _to_decimal(value)
    step_dec = _to_decimal(step)

    units = (value_dec / step_dec).quantize(Decimal("1"), rounding=ROUND_UP)
    aligned = units * step_dec
    return float(aligned)


def validate_price(price: float, price_filter: dict) -> dict:
    tick_size = price_filter.get("tick_size")
    min_price = float(price_filter.get("min_price", 0))
    max_price = float(price_filter.get("max_price", 0))

    if not tick_size:
        return {
            "valid": False,
            "reason": "missing_tick_size",
        }

    aligned_price = _floor_to_step(price, tick_size)

    if price < min_price or price > max_price:
        return {
            "valid": False,
            "reason": "price_out_of_range",
            "input_price": price,
            "aligned_price": aligned_price,
            "tick_size": tick_size,
            "min_price": min_price,
            "max_price": max_price,
        }

    return {
        "valid": price == aligned_price,
        "reason": "ok" if price == aligned_price else "price_not_aligned_to_tick_size",
        "input_price": price,
        "aligned_price": aligned_price,
        "tick_size": tick_size,
        "min_price": min_price,
        "max_price": max_price,
    }


def validate_quantity(qty: float, lot_size_filter: dict) -> dict:
    step_size = lot_size_filter.get("step_size")
    min_qty = float(lot_size_filter.get("min_qty", 0))
    max_qty = float(lot_size_filter.get("max_qty", 0))

    if not step_size:
        return {
            "valid": False,
            "reason": "missing_step_size",
        }

    aligned_qty = _floor_to_step(qty, step_size)

    if qty < min_qty or qty > max_qty:
        return {
            "valid": False,
            "reason": "qty_out_of_range",
            "input_qty": qty,
            "aligned_qty": aligned_qty,
            "step_size": step_size,
            "min_qty": min_qty,
            "max_qty": max_qty,
        }

    return {
        "valid": qty == aligned_qty,
        "reason": "ok" if qty == aligned_qty else "qty_not_aligned_to_step_size",
        "input_qty": qty,
        "aligned_qty": aligned_qty,
        "step_size": step_size,
        "min_qty": min_qty,
        "max_qty": max_qty,
    }


def prepare_partial_exit_quantity(entry_qty: float, qty_ratio: float, lot_size_filter: dict) -> dict:
    raw_qty = entry_qty * qty_ratio
    quantity_result = validate_quantity(raw_qty, lot_size_filter)
    aligned_qty = float(quantity_result.get("aligned_qty", 0.0) or 0.0)
    min_qty = float(lot_size_filter.get("min_qty", 0) or 0)

    return {
        "raw_qty": raw_qty,
        "adjusted_qty": aligned_qty,
        "valid": aligned_qty >= min_qty and aligned_qty > 0,
        "reason": "ok" if aligned_qty >= min_qty and aligned_qty > 0 else "partial_qty_below_min_qty",
        "min_qty": min_qty,
    }


def validate_notional(price: float, qty: float, notional_filter: dict) -> dict:
    notional = price * qty

    min_notional = float(notional_filter.get("min_notional", 0))
    max_notional_raw = notional_filter.get("max_notional")
    max_notional = float(max_notional_raw) if max_notional_raw not in (None, "", 0) else 0.0

    if min_notional and notional < min_notional:
        return {
            "valid": False,
            "reason": "below_min_notional",
            "notional": notional,
            "min_notional": min_notional,
            "max_notional": max_notional,
        }

    if max_notional and notional > max_notional:
        return {
            "valid": False,
            "reason": "above_max_notional",
            "notional": notional,
            "min_notional": min_notional,
            "max_notional": max_notional,
        }

    return {
        "valid": True,
        "reason": "ok",
        "notional": notional,
        "min_notional": min_notional,
        "max_notional": max_notional,
    }


def validate_order(price: float, qty: float, filters: dict) -> dict:
    price_result = validate_price(price, filters.get("price_filter", {}))
    quantity_result = validate_quantity(qty, filters.get("lot_size_filter", {}))
    notional_result = validate_notional(price, qty, filters.get("notional_filter", {}))

    all_valid = (
        price_result.get("valid", False)
        and quantity_result.get("valid", False)
        and notional_result.get("valid", False)
    )

    return {
        "price_check": price_result,
        "quantity_check": quantity_result,
        "notional_check": notional_result,
        "all_valid": all_valid,
    }


def auto_adjust_order_inputs(
    price: float,
    qty: float,
    filters: dict,
    min_notional_reference_price: float | None = None,
) -> dict:
    price_filter = filters.get("price_filter", {})
    lot_size_filter = filters.get("lot_size_filter", {})
    notional_filter = filters.get("notional_filter", {})

    tick_size = price_filter.get("tick_size")
    step_size = lot_size_filter.get("step_size")

    min_qty = float(lot_size_filter.get("min_qty", 0))
    max_qty = float(lot_size_filter.get("max_qty", 0))

    min_notional = float(notional_filter.get("min_notional", 0))

    adjusted_price = price
    adjusted_qty = qty

    if tick_size:
        adjusted_price = _floor_to_step(adjusted_price, tick_size)

    if step_size:
        adjusted_qty = _floor_to_step(adjusted_qty, step_size)

    if adjusted_qty < min_qty:
        adjusted_qty = min_qty

    if min_notional and adjusted_price > 0:
        current_notional = adjusted_price * adjusted_qty

        if current_notional < min_notional:
            required_qty = min_notional / adjusted_price

            if step_size:
                adjusted_qty = _ceil_to_step(required_qty, step_size)
            else:
                adjusted_qty = required_qty

    if min_notional and min_notional_reference_price is not None and min_notional_reference_price > 0:
        reference_notional = float(min_notional_reference_price) * adjusted_qty

        if reference_notional < min_notional:
            required_qty = min_notional / float(min_notional_reference_price)

            if step_size:
                adjusted_qty = _ceil_to_step(required_qty, step_size)
            else:
                adjusted_qty = required_qty

    if adjusted_qty < min_qty:
        adjusted_qty = min_qty

    capped_by_max_qty = False
    if max_qty and adjusted_qty > max_qty:
        adjusted_qty = max_qty
        capped_by_max_qty = True

    final_validation = validate_order(
        adjusted_price,
        adjusted_qty,
        filters,
    )

    return {
        "input_price": price,
        "input_qty": qty,
        "min_notional_reference_price": min_notional_reference_price,
        "adjusted_price": adjusted_price,
        "adjusted_qty": adjusted_qty,
        "capped_by_max_qty": capped_by_max_qty,
        "final_validation": final_validation,
    }
