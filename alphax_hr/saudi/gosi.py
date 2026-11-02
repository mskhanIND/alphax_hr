"""GOSI (social insurance) contribution engine.

Three contribution systems exist side by side:

* ``Legacy``    – Saudis whose first GOSI registration was before 3 Jul 2024.
* ``New``       – Saudis first registered on/after 3 Jul 2024 (Royal Decree
                  M/273). The pension branch steps up 0.5% per side every July
                  from 2025 until it reaches 11% in 2028.
* ``Non-Saudi`` – expatriates: employer pays occupational hazards only.

The system is decided by the *GOSI registration date*, never the hire date:
an experienced Saudi who changes employer stays on the legacy system.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

NEW_SYSTEM_START = date(2024, 7, 3)
DEFAULT_WAGE_CAP = Decimal("45000")
DEFAULT_WAGE_FLOOR = Decimal("0")  # set per site if GOSI enforces a minimum

LEGACY, NEW, NON_SAUDI, UNCLASSIFIED = "Legacy", "New", "Non-Saudi", "Unclassified"


@dataclass(frozen=True)
class RateRow:
    """One effective-dated rate row (percentages, per side)."""

    system: str
    effective_from: date
    employee_pension: Decimal
    employer_pension: Decimal
    employee_saned: Decimal
    employer_saned: Decimal
    employer_hazard: Decimal

    @property
    def employee_total(self) -> Decimal:
        return self.employee_pension + self.employee_saned

    @property
    def employer_total(self) -> Decimal:
        return self.employer_pension + self.employer_saned + self.employer_hazard


def _r(system, y, m, d, ep, rp, es="0.75", rs="0.75", hz="2"):
    D = Decimal
    return RateRow(system, date(y, m, d), D(ep), D(rp), D(es), D(rs), D(hz))


# Statutory defaults. Sites seed these into "GOSI Contribution Rate" records
# and may edit/extend them when GOSI publishes changes.
DEFAULT_RATES: tuple[RateRow, ...] = (
    _r(LEGACY, 2014, 1, 1, "9", "9"),
    _r(NEW, 2024, 7, 3, "9", "9"),
    _r(NEW, 2025, 7, 1, "9.5", "9.5"),
    _r(NEW, 2026, 7, 1, "10", "10"),
    _r(NEW, 2027, 7, 1, "10.5", "10.5"),
    _r(NEW, 2028, 7, 1, "11", "11"),
    _r(NON_SAUDI, 2014, 1, 1, "0", "0", "0", "0", "2"),
)


def classify(is_saudi: bool, gosi_registration_date: date | None) -> str:
    """Return the contribution system for an employee.

    Saudis without a known first-registration date are ``Unclassified`` —
    we flag them instead of guessing from the hire date.
    """
    if not is_saudi:
        return NON_SAUDI
    if gosi_registration_date is None:
        return UNCLASSIFIED
    return NEW if gosi_registration_date >= NEW_SYSTEM_START else LEGACY


def rate_for(system: str, on: date, rates=DEFAULT_RATES) -> RateRow:
    """Latest rate row of ``system`` effective on ``on``."""
    candidates = [r for r in rates if r.system == system and r.effective_from <= on]
    if not candidates:
        raise ValueError(f"No GOSI rate for system {system!r} on {on.isoformat()}")
    return max(candidates, key=lambda r: r.effective_from)


def contributory_wage(basic, housing, cap=DEFAULT_WAGE_CAP, floor=DEFAULT_WAGE_FLOOR) -> Decimal:
    """Basic + housing allowance, clamped to the GOSI floor/cap."""
    wage = Decimal(str(basic or 0)) + Decimal(str(housing or 0))
    if wage <= 0:
        return Decimal("0")
    return min(max(wage, Decimal(str(floor))), Decimal(str(cap)))


def _money(v: Decimal) -> Decimal:
    return v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@dataclass
class Contribution:
    system: str
    period_date: date
    wage: Decimal
    employee_rate: Decimal = Decimal("0")
    employer_rate: Decimal = Decimal("0")
    employee_amount: Decimal = Decimal("0")
    employer_amount: Decimal = Decimal("0")
    warnings: list[str] = field(default_factory=list)

    @property
    def total(self) -> Decimal:
        return self.employee_amount + self.employer_amount

    def as_dict(self) -> dict:
        return {
            "system": self.system,
            "period_date": self.period_date.isoformat(),
            "wage": float(self.wage),
            "employee_rate": float(self.employee_rate),
            "employer_rate": float(self.employer_rate),
            "employee_amount": float(self.employee_amount),
            "employer_amount": float(self.employer_amount),
            "total": float(self.total),
            "warnings": list(self.warnings),
        }


def calculate(
    *,
    is_saudi: bool,
    gosi_registration_date: date | None,
    basic,
    housing,
    period_date: date,
    rates=DEFAULT_RATES,
    cap=DEFAULT_WAGE_CAP,
    floor=DEFAULT_WAGE_FLOOR,
) -> Contribution:
    """Monthly GOSI contribution for one employee for the period containing ``period_date``."""
    system = classify(is_saudi, gosi_registration_date)
    wage = contributory_wage(basic, housing, cap, floor)
    result = Contribution(system=system, period_date=period_date, wage=wage)
    if system == UNCLASSIFIED:
        result.warnings.append("gosi_registration_date_missing")
        return result
    if wage == 0:
        result.warnings.append("no_contributory_wage")
    raw = Decimal(str(basic or 0)) + Decimal(str(housing or 0))
    if raw > Decimal(str(cap)):
        result.warnings.append("wage_capped")
    row = rate_for(system, period_date, rates)
    result.employee_rate = row.employee_total
    result.employer_rate = row.employer_total
    result.employee_amount = _money(wage * row.employee_total / 100)
    result.employer_amount = _money(wage * row.employer_total / 100)
    return result
