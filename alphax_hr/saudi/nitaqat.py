"""Saudization (Nitaqat) ratio estimate.

This is an internal *estimate* for HR monitoring, not the official Qiwa
figure. Weighting rules are configurable because MHRSD adjusts them:

* a Saudi earning at least ``full_count_wage`` counts as 1,
* a Saudi earning at least ``min_count_wage`` (SAR 3,000) but less counts as ``partial_weight`` (0.5),
* a Saudi earning less than ``min_count_wage`` does not count,
* non-Saudis count as 1 in the denominator.

The wage needed to count fully follows the official schedule (royal directive of 25 Oct 2026): SAR 4,000, then
SAR 5,000 from 25 Apr 2027 and SAR 6,000 from 25 Apr 2028. It is the wage at which a Saudi counts fully in the
Saudization ratio, not a minimum wage.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date

FULL_COUNT_SCHEDULE = ((date(2000, 1, 1), 4000.0), (date(2027, 4, 25), 5000.0), (date(2028, 4, 25), 6000.0))
MIN_COUNT_WAGE = 3000.0


def full_count_wage_on(day: date, schedule=FULL_COUNT_SCHEDULE) -> float:
    """The wage at which a Saudi counts fully on ``day``."""
    wage = schedule[0][1]
    for start, value in schedule:
        if day >= start:
            wage = value
    return wage


def upcoming(day: date, schedule=FULL_COUNT_SCHEDULE):
    """Threshold changes after ``day``: [(date, wage)]."""
    return [(d, w) for d, w in schedule if d > day]


@dataclass(frozen=True)
class NitaqatPolicy:
    full_count_wage: float = 4000.0
    partial_weight: float = 0.5
    target_percent: float | None = None
    min_count_wage: float = MIN_COUNT_WAGE


def weight(wage: float, policy: NitaqatPolicy) -> float:
    if wage >= policy.full_count_wage:
        return 1.0
    if wage >= policy.min_count_wage:
        return policy.partial_weight
    return 0.0


def ratio(employees, policy: NitaqatPolicy = NitaqatPolicy()) -> dict:
    """``employees`` is an iterable of ``{"is_saudi": bool, "wage": number}``."""
    saudi_weight = 0.0
    saudi_head = 0
    partial = 0
    not_counted = 0
    total = 0
    for row in employees:
        total += 1
        if row.get("is_saudi"):
            saudi_head += 1
            w = weight(float(row.get("wage") or 0), policy)
            saudi_weight += w
            if w == 0:
                not_counted += 1
            elif w < 1:
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
        "saudis_not_counted": not_counted,
        "full_count_wage": policy.full_count_wage,
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


def forecast(employees, policy: NitaqatPolicy, changes):
    """For each threshold change: the Saudis who stop counting fully, the monthly raise needed to keep them, and the
    ratio afterwards if nothing changes. ``employees`` rows need ``is_saudi``, ``wage`` and may carry ``name``."""
    rows = list(employees)
    out = []
    for when, wage in changes:
        p = NitaqatPolicy(full_count_wage=wage, partial_weight=policy.partial_weight, target_percent=policy.target_percent,
                          min_count_wage=policy.min_count_wage)
        affected = [r for r in rows if r.get("is_saudi") and policy.full_count_wage <= float(r.get("wage") or 0) < wage]
        below = [r for r in rows if r.get("is_saudi") and float(r.get("wage") or 0) < wage]
        out.append({"date": when.isoformat(), "full_count_wage": wage, "after": ratio(rows, p),
                    "stop_counting_fully": [{"name": r.get("name"), "employee_name": r.get("employee_name"),
                                             "wage": float(r.get("wage") or 0), "raise_needed": round(wage - float(r.get("wage") or 0), 2)}
                                            for r in affected],
                    "monthly_cost_all_below": round(sum(wage - float(r.get("wage") or 0) for r in below), 2),
                    "saudis_below": len(below)})
    return out
