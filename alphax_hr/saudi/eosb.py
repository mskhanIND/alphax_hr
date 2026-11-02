"""End-of-service benefit (Saudi Labor Law, Articles 84, 85 and 87).

* Art. 84 – half a month's wage for each of the first five years of service,
  one month's wage for each year after that; partial years are pro-rated.
* Art. 85 – on resignation the award is reduced: nothing below 2 years,
  one third for 2–5 years, two thirds for 5–10 years, full from 10 years.
* Art. 87 – full award despite resignation for force majeure, or a female
  worker leaving within 6 months of marriage / 3 months of childbirth.
* Art. 80 – termination for cause forfeits the award.

The wage basis is the *last actual wage* (basic plus regular allowances); the
caller decides which components count.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from alphax_hr.saudi.service import service_years

TERMINATION = "Termination by employer"
CONTRACT_END = "End of fixed-term contract"
RESIGNATION = "Resignation"
RESIGNATION_ART87 = "Resignation – Article 87 exception"
DISMISSAL_ART80 = "Dismissal under Article 80"

REASONS = (TERMINATION, CONTRACT_END, RESIGNATION, RESIGNATION_ART87, DISMISSAL_ART80)


@dataclass
class EOSBResult:
    reason: str
    service_years: float
    monthly_wage: Decimal
    gross_award: Decimal
    entitlement_factor: Decimal
    award: Decimal
    breakdown: list[dict]

    def as_dict(self) -> dict:
        return {
            "reason": self.reason,
            "service_years": round(self.service_years, 4),
            "monthly_wage": float(self.monthly_wage),
            "gross_award": float(self.gross_award),
            "entitlement_factor": float(self.entitlement_factor),
            "award": float(self.award),
            "breakdown": self.breakdown,
        }


def _money(v: Decimal) -> Decimal:
    return v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def resignation_factor(years: float) -> Decimal:
    if years < 2:
        return Decimal("0")
    if years < 5:
        return Decimal(1) / Decimal(3)
    if years < 10:
        return Decimal(2) / Decimal(3)
    return Decimal("1")


def calculate(joining: date, exit_date: date, monthly_wage, reason: str = TERMINATION) -> EOSBResult:
    if reason not in REASONS:
        raise ValueError(f"Unknown end-of-service reason: {reason}")
    if exit_date < joining:
        raise ValueError("Exit date is before the joining date")
    wage = Decimal(str(monthly_wage or 0))
    years = service_years(joining, exit_date)
    y = Decimal(str(years))
    first = min(y, Decimal(5))
    after = max(y - Decimal(5), Decimal(0))
    first_amount = first * wage / 2
    after_amount = after * wage
    gross = first_amount + after_amount
    breakdown = [
        {"label": "first_5_years", "years": float(round(first, 4)), "rate": 0.5, "amount": float(_money(first_amount))},
        {"label": "after_5_years", "years": float(round(after, 4)), "rate": 1.0, "amount": float(_money(after_amount))},
    ]
    if reason == DISMISSAL_ART80:
        factor = Decimal("0")
    elif reason == RESIGNATION:
        factor = resignation_factor(years)
    else:
        factor = Decimal("1")
    return EOSBResult(reason, years, wage, _money(gross), factor, _money(gross * factor), breakdown)
