"""Payroll overview, GOSI register and end-of-service calculator (HR only)."""
from __future__ import annotations

from datetime import date

import frappe
from frappe import _
from frappe.utils import flt, get_first_day, get_last_day, getdate, nowdate

from alphax_hr.api._common import require_hr, settings
from alphax_hr.api._wages import wages
from alphax_hr.saudi import eosb as eosb_rules
from alphax_hr.saudi import gosi as gosi_rules


@frappe.whitelist()
def payroll_runs(year=None):
	require_hr()
	year = int(year or getdate(nowdate()).year)
	rows = frappe.get_list(
		"Payroll Entry",
		filters={"posting_date": ["between", [f"{year}-01-01", f"{year}-12-31"]]},
		fields=["name", "company", "posting_date", "start_date", "end_date", "payroll_frequency",
				"number_of_employees", "status", "docstatus", "department", "branch"],
		order_by="posting_date desc",
		page_length=500,
	)
	return {"year": year, "rows": rows,
			"counts": {s: sum(1 for r in rows if r.status == s) for s in {r.status for r in rows}}}


@frappe.whitelist()
def slip_summary(month=None):
	require_hr()
	ref = getdate(month or nowdate())
	start, end = get_first_day(ref), get_last_day(ref)
	rows = frappe.get_list(
		"Salary Slip",
		filters={"start_date": [">=", start], "end_date": ["<=", end], "docstatus": ["<", 2]},
		fields=["docstatus", "count(name) as slips", "sum(gross_pay) as gross", "sum(total_deduction) as deductions",
				"sum(net_pay) as net"],
		group_by="docstatus",
	)
	out = {"month": str(start), "draft": {}, "submitted": {}}
	for r in rows:
		out["submitted" if r.docstatus == 1 else "draft"] = {
			"slips": r.slips, "gross": flt(r.gross, 2), "deductions": flt(r.deductions, 2), "net": flt(r.net, 2)}
	out["active_employees"] = frappe.get_list("Employee", filters={"status": "Active"}, fields=["count(name) as n"])[0].n
	return out


def _rates():
	rows = frappe.get_all(  # rate table is configuration, readable by HR
		"GOSI Contribution Rate",
		fields=["system", "effective_from", "employee_pension", "employer_pension",
				"employee_saned", "employer_saned", "employer_hazard"],
	)
	if not rows:
		return gosi_rules.DEFAULT_RATES
	from decimal import Decimal as D

	return tuple(
		gosi_rules.RateRow(r.system, getdate(r.effective_from), D(str(r.employee_pension or 0)),
						   D(str(r.employer_pension or 0)), D(str(r.employee_saned or 0)),
						   D(str(r.employer_saned or 0)), D(str(r.employer_hazard or 0)))
		for r in rows
	)


@frappe.whitelist()
def gosi_register(month=None, company=None):
	require_hr()
	conf = settings()
	ref = getdate(month or nowdate())
	start, end = get_first_day(ref), get_last_day(ref)
	filters = {"status": "Active", "date_of_joining": ["<=", end]}
	if company or conf.default_company:
		filters["company"] = company or conf.default_company
	emps = frappe.get_list("Employee", filters=filters,
						   fields=["name", "employee_name", "alphax_is_saudi", "alphax_gosi_registration_date",
								   "alphax_gosi_number", "department"],
						   order_by="employee_name asc", page_length=10000)
	wage_map = wages([e.name for e in emps], start, end)
	rates = _rates()
	rows, totals = [], {"employee": 0.0, "employer": 0.0, "wage": 0.0}
	summary = {gosi_rules.LEGACY: 0, gosi_rules.NEW: 0, gosi_rules.NON_SAUDI: 0, gosi_rules.UNCLASSIFIED: 0}
	for e in emps:
		w = wage_map[e.name]
		reg = getdate(e.alphax_gosi_registration_date) if e.alphax_gosi_registration_date else None
		try:
			c = gosi_rules.calculate(is_saudi=bool(e.alphax_is_saudi), gosi_registration_date=reg,
									 basic=w["basic"], housing=w["housing"], period_date=end, rates=rates,
									 cap=flt(conf.gosi_wage_cap) or gosi_rules.DEFAULT_WAGE_CAP,
									 floor=flt(conf.gosi_wage_floor))
		except ValueError as exc:
			frappe.throw(_("GOSI rates are incomplete: {0}").format(exc))
		data = c.as_dict()
		data.update({"employee": e.name, "employee_name": e.employee_name, "department": e.department,
					 "gosi_number": e.alphax_gosi_number, "wage_source": w["source"],
					 "warnings": data["warnings"] + w["warnings"]})
		rows.append(data)
		summary[c.system] += 1
		totals["employee"] += data["employee_amount"]
		totals["employer"] += data["employer_amount"]
		totals["wage"] += data["wage"]
	totals = {k: round(v, 2) for k, v in totals.items()}
	totals["total"] = round(totals["employee"] + totals["employer"], 2)
	return {"month": str(start), "period_end": str(end), "rows": rows, "totals": totals, "systems": summary,
			"needs_attention": sum(1 for r in rows if r["warnings"])}


@frappe.whitelist()
def eosb(employee, exit_date=None, reason=eosb_rules.TERMINATION, monthly_wage=None):
	require_hr()
	doc = frappe.get_doc("Employee", employee)
	doc.check_permission("read")
	if not doc.date_of_joining:
		frappe.throw(_("The employee has no joining date."))
	exit_on = getdate(exit_date or doc.relieving_date or nowdate())
	source = "manual"
	if monthly_wage in (None, ""):
		# Last actual wage: the most recent payslip up to the exit month; the
		# salary structure base is only a fallback.
		w = wages([employee], date(2000, 1, 1), get_last_day(exit_on))[employee]
		monthly_wage, source = w["eosb_wage"], w["source"]
	try:
		result = eosb_rules.calculate(getdate(doc.date_of_joining), exit_on, monthly_wage, reason)
	except ValueError as exc:
		frappe.throw(str(exc))
	data = result.as_dict()
	data.update({"employee": doc.name, "employee_name": doc.employee_name, "date_of_joining": str(doc.date_of_joining),
				 "exit_date": str(exit_on), "wage_source": source, "reasons": list(eosb_rules.REASONS)})
	return data
