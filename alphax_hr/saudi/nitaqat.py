"""Saudization (Nitaqat) ratio estimate.

This is an internal *estimate* for HR monitoring, not the official Qiwa
figure. Weighting rules are configurable because MHRSD adjusts them:

* a Saudi earning at least ``full_count_wage`` counts as 1,
* a Saudi earning less counts as ``partial_weight`` (default 0.5),
* non-Saudis count as 1 in the denominator.
"""
from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class NitaqatPolicy:
    full_count_wage: float = 4000.0
    partial_weight: float = 0.5
    target_percent: float | None = None


def ratio(employees, policy: NitaqatPolicy = NitaqatPolicy()) -> dict:
    """``employees`` is an iterable of ``{"is_saudi": bool, "wage": number}``."""
    saudi_weight = 0.0
    saudi_head = 0
    partial = 0
    total = 0
    for row in employees:
        total += 1
        if row.get("is_saudi"):
            saudi_head += 1
            if float(row.get("wage") or 0) >= policy.full_count_wage:
                saudi_weight += 1
            else:
                saudi_weight += policy.partial_weight
                partial += 1
    non_saudi = total - saudi_head
    denominator = saudi_weight + non_saudi
    percent = round(100 * saudi_weight / denominator, 2) if denominator else 0.0
    result = {
        "total_employees": total,
        "saudi_headcount": saudi_head,
        "non_saudi_headcount": non_saudi,
        "saudi_weighted": round(saudi_weight, 2),
        "saudis_counted_partially": partial,
        "saudization_percent": percent,
        "target_percent": policy.target_percent,
        "saudis_needed_for_target": None,
    }
    if policy.target_percent is not None and percent < policy.target_percent:
        t = policy.target_percent / 100
        # Each added full-wage Saudi adds 1 to numerator and denominator.
        needed = (t * denominator - saudi_weight) / (1 - t) if t < 1 else math.inf
        result["saudis_needed_for_target"] = max(0, math.ceil(needed - 1e-9))
    elif policy.target_percent is not None:
        result["saudis_needed_for_target"] = 0
    return result
