"""Pure rules for disciplinary penalties (no Frappe imports, unit-testable).

The steps follow the shape of the MHRSD model work regulations: the penalty grows with
each repeat of the same violation within 180 days. Companies must apply the schedule in
their own approved regulations; the seeded schedule is a starting point for HR to review.
"""
from __future__ import annotations

from datetime import date, timedelta

REPEAT_WINDOW_DAYS = 180
MONTHLY_CAP_DAYS = 5          # total wage deductions + unpaid suspension per month
PER_VIOLATION_CAP_DAYS = 5    # a single violation never costs more than 5 days' wage
DISCOVERY_LIMIT_DAYS = 30     # no penalty for a violation discovered more than 30 days earlier
OBJECTION_DAYS = 15           # the employee may object within 15 days of being notified
ACTIONS = ("Warning", "Deduction", "Suspension", "Termination")


def occurrence(previous_dates: list[date], on: date) -> int:
    """1 for a first violation; counts earlier ones of the same type within the window."""
    start = on - timedelta(days=REPEAT_WINDOW_DAYS)
    return 1 + sum(1 for d in previous_dates if start <= d < on)


def step_for(steps: list[dict], occ: int) -> dict:
    if not steps:
        return {"action": "Warning"}
    s = dict(steps[min(occ, len(steps)) - 1])
    if s.get("action") not in ACTIONS:
        raise ValueError(f"Unknown penalty action: {s.get('action')}")
    return s


def penalty_days(step: dict) -> float:
    """Days of wage the step costs (percent of one day's wage, or whole days)."""
    if step.get("action") not in ("Deduction", "Suspension"):
        return 0.0
    days = float(step.get("days") or 0) + float(step.get("percent") or 0) / 100.0
    return min(days, PER_VIOLATION_CAP_DAYS)


def capped(days: float, already_this_month: float) -> tuple[float, bool]:
    room = max(0.0, MONTHLY_CAP_DAYS - already_this_month)
    return (min(days, room), days > room)


def daily_wage(monthly: float) -> float:
    return round(monthly / 30.0, 2)


def late_matches(minutes: int, lo: int | None, hi: int | None) -> bool:
    return minutes > 0 and minutes >= (lo or 1) and (not hi or minutes <= hi)
