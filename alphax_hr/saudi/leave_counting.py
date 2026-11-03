"""How many days a leave request costs, under the company's counting policy (no Frappe imports).

Policy per leave type:
- count_mode: "Calendar days" | "Working days only" | "Skip public holidays" | "Skip weekends"
- sandwich: "Off" | "Inside one request" | "Also across requests" (weekends between leave days count);
  sandwich_holidays: public holidays between leave days count too.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

CALENDAR, WORKING, SKIP_HOLIDAYS, SKIP_WEEKENDS = "Calendar days", "Working days only", "Skip public holidays", "Skip weekends"
SANDWICH_OFF, SANDWICH_IN, SANDWICH_ACROSS = "Off", "Inside one request", "Also across requests"


@dataclass
class Policy:
    count_mode: str = CALENDAR
    sandwich: str = SANDWICH_OFF
    sandwich_holidays: bool = False


@dataclass
class Result:
    days: float
    weekends_skipped: int = 0
    holidays_skipped: int = 0
    sandwiched: int = 0
    adjacent_days: int = 0
    notes: list = field(default_factory=list)

    def describe(self) -> str:
        parts = [f"{self.days:g} day(s)"]
        if self.weekends_skipped:
            parts.append(f"{self.weekends_skipped} weekend day(s) not counted")
        if self.holidays_skipped:
            parts.append(f"{self.holidays_skipped} public holiday(s) not counted")
        if self.sandwiched:
            parts.append(f"{self.sandwiched} day(s) between leave days counted (sandwich)")
        if self.adjacent_days:
            parts.append(f"{self.adjacent_days} off day(s) joining another leave counted (sandwich)")
        return " · ".join(parts)


def _days(a: date, b: date):
    return [a + timedelta(days=i) for i in range((b - a).days + 1)]


def _skips(policy: Policy, is_weekend: bool, is_holiday: bool) -> bool:
    if policy.count_mode == WORKING:
        return is_weekend or is_holiday
    if policy.count_mode == SKIP_HOLIDAYS:
        return is_holiday
    if policy.count_mode == SKIP_WEEKENDS:
        return is_weekend
    return False


def _sandwichable(policy: Policy, is_weekend: bool, is_holiday: bool) -> bool:
    return policy.sandwich != SANDWICH_OFF and (is_weekend or (is_holiday and policy.sandwich_holidays))


def count(start: date, end: date, weekends: set, holidays: set, policy: Policy, half_day: bool = False,
          leave_before: date | None = None, leave_after: date | None = None) -> Result:
    """Days to deduct. ``leave_before`` / ``leave_after``: the end / start of the employee's neighbouring
    leave (only used with "Also across requests") — off days joining the two leaves are counted here."""
    if end < start:
        raise ValueError("end before start")
    days = _days(start, end)
    working = [d for d in days if d not in weekends and d not in holidays]
    first_work, last_work = (working[0], working[-1]) if working else (None, None)
    res = Result(days=0)
    for d in days:
        wk, hol = d in weekends, d in holidays and d not in weekends
        if not _skips(policy, wk, hol):
            res.days += 1
            continue
        if first_work and first_work < d < last_work and _sandwichable(policy, wk, hol):
            res.days += 1
            res.sandwiched += 1
            continue
        if wk:
            res.weekends_skipped += 1
        else:
            res.holidays_skipped += 1
    if policy.sandwich == SANDWICH_ACROSS:
        for gap in (_gap(leave_before, start, weekends, holidays, policy, before=True),
                    _gap(end, leave_after, weekends, holidays, policy, before=False)):
            res.days += gap
            res.adjacent_days += gap
    if half_day:
        res.days -= 0.5
    return res


def _gap(a: date | None, b: date | None, weekends, holidays, policy, before: bool) -> int:
    """Off days strictly between two leaves, counted only if every day between them is an off day."""
    if not a or not b or b <= a:
        return 0
    between = _days(a + timedelta(days=1), b - timedelta(days=1))
    if not between:
        return 0
    for d in between:
        wk, hol = d in weekends, d in holidays and d not in weekends
        if not (wk or hol) or not _sandwichable(policy, wk, hol):
            return 0
        if not _skips(policy, wk, hol):
            return 0  # already counted as leave by the mode itself
    return len(between)
