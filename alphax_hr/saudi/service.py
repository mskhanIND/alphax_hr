"""Service-length helpers shared by leave and end-of-service rules."""
from __future__ import annotations

from datetime import date


def service_years(joining: date, until: date) -> float:
    """Service in years (days / 365), inclusive of the last day."""
    if until < joining:
        return 0.0
    return ((until - joining).days + 1) / 365.0


def full_years(joining: date, until: date) -> int:
    """Completed anniversary years between ``joining`` and ``until``."""
    if until < joining:
        return 0
    years = until.year - joining.year
    if (until.month, until.day) < (joining.month, joining.day):
        years -= 1
    return max(years, 0)
