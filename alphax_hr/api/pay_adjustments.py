"""HR pay adjustments: bonuses and one-time payments, deductions for damage / consent / court orders,
and salary increments - single employee or in bulk, checked against the Saudi Labor Law deduction limits."""
from __future__ import annotations

import json

import frappe
from frappe import _
from frappe.utils import cint, flt, get_last_day, getdate, nowdate

from alphax_hr.api import loans
from alphax_hr.api._common import parse_json, require_hr, require_hr_manager
from alphax_hr.saudi import deductions as rules

DT = "AlphaX Pay Adjustment"
EARNINGS = ("Bonus", "One-time payment", "Allowance / arrears")
DEDUCTIONS = ("Damage or loss (Art. 91)", "Deduction with written consent (Art. 92)", "Court order (Art. 92)", "Other recovery")
NEEDS_CONSENT = ("Deduction with written consent (Art. 92)", "Other recovery")
GUIDE = {
	"Bonus": "Paid with the chosen month's salary.",
	"One-time payment": "A one-off earning (e.g. a one-time increment or reward) with the chosen month's salary.",
	"Allowance / arrears": "Back pay or an allowance missed earlier.",
	"Damage or loss (Art. 91)": "The employee lost or damaged company property. At most five days' wage a month; the rest moves to the "
								"next months automatically. The employee may object within 15 days.",
	"Deduction with written consent (Art. 92)": "Any other deduction for the company's own claims needs the employee's written consent.",
	"Court order (Art. 92)": "Deduction ordered by a court (attach the order). Court orders may take up to a quarter of the wage.",
	"Other recovery": "Recovering an overpayment or other amount owed - needs the employee's written consent.",
}


def _employees(data):
	ids = [e for e in (data.get("employees") or []) if e]
	if data.get("department"):
		ids += frappe.get_all("Employee", filters={"department": data["department"], "status": "Active"}, pluck="name")
	ids = list(dict.fromkeys(ids))
	if not ids:
		frappe.throw(_("Choose at least one employee."))
	return ids


def _amount_for(employee, data):
	if data.get("amount_type") == "% of wage":
		return flt(loans.monthly_wage(employee) * flt(data.get("amount")) / 100, 2)
	return flt(data.get("amount"), 2)


def _plan(employee, data):
	"""Months and amounts this adjustment will use for one employee, with the Saudi limits checked."""
	category = data.get("category")
	month = loans._month(data.get("payroll_month") or nowdate())
	amount = _amount_for(employee, data)
	if amount <= 0:
		return {"employee": employee, "amount": 0, "lines": [], "problems": [_("The amount is zero.")]}
	lines, problems = [], []
	if category in EARNINGS:
		lines = [{"month": month, "amount": amount}]
	else:
		wage = loans.monthly_wage(employee)
		if category in NEEDS_CONSENT and not cint(data.get("consent")):
			problems.append(_("Needs the employee's written consent (Art. 92). Tick consent and attach it."))
		parts = rules.split_by_cap(amount, rules.damage_cap(wage)) if category == "Damage or loss (Art. 91)" else [amount]
		kind = loans.ADJ_KIND.get(category, rules.CONSENT)
		for i, part in enumerate(parts):
			m = rules.add_months(month, i)
			res = loans.check(employee, m, [(kind, part)], wage=wage)
			for p in loans.describe(res.problems):
				problems.append(f"{frappe.utils.formatdate(m, 'MMM yyyy')}: {p}")
			lines.append({"month": m, "amount": part})
	return {"employee": employee, "employee_name": frappe.db.get_value("Employee", employee, "employee_name"),
			"amount": amount, "lines": [{**x, "month": str(x["month"])} for x in lines], "problems": problems}


@frappe.whitelist(methods=["POST"])
def preview(data):
	require_hr()
	data = parse_json(data) or {}
	_validate(data)
	return {"rows": [_plan(e, data) for e in _employees(data)], "guide": _(GUIDE.get(data.get("category"), ""))}


def _validate(data):
	if data.get("category") not in EARNINGS + DEDUCTIONS:
		frappe.throw(_("Choose a category."))
	if not (data.get("reason") or "").strip():
		frappe.throw(_("Please give a reason."))


@frappe.whitelist(methods=["POST"])
def create(data):
	"""Post the adjustment(s) as Additional Salary for each employee. Nothing is posted if any employee breaks a limit."""
	require_hr()
	data = parse_json(data) or {}
	_validate(data)
	plans = [_plan(e, data) for e in _employees(data)]
	bad = [p for p in plans if p["problems"]]
	if bad:
		frappe.throw("<br>".join(f"<b>{p['employee_name'] or p['employee']}</b>: {'; '.join(p['problems'])}" for p in bad[:20]),
					 title=_("Not posted"))
	category = data["category"]
	kind = "Earning" if category in EARNINGS else "Deduction"
	comp = data.get("salary_component") or loans.component("bonus_component" if kind == "Earning" else "hr_deduction_component")
	if frappe.db.get_value("Salary Component", comp, "statistical_component"):
		frappe.throw(_("{0} is an accrual component and is never paid.").format(comp))
	if frappe.db.get_value("Salary Component", comp, "type") != kind:
		frappe.throw(_("{0} is not an {1} component.").format(comp, _(kind).lower()))
	batch = frappe.generate_hash(length=8) if len(plans) > 1 else None
	made = []
	for p in plans:
		company = frappe.db.get_value("Employee", p["employee"], "company")
		posted = []
		for line in p["lines"]:
			add = frappe.get_doc({"doctype": "Additional Salary", "employee": p["employee"], "company": company, "salary_component": comp,
								  "amount": line["amount"], "payroll_date": getdate(get_last_day(line["month"])),
								  "overwrite_salary_structure_amount": 0})
			add.flags.ignore_permissions = True
			add.insert()
			add.submit()
			posted.append({**line, "additional_salary": add.name})
		doc = frappe.get_doc({"doctype": DT, "employee": p["employee"], "kind": kind, "category": category, "salary_component": comp,
							  "amount": p["amount"], "payroll_month": loans._month(data.get("payroll_month") or nowdate()),
							  "status": "Posted", "batch": batch, "consent": cint(data.get("consent")),
							  "consent_file": data.get("consent_file"), "reason": str(data["reason"])[:1000],
							  "additional_salaries": json.dumps(posted)})
		doc.insert(ignore_permissions=True)
		made.append(doc.name)
		if kind == "Deduction":
			from alphax_hr.api import alerts

			alerts.event("Request decision", _("Salary deduction: {0:,.2f}").format(p["amount"]),
						 f"{_(category)} - {data['reason']}", employee=p["employee"], url="/alphax/me/payslips", doc=(DT, doc.name))
	return {"created": made, "batch": batch}


@frappe.whitelist()
def adjustments(month=None, kind=None):
	require_hr()
	filters = {}
	if month:
		filters["payroll_month"] = loans._month(month)
	if kind:
		filters["kind"] = kind
	rows = frappe.get_all(DT, filters=filters, fields=["name", "employee", "employee_name", "kind", "category", "amount", "payroll_month",
													  "status", "batch", "reason", "consent", "additional_salaries"],
						  order_by="creation desc", limit=500)
	for r in rows:
		r.payroll_month = str(r.payroll_month)
		r.lines = parse_json(r.pop("additional_salaries"), []) or []
	comps = frappe.get_all("Salary Component", filters={"statistical_component": 0}, fields=["name", "type"], order_by="name")
	return {"rows": rows, "components": comps, "categories": {"Earning": EARNINGS, "Deduction": DEDUCTIONS},
			"guide": {k: _(v) for k, v in GUIDE.items()}, "needs_consent": NEEDS_CONSENT}


@frappe.whitelist(methods=["POST"])
def cancel(name, reason=None):
	require_hr_manager()
	doc = frappe.get_doc(DT, name)
	if doc.status != "Posted":
		frappe.throw(_("Already cancelled."))
	for line in parse_json(doc.additional_salaries, []) or []:
		if loans._slip_submitted(doc.employee, loans._month(line["month"])):
			frappe.throw(_("The {0} salary is already submitted with this amount. Correct it in a later month.").format(
				frappe.utils.formatdate(line["month"], "MMM yyyy")))
	for line in parse_json(doc.additional_salaries, []) or []:
		if frappe.db.get_value("Additional Salary", line["additional_salary"], "docstatus") == 1:
			add = frappe.get_doc("Additional Salary", line["additional_salary"])
			add.flags.ignore_permissions = True
			add.cancel()
	doc.status = "Cancelled"
	if reason:
		doc.add_comment("Comment", frappe.utils.escape_html(str(reason)[:500]))
	doc.save(ignore_permissions=True)
	return {"ok": True}


@frappe.whitelist()
def deduction_status(employee, month=None):
	"""Everything deducted from the employee in a month against the legal limits (shown before HR adds more)."""
	require_hr()
	month = loans._month(month or nowdate())
	wage = loans.monthly_wage(employee)
	res = loans.check(employee, month, [], wage=wage)
	return {"wage": wage, "month": str(month), "items": [{"kind": k, "label": _(rules.LABELS[k]), "amount": v} for k, v in res.by_kind.items()],
			"total": res.total, "half_wage": rules.total_cap(wage), "room": res.room, "loan_cap": rules.loan_cap(wage),
			"damage_cap": rules.damage_cap(wage), "problems": loans.describe(res.problems)}


# ------------------------------------------------------------------ salary increments
def _increment_package(employee, mode, value):
	from alphax_hr.api.salary import _config

	c = _config()
	ssa = frappe.get_all("Salary Structure Assignment", filters={"employee": employee, "docstatus": 1}, fields=["salary_structure"],
						 order_by="from_date desc", limit=1)
	if not ssa:
		return None, _("No salary yet")
	rows = frappe.get_all("Salary Detail", filters={"parent": ssa[0].salary_structure, "parenttype": "Salary Structure",
													"parentfield": "earnings"}, fields=["salary_component", "amount", "amount_based_on_formula"])
	keys = {c[k]: k for k in ("basic", "housing", "transport", "other") if c[k]}
	if any(r.amount_based_on_formula for r in rows) or any(r.salary_component not in keys for r in rows):
		return None, _("Salary has components AlphaX does not manage; change it on the profile")
	parts = {"basic": 0.0, "housing": 0.0, "transport": 0.0, "other": 0.0}
	for r in rows:
		parts[keys[r.salary_component]] += flt(r.amount)
	before = sum(parts.values())
	if mode == "percent_all":
		parts = {k: flt(v * (1 + flt(value) / 100), 2) for k, v in parts.items()}
	elif mode == "percent_basic":
		parts["basic"] = flt(parts["basic"] * (1 + flt(value) / 100), 2)
	else:
		parts["basic"] = flt(parts["basic"] + flt(value), 2)
	return {"mode": "components", **parts, "_before": before, "_after": flt(sum(parts.values()), 2)}, None


@frappe.whitelist(methods=["POST"])
def increment(data, apply=0):
	"""Salary increment for one or many employees from a date: % of all components, % of basic, or an amount on basic."""
	require_hr_manager() if cint(apply) else require_hr()
	data = parse_json(data) or {}
	mode = data.get("mode") or "percent_all"
	if mode not in ("percent_all", "percent_basic", "amount_basic") or flt(data.get("value")) <= 0:
		frappe.throw(_("Choose how much to increase."))
	if not data.get("from_date"):
		frappe.throw(_("Choose the date the new salary starts."))
	rows = []
	for e in _employees(data):
		pkg, why = _increment_package(e, mode, data.get("value"))
		row = {"employee": e, "employee_name": frappe.db.get_value("Employee", e, "employee_name"), "skipped": why}
		if pkg:
			row.update({"before": pkg["_before"], "after": pkg["_after"]})
			if cint(apply):
				from alphax_hr.api.salary import assign

				clean = {k: v for k, v in pkg.items() if not k.startswith("_")}
				res = assign(e, clean, data["from_date"])
				row["assignment"] = res["assignment"]
				frappe.get_doc("Employee", e).add_comment("Comment", frappe.utils.escape_html(
					_("Salary increment from {0}: {1:,.2f} → {2:,.2f}. {3}").format(data["from_date"], pkg["_before"], pkg["_after"],
																				   data.get("reason") or "")))
		rows.append(row)
	return {"rows": rows, "applied": bool(cint(apply))}
