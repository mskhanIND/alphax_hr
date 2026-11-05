"""Notice and compensation when a contract ends (Saudi Labor Law, Articles 75, 76, 77).

* Art. 75 — indefinite contract, monthly paid: 30 days' written notice from the employee, 60 days from the employer;
  not monthly paid: 30 days either way.
* Art. 76 — the party that does not give the notice pays the other the wage for the notice period not given.
* Art. 77 — ending the contract without a valid reason (unless the contract sets the compensation): indefinite
  contract 15 days' wage per year of service; fixed-term contract the wage for the rest of the term; never less than
  two months' wage.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP

INDEFINITE = "Indefinite"
FIXED = "Fixed term"
EMPLOYEE, EMPLOYER = "Employee", "Employer"


def _money(v) -> float:
    return float(Decimal(str(v)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def notice_days(contract: str, initiated_by: str, monthly_paid: bool = True) -> int:
    """Statutory notice for an indefinite contract (fixed-term contracts end on their date: 0)."""
    if contract != INDEFINITE:
        return 0
    if not monthly_paid:
        return 30
    return 60 if initiated_by == EMPLOYER else 30


def notice_shortfall(required: int, notice_given_on: date | None, exit_date: date) -> int:
    """Days of the required notice that were not given before the last working day."""
    if not required:
        return 0
    given = (exit_date - notice_given_on).days if notice_given_on else 0
    return max(0, required - max(given, 0))


def notice_pay(monthly_wage, days: int) -> float:
    return _money(Decimal(str(monthly_wage or 0)) / 30 * days)


def article77(contract: str, monthly_wage, service_years: float, remaining_days: int = 0, agreed=None) -> float:
    """Compensation for ending the contract without a valid reason."""
    if agreed:
        return _money(agreed)
    wage = Decimal(str(monthly_wage or 0))
    if contract == INDEFINITE:
        amount = wage / 30 * 15 * Decimal(str(service_years or 0))
    else:
        amount = wage / 30 * max(remaining_days, 0)
    return _money(max(amount, wage * 2))
