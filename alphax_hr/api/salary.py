"""Salary package for an employee: preview, create (own Salary Structure + assignment), current salary.

Follows the CentralHRMS approach so existing IRSAA payroll keeps working: each
employee gets their own Salary Structure with fixed component amounts, and a
Salary Structure Assignment from the start date. Changing salary later creates
a new structure and assignment; history is kept.
"""
from __future__ import annotations

from decimal import Decimal

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, nowdate

from alphax_hr.api._common import parse_json, require_hr, settings
from alphax_hr.saudi import gosi as gosi_rules
from alphax_hr.saudi import salary as pkg

DEFAULT_NAMES = {
	"salary_basic_component": ("Basic", "Basic Salary"),
	"salary_housing_component": ("House Rent Allowance", "Housing Allowance", "Housing"),
	"salary_transport_component": ("Transport Allowance", "Transportation Allowance", "Transport"),
	"salary_other_component": ("Other Allowance", "Other Allowances"),
	"salary_gosi_component": ("GOSI", "GOSI Employee", "GOSI Deduction"),
}


def seed_components():
	"""Fill empty component settings from components that exist on the site (by common names)."""
	if not frappe.db.exists("DocType", "AlphaX HR Settings"):
		return
	for field, names in DEFAULT_NAMES.items():
		if frappe.db.get_single_value("AlphaX HR Settings", field):
			continue
		for n in names:
			if frappe.db.exists("Salary Component", n):
				frappe.db.set_single_value("AlphaX HR Settings", field, n)
				break


def _config():
	conf = settings()
	return {
		"basic": conf.salary_basic_component, "housing": conf.salary_housing_component,
		"transport": conf.salary_transport_component, "other": conf.salary_other_component,
		"gosi": conf.salary_gosi_component,
		"housing_percent": flt(conf.salary_housing_percent) if conf.salary_housing_percent is not None else 25,
		"transport_percent": flt(conf.salary_transport_percent) if conf.salary_transport_percent is not None else 10,
	}


@frappe.whitelist()
def config(company=None):
	require_hr()
	c = _config()
	company = company or settings().default_company
	c["currency"] = frappe.get_cached_value("Company", company, "default_currency") if company else "SAR"
	c["ready"] = bool(c["basic"])
	return c


def _gosi_rates():
	from alphax_hr.api.payroll import _rates

	return _rates()


def compute(package, is_saudi=False, gosi_registration_date=None, start_date=None):
	"""Turn the form's package into earnings/deductions rows.

	package: {"mode": "total"|"components", "total", "other", "basic", "housing", "transport"}
	"""
	c = _config()
	if not c["basic"]:
		frappe.throw(_("Set the Basic salary component in Setup & health → Settings."), title=_("Salary setup"))
	mode = package.get("mode") or "total"
	if mode == "total":
		try:
			parts = pkg.split_total(package.get("total"), c["housing_percent"], c["transport_percent"], package.get("other") or 0)
		except (ValueError, ArithmeticError):
			frappe.throw(_("Enter a total package larger than the other allowances."))
	else:
		parts = {k: Decimal(str(flt(package.get(k)))) for k in ("basic", "housing", "transport", "other")}
		if parts["basic"] <= 0:
			frappe.throw(_("Enter the basic salary."))
	earnings = []
	for key in ("basic", "housing", "transport", "other"):
		amount = flt(parts.get(key) or 0, 2)
		if not amount:
			continue
		if not c[key]:
			frappe.throw(_("Set the {0} component in Setup & health → Settings.").format(_(key.title())), title=_("Salary setup"))
		earnings.append({"salary_component": c[key], "key": key, "amount": amount})
	deductions = []
	gosi = None
	if cint(is_saudi) and c["gosi"]:
		on = getdate(start_date or nowdate())
		reg = getdate(gosi_registration_date) if gosi_registration_date else on
		res = gosi_rules.calculate(is_saudi=True, gosi_registration_date=reg, basic=parts["basic"],
								   housing=parts.get("housing") or 0, period_date=on, rates=_gosi_rates(),
								   cap=flt(settings().gosi_wage_cap) or gosi_rules.DEFAULT_WAGE_CAP,
								   floor=flt(settings().gosi_wage_floor))
		gosi = res.as_dict()
		if gosi["employee_amount"]:
			deductions.append({"salary_component": c["gosi"], "key": "gosi", "amount": round(gosi["employee_amount"], 2)})
	gross = round(sum(e["amount"] for e in earnings), 2)
	ded = round(sum(d["amount"] for d in deductions), 2)
	return {"earnings": earnings, "deductions": deductions, "gross": gross, "total_deductions": ded,
			"net": round(gross - ded, 2), "basic": flt(parts["basic"], 2), "gosi": gosi}


@frappe.whitelist()
def preview(package, is_saudi=0, gosi_registration_date=None, start_date=None):
	require_hr()
	return compute(parse_json(package, {}), is_saudi, gosi_registration_date, start_date)


def _next_name(employee):
	existing = frappe.get_all("Salary Structure", filters={"name": ["like", f"{employee}-SS-%"]}, pluck="name")
	nums = [cint(n.rsplit("-", 1)[-1]) for n in existing if n.rsplit("-", 1)[-1].isdigit()]
	return f"{employee}-SS-{max(nums or [0]) + 1}"


def assign(employee, package, from_date=None):
	"""Create and submit the employee's Salary Structure and Salary Structure Assignment."""
	emp = frappe.get_doc("Employee", employee)
	start = getdate(from_date or emp.date_of_joining)
	data = compute(package, emp.get("alphax_is_saudi"), emp.get("alphax_gosi_registration_date"), start)
	currency = frappe.get_cached_value("Company", emp.company, "default_currency")
	ss = frappe.new_doc("Salary Structure")
	ss.name = _next_name(employee)
	ss.update({"company": emp.company, "is_active": "Yes", "payroll_frequency": "Monthly", "currency": currency})
	for row in data["earnings"]:
		ss.append("earnings", {"salary_component": row["salary_component"], "amount": row["amount"], "amount_based_on_formula": 0})
	for row in data["deductions"]:
		ss.append("deductions", {"salary_component": row["salary_component"], "amount": row["amount"], "amount_based_on_formula": 0})
	ss.flags.name_set = True
	ss.insert()
	ss.submit()
	ssa = frappe.get_doc({"doctype": "Salary Structure Assignment", "employee": employee, "salary_structure": ss.name,
						  "company": emp.company, "currency": currency, "from_date": start, "base": data["basic"]})
	ssa.insert()
	ssa.submit()
	return {"salary_structure": ss.name, "assignment": ssa.name, **data}


@frappe.whitelist()
def set_salary(employee, package, from_date):
	"""Profile: new salary from a date (keeps earlier assignments as history)."""
	require_hr()
	frappe.get_doc("Employee", employee).check_permission("write")
	return assign(employee, parse_json(package, {}), from_date)


@frappe.whitelist()
def current(employee):
	require_hr()
	frappe.get_doc("Employee", employee).check_permission("read")
	rows = frappe.get_all("Salary Structure Assignment", filters={"employee": employee, "docstatus": 1},
						  fields=["name", "salary_structure", "from_date", "base"], order_by="from_date desc", limit_page_length=20)
	if not rows:
		return {"current": None, "history": []}
	cur = rows[0]
	details = frappe.get_all("Salary Detail", filters={"parent": cur.salary_structure, "parenttype": "Salary Structure"},
							 fields=["salary_component", "amount", "parentfield", "formula", "amount_based_on_formula"],
							 order_by="idx asc")
	earnings = [d for d in details if d.parentfield == "earnings"]
	deductions = [d for d in details if d.parentfield == "deductions"]
	gross = sum(flt(d.amount) for d in earnings)
	ded = sum(flt(d.amount) for d in deductions)
	return {"current": {**cur, "from_date": str(cur.from_date), "earnings": earnings, "deductions": deductions,
						"gross": gross, "total_deductions": ded, "net": gross - ded},
			"history": [{**r, "from_date": str(r.from_date)} for r in rows]}
