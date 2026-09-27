"""Transparent deterministic scenarios, not causal predictions or probabilistic service guarantees."""
import math


def capacity_plan(rows, capacity, multiplier=1.0):
    result = []
    for row in rows:
        expected = row["prediction"] * multiplier
        high = row["upper"] * multiplier
        result.append({"date": row["date"], "expected": expected, "upper_scenario": high,
                       "capacity": capacity, "overflow": max(0, expected-capacity),
                       "headroom": capacity-expected})
    return {"days": result, "total_expected": sum(r["expected"] for r in result),
            "overloaded_days": sum(r["overflow"] > 0 for r in result),
            "total_overflow": sum(r["overflow"] for r in result),
            "peak_expected": max(r["expected"] for r in result),
            "extra_daily_capacity": max(0, max(r["expected"] for r in result)-capacity),
            "note": "Independent daily capacity; unused capacity does not carry over. Demand scaling is an assumption, not a learned intervention effect. Upper bounds are per-day scenarios, not joint probabilities."}


def inventory_plan(rows, on_hand, on_order, lead_days, review_days, safety_stock, multiplier=1.0):
    window = lead_days + review_days
    if window > len(rows):
        raise ValueError("Lead time plus review period must fit within the forecast horizon.")
    protection_demand = sum(r["prediction"] for r in rows[:window]) * multiplier
    lead_demand = sum(r["prediction"] for r in rows[:lead_days]) * multiplier
    target = protection_demand + safety_stock
    position = on_hand + on_order
    return {"protection_days": window, "expected_protection_demand": protection_demand,
            "target_stock": target, "inventory_position": position,
            "recommended_order": math.ceil(max(0, target-position)),
            "potential_shortfall_before_delivery": max(0, lead_demand-on_hand),
            "note": "Periodic order-up-to scenario. Assumes existing orders arrive within the protection window, no backorders, no minimum order quantities, and fixed lead time. Safety stock is user-specified, not a calibrated service level."}
