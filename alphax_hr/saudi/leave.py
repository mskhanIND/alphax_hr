"""Statutory leave rules.

* Annual leave (Art. 109): 21 days a year, 30 days once the employee has
  completed five years of continuous service.
* Sick leave (Art. 117): within one year counted from the first sick day,
  the first 30 days are on full pay, the next 60 days on 75% pay and the
  following 30 days unpaid.
"""
from __future__ import annotations

from datetime import date

from alphax_hr.saudi.service import full_years

ANNUAL_BASE_DAYS = 21
ANNUAL_SENIOR_DAYS = 30
SENIOR_AFTER_YEARS = 5

SICK_TIERS = ((30, 1.0), (60, 0.75), (30, 0.0))  # (days, pay factor)


def annual_entitlement(joining: date, on: date) -> int:
    """Yearly annual-leave entitlement applicable on ``on``."""
    return ANNUAL_SENIOR_DAYS if full_years(joining, on) >= SENIOR_AFTER_YEARS else ANNUAL_BASE_DAYS


def annual_accrual(joining: date, start: date, end: date) -> float:
    """Days accrued between ``start`` and ``end`` (inclusive), switching to the
    senior rate on the fifth anniversary when it falls inside the window."""
    if end < start:
        return 0.0
    start = max(start, joining)
    if end < start:
        return 0.0
    fifth = _anniversary(joining, SENIOR_AFTER_YEARS)
    total = 0.0
    if start < fifth:
        seg_end = min(end, date.fromordinal(fifth.toordinal() - 1))
        total += ((seg_end - start).days + 1) * ANNUAL_BASE_DAYS / 365.0
    if end >= fifth:
        seg_start = max(start, fifth)
        total += ((end - seg_start).days + 1) * ANNUAL_SENIOR_DAYS / 365.0
    return round(total, 2)


def _anniversary(d: date, years: int) -> date:
    try:
        return d.replace(year=d.year + years)
    except ValueError:  # 29 Feb
        return d.replace(year=d.year + years, day=28)


def sick_leave_split(days_already_taken: float, requested_days: float) -> list[dict]:
    """Split a sick-leave request across the pay tiers.

    ``days_already_taken`` is sick leave already used in the current
    sick-leave year. Days beyond the 120-day statutory window are reported
    with ``tier = 'exceeds_statutory'``.
    """
    remaining = float(requested_days)
    used = float(days_already_taken)
    parts: list[dict] = []
    cursor = 0.0
    for idx, (size, factor) in enumerate(SICK_TIERS, start=1):
        tier_start, tier_end = cursor, cursor + size
        cursor = tier_end
        if used >= tier_end or remaining <= 0:
            continue
        available = tier_end - max(used, tier_start)
        take = min(available, remaining)
        parts.append({"tier": idx, "days": take, "pay_factor": factor})
        remaining -= take
        used += take
    if remaining > 0:
        parts.append({"tier": "exceeds_statutory", "days": remaining, "pay_factor": 0.0})
    return parts
