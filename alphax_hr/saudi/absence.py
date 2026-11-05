"""Article 80 (Saudi Labor Law): dismissal without the end-of-service award for absence without a valid reason —
more than 30 days in one contract year or more than 15 consecutive days — only if the employer gave a written
warning after 20 days (contract year) or 10 consecutive days.

Pure functions over the attendance register's day codes, so they can be tested without a site.
"""
from __future__ import annotations

from datetime import date

ABSENT = "A"
NOT_MARKED = "?"
BRIDGE = {"H", ""}  # holidays / weekly offs (and days not yet worked) do not break a run of absences

CONSECUTIVE_WARNING, CONSECUTIVE_LIMIT = 10, 15
YEAR_WARNING, YEAR_LIMIT = 20, 30


def contract_year_start(joining: date | None, today: date) -> date:
    """Start of the current contract year (the last anniversary of the joining date)."""
    if not joining:
        return date(today.year, 1, 1)
    def anniversary(year):
        try:
            return joining.replace(year=year)
        except ValueError:  # 29 February
            return date(year, 2, 28)
    start = anniversary(today.year)
    return start if start <= today else anniversary(today.year - 1)


def absent(code: str, counts_unmarked: bool) -> bool:
    return code == ABSENT or (counts_unmarked and code == NOT_MARKED)


def evaluate(days, year_start: date, counts_unmarked: bool = False) -> dict:
    """``days``: [(date, code)] in date order up to yesterday. Returns the current run of consecutive absences
    (holidays inside a run do not break it), its first day, and the absences in this contract year."""
    run, run_from, last = 0, None, None
    for d, code in days:
        if absent(code, counts_unmarked):
            if run == 0:
                run_from = d
            run += 1
            last = d
        elif code in BRIDGE:
            continue
        else:
            run, run_from = 0, None
    total = sum(1 for d, code in days if d >= year_start and absent(code, counts_unmarked))
    return {"consecutive": run, "consecutive_from": run_from, "year_total": total, "last_absent": last, "year_start": year_start}


def stage(stats: dict) -> list[str]:
    """What is due: "consecutive_warning", "year_warning", "consecutive_limit", "year_limit"."""
    out = []
    if stats["consecutive"] >= CONSECUTIVE_WARNING:
        out.append("consecutive_warning")
    if stats["year_total"] >= YEAR_WARNING:
        out.append("year_warning")
    if stats["consecutive"] > CONSECUTIVE_LIMIT:
        out.append("consecutive_limit")
    if stats["year_total"] > YEAR_LIMIT:
        out.append("year_limit")
    return out
