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


def service_period(joining: date, on: date) -> tuple[int, date, date]:
    """The service year containing ``on``: (year_index, start, end) with ``end`` inclusive.

    Periods run from each anniversary of the joining date (Art. 109 grants
    leave per year of service, not per calendar year).
    """
    if on < joining:
        raise ValueError("Date is before the joining date")
    k = full_years_between(joining, on)
    start = _anniversary(joining, k)
    end = date.fromordinal(_anniversary(joining, k + 1).toordinal() - 1)
    return k, start, end


def full_years_between(joining: date, on: date) -> int:
    from alphax_hr.saudi.service import full_years

    return full_years(joining, on)


def entitlement_for_service_year(year_index: int, base: int = ANNUAL_BASE_DAYS, senior: int = ANNUAL_SENIOR_DAYS,
                                 senior_after: int = SENIOR_AFTER_YEARS) -> int:
    """Days granted for service year ``year_index`` (0 = first year)."""
    return senior if year_index >= senior_after else base


POLICY_LAW = "Saudi Labor Law"
POLICY_FIXED = "Fixed for all employees"


def annual_days(year_index: int, policy: str = POLICY_LAW, fixed_days: int | None = None,
                contract_days: int | None = None, base: int = ANNUAL_BASE_DAYS, senior: int = ANNUAL_SENIOR_DAYS,
                senior_after: int = SENIOR_AFTER_YEARS) -> tuple[int, str]:
    """Annual leave days for one service year and where the number came from.

    Order: the employee's contract, else the company policy. Art. 109's minimum
    (21 days, 30 from the 6th year) always applies, so a contract or policy can
    give more than the law but never less.
    """
    legal_min = entitlement_for_service_year(year_index, ANNUAL_BASE_DAYS, ANNUAL_SENIOR_DAYS, SENIOR_AFTER_YEARS)
    if contract_days:
        days, source = int(contract_days), "contract"
    elif policy == POLICY_FIXED and fixed_days:
        days, source = int(fixed_days), "company"
    else:
        days, source = entitlement_for_service_year(year_index, base, senior, senior_after), "law"
    if days < legal_min:
        return legal_min, "legal_minimum"
    return days, source


def describe_sick_split(parts: list[dict]) -> str:
    labels = {1.0: "full pay", 0.75: "75% pay", 0.0: "unpaid"}
    out = []
    for p in parts:
        if p["tier"] == "exceeds_statutory":
            out.append(f"{p['days']:g} day(s) beyond the 120-day statutory limit")
        else:
            out.append(f"{p['days']:g} day(s) {labels.get(p['pay_factor'], str(p['pay_factor']))}")
    return " · ".join(out)


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
