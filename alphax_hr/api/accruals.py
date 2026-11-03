"""Monthly accruals for end-of-service benefit and annual leave (provisions), posted to ERPNext.

Method (common Saudi practice for IAS 19 short-term and end-of-service obligations, without an actuarial model):
- At each month end the obligation is re-measured per employee: end-of-service award as if the employee left that
  day (Art. 84 full award by default, or Art. 85 resignation basis), and annual leave owed = unused days x daily
  actual wage (monthly wage / 30).
- The month's charge is the obligation minus what was already accrued (true-up). A pay rise, extra years or used
  leave are therefore reflected automatically; a negative charge reverses part of the provision.
- One Journal Entry per run: Dr expense / Cr provision, split by the employee's payroll cost center.
- Leavers drop out of the run: their provision is used when the final settlement is paid. Point the End of Service
  and Leave Encashment components' accounts at the provision accounts so the payment uses the provision.
Larger entities reporting under full IFRS should still have the end-of-service obligation valued by an actuary once
a year (projected unit credit); the difference is booked as a manual adjustment.
"""
from __future__ import annotations

from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import flt, get_first_day, get_last_day, getdate

from alphax_hr.api._common import require_hr, settings
from alphax_hr.saudi import eosb as eos_rules

DT = "AlphaX Accrual Run"
ROLES = {"HR Manager", "System Manager", "Accounts Manager"}


def _require_poster():
	if not set(frappe.get_roles()) & ROLES:
		frappe.throw(_("Only HR Managers or Accounts Managers can post accruals."), frappe.PermissionError)


def _bounds(month):
	ref = getdate(month)
	return getdate(get_first_day(ref)), getdate(get_last_day(ref))


def structure_wage(employee, on, eos=False):
	"""Contractual monthly wage on a date from the salary structure in force (accruals, unlike payslips, ignore one-offs).
	For end of service, components mapped as 'EOSB Wage' are used when the mapping exists."""
	ssa = frappe.get_all("Salary Structure Assignment", filters={"employee": employee, "docstatus": 1, "from_date": ["<=", on]},
						 fields=["salary_structure", "base"], order_by="from_date desc", limit=1)
	if not ssa:
		return 0.0
	rows = frappe.get_all("Salary Detail", filters={"parent": ssa[0].salary_structure, "parenttype": "Salary Structure",
													"parentfield": "earnings"}, fields=["salary_component", "amount", "amount_based_on_formula"])
	stat = set(frappe.get_all("Salary Component", filters={"statistical_component": 1}, pluck="name"))
	rows = [r for r in rows if r.salary_component not in stat and not r.amount_based_on_formula]
	if eos:
		mapped = {r.salary_component for r in settings().get("component_map") or [] if r.purpose == "EOSB Wage"}
		if mapped and any(r.salary_component in mapped for r in rows):
			rows = [r for r in rows if r.salary_component in mapped]
	total = sum(flt(r.amount) for r in rows)
	return flt(total or ssa[0].base, 2)


def _leave_days(employee, on):
	lt = settings().get("annual_leave_type")
	if not lt:
		return 0.0
	from hrms.hr.doctype.leave_application.leave_application import get_leave_balance_on

	try:
		return max(0.0, flt(get_leave_balance_on(employee, lt, on, consider_all_leaves_in_the_allocation_period=True), 2))
	except Exception:  # noqa: BLE001 - no allocation yet
		return 0.0


def _previous(company, start):
	"""Last posted obligations per employee before this month."""
	out = {}
	runs = frappe.get_all(DT, filters={"company": company, "status": "Posted", "month": ["<", start]}, pluck="name",
						  order_by="month desc", limit=1)
	if runs:
		for line in frappe.get_all("AlphaX Accrual Line", filters={"parent": runs[0]},
								   fields=["employee", "eos_obligation", "leave_obligation"]):
			out[line.employee] = (flt(line.eos_obligation), flt(line.leave_obligation))
	return out


def compute(company, month):
	start, end = _bounds(month)
	conf = settings()
	full = (conf.get("eos_accrual_basis") or "Full award (Art. 84)").startswith("Full")
	reason = eos_rules.TERMINATION if full else eos_rules.RESIGNATION
	prev = _previous(company, start)
	emps = frappe.get_all("Employee", filters={"company": company, "date_of_joining": ["<=", end]},
						  or_filters={"status": "Active", "relieving_date": [">", end]},
						  fields=["name", "employee_name", "date_of_joining", "payroll_cost_center"], order_by="employee_name asc")
	default_cc = frappe.get_cached_value("Company", company, "cost_center")
	lines = []
	for e in emps:
		eos_wage = structure_wage(e.name, end, eos=True)
		leave_wage = structure_wage(e.name, end)
		note = None
		try:
			res = eos_rules.calculate(getdate(e.date_of_joining), end, eos_wage, reason)
			eos_obl, years = flt(res.award, 2), round(res.service_years, 2)
		except ValueError:
			eos_obl, years, note = 0.0, 0.0, _("No wage")
		days = _leave_days(e.name, end)
		leave_obl = flt(days * leave_wage / 30, 2)
		p_eos, p_leave = prev.get(e.name, (0.0, 0.0))
		lines.append({"employee": e.name, "employee_name": e.employee_name, "cost_center": e.payroll_cost_center or default_cc,
					  "service_years": years, "eos_wage": eos_wage, "eos_obligation": eos_obl, "eos_previous": p_eos,
					  "eos_charge": flt(eos_obl - p_eos, 2), "leave_days": days, "leave_wage": leave_wage,
					  "leave_obligation": leave_obl, "leave_previous": p_leave, "leave_charge": flt(leave_obl - p_leave, 2),
					  "note": note if eos_wage else _("No salary structure")})
	return {"company": company, "month": str(start), "basis": _("Full award (Art. 84)") if full else _("Resignation award (Art. 85)"),
			"lines": lines, "eos_total": flt(sum(x["eos_charge"] for x in lines), 2),
			"leave_total": flt(sum(x["leave_charge"] for x in lines), 2),
			"eos_balance": flt(sum(x["eos_obligation"] for x in lines), 2),
			"leave_balance": flt(sum(x["leave_obligation"] for x in lines), 2)}


def _accounts_ok(company):
	conf = settings()
	missing = [label for field, label in (("eos_expense_account", _("EOS expense")), ("eos_provision_account", _("EOS provision")),
										  ("leave_expense_account", _("Leave expense")), ("leave_provision_account", _("Leave provision")))
			   if not conf.get(field) or frappe.db.get_value("Account", conf.get(field), "company") != company]
	return missing


def _warnings(company):
	out = []
	missing = _accounts_ok(company)
	if missing:
		out.append(_("Set these accounts for {0} in HR status & setup → Settings → Accruals: {1}").format(company, ", ".join(missing)))
	from alphax_hr.api import components

	for key, field in (("eos", "eos_provision_account"), ("leave_encashment", "leave_provision_account")):
		acc = settings().get(field)
		comp = components.get(key)
		used = frappe.db.get_value("Salary Component Account", {"parent": comp, "company": company}, "account")
		if acc and used != acc:
			out.append(_("Component {0} should post to {1} so the final settlement uses the provision (now: {2}).").format(
				comp, acc, used or _("not set")))
	return out


@frappe.whitelist()
def runs(company: str | None = None):
	require_hr()
	filters = {"company": company} if company else {}
	rows = frappe.get_all(DT, filters=filters, fields=["name", "company", "month", "status", "eos_total", "leave_total", "eos_balance",
													  "leave_balance", "journal_entry", "modified"], order_by="month desc", limit=36)
	for r in rows:
		r.month, r.modified = str(r.month), str(r.modified)
	return {"rows": rows, "companies": frappe.get_list("Company", pluck="name"),
			"can_post": bool(set(frappe.get_roles()) & ROLES)}


@frappe.whitelist()
def preview(company: str, month: str):
	require_hr()
	data = compute(company, month)
	data["warnings"] = _warnings(company)
	data["accounts_missing"] = bool(_accounts_ok(company))
	start, _end = _bounds(month)
	data["existing"] = frappe.db.get_value(DT, {"company": company, "month": start, "status": ["!=", "Cancelled"]}, "name")
	return data


@frappe.whitelist(methods=["POST"])
def post(company: str, month: str):
	"""Save the run and post one Journal Entry (Dr expense / Cr provision, by cost center)."""
	_require_poster()
	start, end = _bounds(month)
	if frappe.db.exists(DT, {"company": company, "month": start, "status": "Posted"}):
		frappe.throw(_("Accruals for {0} are already posted. Cancel that run first.").format(frappe.utils.formatdate(start, "MMM yyyy")))
	later = frappe.db.exists(DT, {"company": company, "month": [">", start], "status": "Posted"})
	if later:
		frappe.throw(_("A later month is already posted ({0}). Cancel it first so the true-up stays in order.").format(later))
	missing = _accounts_ok(company)
	if missing:
		frappe.throw(_("Set the accrual accounts first: {0}").format(", ".join(missing)))
	data = compute(company, month)
	conf = settings()
	by_cc = defaultdict(lambda: [0.0, 0.0])
	for x in data["lines"]:
		by_cc[x["cost_center"]][0] += x["eos_charge"]
		by_cc[x["cost_center"]][1] += x["leave_charge"]
	je = frappe.new_doc("Journal Entry")
	je.voucher_type = "Journal Entry"
	je.company = company
	je.posting_date = end
	je.user_remark = _("AlphaX accruals {0}: end of service and annual leave").format(frappe.utils.formatdate(start, "MMM yyyy"))
	for cc, (eos, leave) in by_cc.items():
		for amount, expense, provision in ((eos, conf.eos_expense_account, conf.eos_provision_account),
										   (leave, conf.leave_expense_account, conf.leave_provision_account)):
			amount = flt(amount, 2)
			if not amount:
				continue
			dr, cr = (expense, provision) if amount > 0 else (provision, expense)
			je.append("accounts", {"account": dr, "debit_in_account_currency": abs(amount), "cost_center": cc})
			je.append("accounts", {"account": cr, "credit_in_account_currency": abs(amount), "cost_center": cc})
	run = frappe.get_doc({"doctype": DT, "company": company, "month": start, "status": "Draft", "basis": data["basis"],
						  "eos_total": data["eos_total"], "leave_total": data["leave_total"], "eos_balance": data["eos_balance"],
						  "leave_balance": data["leave_balance"], "lines": data["lines"]})
	run.insert(ignore_permissions=True)
	if je.accounts:
		je.flags.ignore_permissions = True
		je.insert()
		je.submit()
		run.journal_entry = je.name
	run.status = "Posted"
	run.posted_by = frappe.session.user
	run.save(ignore_permissions=True)
	return {"name": run.name, "journal_entry": run.journal_entry, **{k: data[k] for k in ("eos_total", "leave_total")}}


@frappe.whitelist(methods=["POST"])
def cancel(name: str):
	_require_poster()
	run = frappe.get_doc(DT, name)
	if run.status != "Posted":
		frappe.throw(_("Only a posted run can be cancelled."))
	if frappe.db.exists(DT, {"company": run.company, "month": [">", run.month], "status": "Posted"}):
		frappe.throw(_("Cancel the later months first."))
	if run.journal_entry and frappe.db.get_value("Journal Entry", run.journal_entry, "docstatus") == 1:
		je = frappe.get_doc("Journal Entry", run.journal_entry)
		je.flags.ignore_permissions = True
		je.cancel()
	run.status = "Cancelled"
	run.save(ignore_permissions=True)
	return {"ok": True}


@frappe.whitelist()
def detail(name: str):
	require_hr()
	run = frappe.get_doc(DT, name)
	return {**{k: run.get(k) for k in ("name", "company", "status", "basis", "eos_total", "leave_total", "eos_balance", "leave_balance",
										"journal_entry")}, "month": str(run.month),
			"lines": [{k: l.get(k) for k in ("employee", "employee_name", "cost_center", "service_years", "eos_wage", "eos_obligation",
											 "eos_previous", "eos_charge", "leave_days", "leave_wage", "leave_obligation",
											 "leave_previous", "leave_charge", "note")} for l in run.lines]}
