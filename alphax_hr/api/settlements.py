"""End-of-service final settlement: award (Art. 84/85), unused leave, final salary, advances.

Paid either with the final payroll (amounts become Additional Salary on the exit month)
or separately (a stand-alone statement HR pays outside payroll).
"""
from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, now_datetime, nowdate

from alphax_hr.api._common import require_hr, require_hr_manager, settings
from alphax_hr.saudi import eosb as eosb_rules

COMPONENTS = {
	"eosb": ("End of Service Benefit", "EOSB", "Earning"),
	"leave": ("Leave Encashment", "LENC", "Earning"),
	"earn": ("Final Settlement Earnings", "FSE", "Earning"),
	"deduct": ("Final Settlement Deduction", "FSD", "Deduction"),
}
FIELDS = ("name", "employee", "employee_name", "company", "reason", "exit_date", "mode", "status", "date_of_joining", "service_years",
		  "monthly_wage", "wage_source", "eosb_amount", "eosb_factor", "leave_days", "leave_amount", "unpaid_days", "unpaid_salary",
		  "other_earnings", "advances", "other_deductions", "net_amount", "additional_salaries", "approved_by", "approved_on", "paid_on", "notes")


def _component(key):
	if key in ("eosb", "leave"):
		from alphax_hr.api import components

		return components.get("eos" if key == "eosb" else "leave_encashment")
	name, abbr, kind = COMPONENTS[key]
	if not frappe.db.exists("Salary Component", name):
		frappe.get_doc({"doctype": "Salary Component", "salary_component": name, "salary_component_abbr": abbr, "type": kind,
						"depends_on_payment_days": 0}).insert(ignore_permissions=True)
	return name


def leave_balance(employee, on):
	lt = settings().get("annual_leave_type")
	if not lt:
		return 0.0
	from hrms.hr.doctype.leave_application.leave_application import get_leave_balance_on

	return flt(get_leave_balance_on(employee, lt, getdate(on), consider_all_leaves_in_the_allocation_period=True), 2)


def outstanding_advances(employee):
	if not frappe.db.exists("DocType", "Employee Advance"):
		return 0.0
	rows = frappe.get_all("Employee Advance", filters={"employee": employee, "docstatus": 1},
						  fields=["paid_amount", "claimed_amount", "return_amount"])
	return flt(sum(max(flt(r.paid_amount) - flt(r.claimed_amount) - flt(r.return_amount), 0) for r in rows), 2)


def compute(doc):
	emp = frappe.get_doc("Employee", doc.employee)
	if not emp.date_of_joining:
		frappe.throw(_("The employee has no joining date."))
	doc.date_of_joining = emp.date_of_joining
	if not flt(doc.monthly_wage):
		from datetime import date

		from frappe.utils import get_last_day

		from alphax_hr.api._wages import wages

		w = wages([doc.employee], date(2000, 1, 1), get_last_day(doc.exit_date))[doc.employee]
		doc.monthly_wage, doc.wage_source = w["eosb_wage"], w["source"]
	else:
		doc.wage_source = doc.wage_source or "manual"
	try:
		r = eosb_rules.calculate(getdate(emp.date_of_joining), getdate(doc.exit_date), flt(doc.monthly_wage), doc.reason)
	except ValueError as exc:
		frappe.throw(str(exc))
	doc.service_years, doc.eosb_factor, doc.eosb_amount = flt(r.service_years, 4), flt(r.entitlement_factor), flt(r.award)
	daily = flt(doc.monthly_wage) / 30
	if doc.leave_days is None:
		doc.leave_days = max(leave_balance(doc.employee, doc.exit_date), 0)
	doc.leave_amount = flt(flt(doc.leave_days) * daily, 2)
	doc.unpaid_salary = flt(flt(doc.unpaid_days) * daily, 2) if doc.mode == "Separate payment" else 0
	if doc.advances is None:
		doc.advances = outstanding_advances(doc.employee)
	doc.net_amount = flt(flt(doc.eosb_amount) + flt(doc.leave_amount) + flt(doc.unpaid_salary) + flt(doc.other_earnings)
						 - flt(doc.advances) - flt(doc.other_deductions), 2)
	return doc


def _out(doc):
	d = {k: doc.get(k) for k in FIELDS}
	for k in ("exit_date", "date_of_joining", "paid_on", "approved_on"):
		d[k] = str(d[k]) if d[k] else None
	return d


@frappe.whitelist(methods=["POST"])
def prepare(employee: str, exit_date: str, reason: str, mode: str = "With payroll", monthly_wage: float | str | None = None, leave_days: float | str | None = None, unpaid_days: int | str = 0,
			other_earnings: float | str = 0, other_deductions: float | str = 0, advances: str | dict | list | None = None, notes: str | None = None, name: str | None = None):
	"""Create or update a draft settlement and calculate it."""
	require_hr()
	frappe.get_doc("Employee", employee).check_permission("read")
	if reason not in eosb_rules.REASONS:
		frappe.throw(_("Unknown end-of-service reason."))
	if name:
		doc = frappe.get_doc("AlphaX Final Settlement", name)
		if doc.status != "Draft":
			frappe.throw(_("Only a draft can be changed."))
	else:
		existing = frappe.db.get_value("AlphaX Final Settlement", {"employee": employee, "status": ["in", ["Draft", "Approved", "Paid"]]})
		if existing:
			frappe.throw(_("{0} already has a final settlement ({1}).").format(employee, existing))
		doc = frappe.new_doc("AlphaX Final Settlement")
	doc.update({"employee": employee, "exit_date": exit_date, "reason": reason, "mode": mode,
				"monthly_wage": flt(monthly_wage) if monthly_wage not in (None, "") else None,
				"leave_days": flt(leave_days) if leave_days not in (None, "") else None,
				"unpaid_days": flt(unpaid_days), "other_earnings": flt(other_earnings), "other_deductions": flt(other_deductions),
				"advances": flt(advances) if advances not in (None, "") else None, "notes": notes})
	if doc.monthly_wage is None:
		doc.wage_source = None
	compute(doc)
	doc.save()
	return _out(doc)


@frappe.whitelist()
def settlement(name: str):
	require_hr()
	return _out(frappe.get_doc("AlphaX Final Settlement", name))


@frappe.whitelist()
def settlements(status: str | None = None, limit: int | str = 200):
	require_hr()
	filters = {"status": status} if status else {}
	return [_out(r) for r in frappe.get_list("AlphaX Final Settlement", filters=filters, fields=list(FIELDS),
											   order_by="exit_date desc", page_length=min(cint(limit) or 200, 1000))]


def _additional(doc, key, amount):
	add = frappe.get_doc({"doctype": "Additional Salary", "employee": doc.employee, "company": doc.company,
						  "salary_component": _component(key), "amount": flt(amount, 2), "payroll_date": doc.exit_date,
						  "overwrite_salary_structure_amount": 0})
	add.flags.ignore_permissions = True  # HR-Manager-only endpoint
	add.insert()
	add.submit()
	return add.name


@frappe.whitelist(methods=["POST"])
def approve(name: str):
	require_hr_manager()
	doc = frappe.get_doc("AlphaX Final Settlement", name)
	if doc.status != "Draft":
		frappe.throw(_("Only a draft can be approved."))
	compute(doc)
	created = []
	if doc.mode == "With payroll":
		from alphax_hr.api._common import require_salary_structure

		require_salary_structure(doc.employee, doc.exit_date, _("Choose 'Separate payment' or assign a salary first."))
		for key, amount in (("eosb", doc.eosb_amount), ("leave", doc.leave_amount), ("earn", doc.other_earnings),
							("deduct", flt(doc.advances) + flt(doc.other_deductions))):
			if flt(amount) > 0:
				created.append(_additional(doc, key, amount))
	emp = frappe.get_doc("Employee", doc.employee)
	if str(emp.relieving_date or "") != str(doc.exit_date):
		emp.relieving_date = doc.exit_date
		emp.flags.ignore_mandatory = True
		emp.save(ignore_permissions=True)
	doc.additional_salaries = "\n".join(created) or None
	doc.status, doc.approved_by, doc.approved_on = "Approved", frappe.session.user, now_datetime()
	doc.save()
	return _out(doc)


@frappe.whitelist(methods=["POST"])
def mark_paid(name: str, paid_on: str | None = None):
	require_hr_manager()
	doc = frappe.get_doc("AlphaX Final Settlement", name)
	if doc.status != "Approved":
		frappe.throw(_("Approve the settlement first."))
	doc.status, doc.paid_on = "Paid", paid_on or nowdate()
	doc.save()
	if getdate(doc.exit_date) <= getdate(nowdate()):
		frappe.db.set_value("Employee", doc.employee, "status", "Left")
	return _out(doc)


@frappe.whitelist(methods=["POST"])
def cancel(name: str, reason: str):
	require_hr_manager()
	if not (reason or "").strip():
		frappe.throw(_("Please give a reason for cancelling."))
	doc = frappe.get_doc("AlphaX Final Settlement", name)
	if doc.status == "Paid":
		frappe.throw(_("A paid settlement cannot be cancelled here."))
	for add in (doc.additional_salaries or "").split():
		if frappe.db.get_value("Additional Salary", add, "docstatus") == 1:
			a = frappe.get_doc("Additional Salary", add)
			a.flags.ignore_permissions = True
			a.cancel()
	doc.status = "Cancelled"
	doc.save()
	doc.add_comment("Comment", frappe.utils.escape_html(reason[:1000]))
	return _out(doc)


@frappe.whitelist(methods=["GET"])
def statement(name: str):
	"""Bilingual settlement statement as PDF."""
	require_hr()
	from frappe.utils.pdf import get_pdf

	doc = frappe.get_doc("AlphaX Final Settlement", name)
	company_ar = frappe.db.get_value("Company", doc.company, "company_name_in_arabic") if frappe.get_meta("Company").has_field(
		"company_name_in_arabic") else ""
	# Reviewed: template path is fixed in the app, or an HR-authored letter rendered in Frappe's sandboxed Jinja.
	html = frappe.render_template("alphax_hr/templates/alphax/settlement.html",  # nosemgrep
								  {"d": frappe._dict(_out(doc)), "company": doc.company, "company_ar": company_ar or "",
								   "fmt": lambda v: f"{flt(v):,.2f}", "today": frappe.utils.formatdate(nowdate())})
	frappe.response.filename = f"{doc.name}.pdf"
	frappe.response.filecontent = get_pdf(html)
	frappe.response.type = "pdf"
