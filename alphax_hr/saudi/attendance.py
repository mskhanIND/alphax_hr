"""Attendance rules: lateness, early exit, worked hours and overtime (Saudi Labor Law).

Pure functions so they are easy to test. Times are naive datetimes in the
site's time zone (Asia/Riyadh).

Overtime (Art. 107): each extra hour is paid the hourly wage plus 50% of the
hourly *basic* wage. The hourly wage is the monthly wage / 30 / daily hours
(8 normally; 6 for Muslim employees in Ramadan, Art. 98).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

DAYS_PER_MONTH = 30
DEFAULT_DAILY_HOURS = 8.0

# Day codes used by the register (one letter per cell, explained in the UI legend).
PRESENT, ABSENT, LEAVE, HALF_DAY, WFH, HOLIDAY, MISSING_PUNCH, NOT_MARKED, FUTURE = "P", "A", "L", "HD", "W", "H", "M", "?", ""


def shift_window(day: date, start: time, end: time) -> tuple[datetime, datetime]:
    """Shift start and end on ``day``; a shift ending before it starts runs past midnight."""
    s = datetime.combine(day, start)
    e = datetime.combine(day, end)
    if e <= s:
        e += timedelta(days=1)
    return s, e


def late_minutes(shift_start: datetime, first_in: datetime | None, grace: int = 0) -> int:
    """Minutes late beyond the grace period (0 if on time or no check-in)."""
    if not first_in:
        return 0
    late = (first_in - shift_start).total_seconds() / 60
    return int(late) if late > grace else 0


def early_minutes(shift_end: datetime, last_out: datetime | None, grace: int = 0) -> int:
    if not last_out:
        return 0
    early = (shift_end - last_out).total_seconds() / 60
    return int(early) if early > grace else 0


@dataclass
class DayLogs:
    first_in: datetime | None = None
    last_out: datetime | None = None
    hours: float = 0.0
    missing_punch: bool = False
    pairs: list = field(default_factory=list)


def pair_logs(logs: list[tuple[datetime, str]]) -> DayLogs:
    """Pair IN/OUT logs in time order. A lone IN (no OUT after it) is a missing punch.

    Repeated INs keep the first; repeated OUTs keep the last, which matches how
    people double-tap devices.
    """
    out = DayLogs()
    open_in: datetime | None = None
    for t, kind in sorted(logs):
        if kind == "IN":
            if out.first_in is None:
                out.first_in = t
            if open_in is None:
                open_in = t
        elif kind == "OUT":
            if open_in is not None:
                out.pairs.append((open_in, t))
                open_in = None
            elif out.pairs:  # second OUT: extend the last pair
                start, _ = out.pairs[-1]
                out.pairs[-1] = (start, t)
            out.last_out = t
    if open_in is not None:
        out.missing_punch = True
    out.hours = round(sum((b - a).total_seconds() for a, b in out.pairs) / 3600, 2)
    return out


def overtime_hours(worked: float, shift_hours: float, minimum_minutes: int = 30) -> float:
    """Hours beyond the shift, ignoring small overruns (default under 30 minutes)."""
    extra = worked - shift_hours
    if extra * 60 < minimum_minutes:
        return 0.0
    return round(extra, 2)


def overtime_pay(hours: float, monthly_wage: float, monthly_basic: float,
                 daily_hours: float = DEFAULT_DAILY_HOURS) -> float:
    """Art. 107: hourly wage + 50% of the hourly basic wage, per overtime hour."""
    if hours <= 0 or daily_hours <= 0:
        return 0.0
    hourly = monthly_wage / DAYS_PER_MONTH / daily_hours
    hourly_basic = monthly_basic / DAYS_PER_MONTH / daily_hours
    return round(hours * (hourly + 0.5 * hourly_basic), 2)


def day_code(*, day: date, today: date, holiday: bool, attendance_status: str | None, on_leave: bool,
             logs: DayLogs | None) -> str:
    """One code per employee per day for the register."""
    if attendance_status:
        return {"Present": PRESENT, "Absent": ABSENT, "On Leave": LEAVE, "Half Day": HALF_DAY,
                "Work From Home": WFH}.get(attendance_status, PRESENT)
    if on_leave:
        return LEAVE
    if holiday:
        return HOLIDAY
    if day > today:
        return FUTURE
    if logs and logs.missing_punch:
        return MISSING_PUNCH
    if logs and logs.pairs:
        return PRESENT
    if day == today:
        return NOT_MARKED
    return ABSENT
