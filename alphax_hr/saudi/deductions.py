"""Saudi Labor Law limits on wage deductions (no Frappe imports).

- Art. 92(1): an employer loan may be recovered from the wage at no more than 10% of the wage per month
  (without the worker's written consent).
- Art. 91: damage/loss caused by the worker - at most five days' wage per month.
- Art. 70 (via the work regulation): a fine for one violation at most five days' wage; fines in one month at most
  five days' wage (handled by the penalties module).
- Art. 92: any other deduction for private rights needs the worker's written consent.
- Art. 93: in all cases the total deducted in a month may not exceed half of the wage due, unless the labour court
  allows more.
"Wage" is the actual wage (basic + allowances, Art. 2); a day's wage is the monthly wage / 30.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

LOAN_PCT = 0.10
TOTAL_PCT = 0.50
COURT_PCT = 0.25
DAMAGE_DAYS = 5
FINE_DAYS = 5
DAYS_IN_MONTH = 30

LOAN, ADVANCE, DAMAGE, FINE, CONSENT, COURT, STATUTORY = "loan", "advance", "damage", "fine", "consent", "court", "statutory"
LABELS = {LOAN: "Loan installment (Art. 92/1)", ADVANCE: "Salary advance recovery", DAMAGE: "Damage / loss (Art. 91)",
		  FINE: "Penalty (Art. 70)", CONSENT: "Deduction with written consent (Art. 92)", COURT: "Court order (Art. 92)",
		  STATUTORY: "GOSI and other statutory contributions"}


def day_wage(monthly: float) -> float:
	return round(monthly / DAYS_IN_MONTH, 2)


def loan_cap(monthly: float) -> float:
	return round(monthly * LOAN_PCT, 2)


def damage_cap(monthly: float) -> float:
	return round(day_wage(monthly) * DAMAGE_DAYS, 2)


def total_cap(monthly: float) -> float:
	return round(monthly * TOTAL_PCT, 2)


def add_months(d: date, n: int) -> date:
	m = d.month - 1 + n
	return date(d.year + m // 12, m % 12 + 1, 1)


def plan_installments(amount: float, months: int, first_month: date) -> list[dict]:
	"""Equal monthly installments; the last one absorbs the rounding."""
	if amount <= 0 or months < 1:
		raise ValueError("amount and months must be positive")
	each = round(amount / months, 2)
	rows = []
	for i in range(months):
		value = each if i < months - 1 else round(amount - each * (months - 1), 2)
		rows.append({"due_month": add_months(date(first_month.year, first_month.month, 1), i), "amount": value})
	return rows


def min_months_for_cap(amount: float, monthly: float) -> int:
	cap = loan_cap(monthly)
	if cap <= 0:
		return 0
	n = int(amount // cap)
	return n + (1 if amount - n * cap > 0.005 else 0)


def split_by_cap(amount: float, cap: float) -> list[float]:
	"""Spread an amount over months so no month exceeds ``cap`` (used for damage, Art. 91)."""
	if cap <= 0:
		return [round(amount, 2)]
	out, left = [], round(amount, 2)
	while left > 0.005:
		take = round(min(cap, left), 2)
		out.append(take)
		left = round(left - take, 2)
	return out


@dataclass
class MonthCheck:
	wage: float
	total: float = 0.0
	by_kind: dict = field(default_factory=dict)
	problems: list = field(default_factory=list)  # (code, params)

	@property
	def ok(self):
		return not self.problems

	@property
	def room(self):
		return round(max(0.0, total_cap(self.wage) - self.total), 2)


def check_month(wage: float, items: list[tuple[str, float]], consent_for_loans: bool = False,
				include_statutory: bool = True) -> MonthCheck:
	"""Check one employee's deductions for one month against Art. 91/92/93."""
	res = MonthCheck(wage=wage)
	for kind, amount in items:
		res.by_kind[kind] = round(res.by_kind.get(kind, 0.0) + amount, 2)
	res.total = round(sum(v for k, v in res.by_kind.items() if include_statutory or k != STATUTORY), 2)
	if wage <= 0:
		if res.total > 0:
			res.problems.append(("no_wage", {}))
		return res
	if res.by_kind.get(LOAN, 0) > loan_cap(wage) + 0.005 and not consent_for_loans:
		res.problems.append(("loan_over_10", {"amount": res.by_kind[LOAN], "cap": loan_cap(wage)}))
	if res.by_kind.get(DAMAGE, 0) > damage_cap(wage) + 0.005:
		res.problems.append(("damage_over_5_days", {"amount": res.by_kind[DAMAGE], "cap": damage_cap(wage)}))
	if res.by_kind.get(FINE, 0) > day_wage(wage) * FINE_DAYS + 0.005:
		res.problems.append(("fines_over_5_days", {"amount": res.by_kind[FINE], "cap": round(day_wage(wage) * FINE_DAYS, 2)}))
	if res.by_kind.get(COURT, 0) > round(wage * COURT_PCT, 2) + 0.005:
		res.problems.append(("court_over_quarter", {"amount": res.by_kind[COURT], "cap": round(wage * COURT_PCT, 2)}))
	if res.total > total_cap(wage) + 0.005:
		res.problems.append(("over_half_wage", {"amount": res.total, "cap": total_cap(wage)}))
	return res
