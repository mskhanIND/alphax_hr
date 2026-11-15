"""Leave allocation for HR inside /alphax: see, give and cancel leave balances (HRMS Leave Allocation underneath).

Annual leave has its own automatic allocation per service year (leave_engine); this screen also shows that plan,
and lets HR give any other leave type to one employee, a department or everyone.
"""
from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, nowdate

from alphax_hr.api._common import parse_json, require_hr, require_hr_manager


def _year_bounds(year):
	year = cint(year) or getdate(nowdate()).year
	return f"{year}-01-01", f"{year}-12-31"


@frappe.whitelist()
def allocations(year: int | str | None = None, leave_type: str | None = None, department: str | None = None, txt: str | None = None):
	"""Submitted allocations that overlap the year, with what is used and left."""
	require_hr()
	start, end = _year_bounds(year)
	filters = {"docstatus": 1, "from_date": ["<=", end], "to_date": [">=", start]}
	if leave_type:
		filters["leave_type"] = leave_type
	rows = frappe.get_all("Leave Allocation", filters=filters, fields=[
		"name", "employee", "employee_name", "department", "leave_type", "from_date", "to_date", "new_leaves_allocated",
		"unused_leaves", "total_leaves_allocated", "carry_forward", "description"], order_by="employee_name asc, leave_type asc", limit=2000)
	if department:
		rows = [r for r in rows if r.department == department]
	if txt:
		n = str(txt).lower()
		rows = [r for r in rows if n in (r.employee_name or "").lower() or n in (r.employee or "").lower()]
	if rows:
		from hrms.hr.doctype.leave_application.leave_application import get_leaves_for_period

		for r in rows:
			try:
				used = abs(flt(get_leaves_for_period(r.employee, r.leave_type, r.from_date, r.to_date)))  # HRMS returns it negative
			except Exception:
				used = 0
			r["used"] = used or 0.0  # never "-0"
			r["left"] = flt(r.total_leaves_allocated) - used
	types = frappe.get_all("Leave Type", filters={"is_lwp": 0}, fields=["name", "is_carry_forward"], order_by="name asc")
	return {"rows": rows, "leave_types": types, "year": cint(year) or getdate(nowdate()).year,
			"can_edit": bool(set(frappe.get_roles()) & {"HR Manager", "System Manager"})}


def _targets(employees, department, company):
	filters = {"status": "Active"}
	if employees:
		filters["name"] = ["in", list(employees)]
	if department:
		filters["department"] = department
	if company:
		filters["company"] = company
	return frappe.get_all("Employee", filters=filters, fields=["name", "employee_name", "date_of_joining"], order_by="employee_name asc")


@frappe.whitelist(methods=["POST"])
def allocate(data: str | dict):
	"""Give `days` of a leave type for a period to the chosen employees (or a department, or everyone).
	Employees who already have an allocation of that type overlapping the period are skipped, never doubled.
	Preview first with data.dry_run = 1."""
	require_hr_manager()
	d = frappe._dict(parse_json(data) or {})
	if not d.leave_type or not frappe.db.exists("Leave Type", d.leave_type):
		frappe.throw(_("Please choose a leave type."))
	if not d.from_date or not d.to_date or getdate(d.to_date) < getdate(d.from_date):
		frappe.throw(_("Please choose a valid period."))
	days = flt(d.days)
	if days <= 0:
		frappe.throw(_("Days must be more than zero."))
	employees = d.employees or []
	if not employees and not d.department and not cint(d.everyone):
		frappe.throw(_("Choose employees, a department, or everyone."))
	people = _targets(employees, d.department, d.company)
	plan = []
	for e in people:
		if e.date_of_joining and getdate(e.date_of_joining) > getdate(d.to_date):
			plan.append({"employee": e.name, "employee_name": e.employee_name, "action": "skip", "why": _("Joins after this period")})
			continue
		clash = frappe.db.get_value("Leave Allocation", {"employee": e.name, "leave_type": d.leave_type, "docstatus": 1,
														 "from_date": ["<=", d.to_date], "to_date": [">=", d.from_date]}, "name")
		plan.append({"employee": e.name, "employee_name": e.employee_name, "action": "skip" if clash else "create",
					 "why": _("Already has {0}").format(clash) if clash else None})
	if cint(d.dry_run):
		return {"rows": plan, "create": sum(1 for p in plan if p["action"] == "create")}
	created, failed = [], []
	for p in plan:
		if p["action"] != "create":
			continue
		frappe.db.savepoint("alphax_alloc")
		try:
			doc = frappe.get_doc({"doctype": "Leave Allocation", "employee": p["employee"], "leave_type": d.leave_type,
								  "from_date": d.from_date, "to_date": d.to_date, "new_leaves_allocated": days,
								  "carry_forward": 1 if cint(d.carry_forward) else 0,
								  "description": (d.reason or _("Allocated by HR in AlphaX"))[:250]})
			doc.insert()
			doc.submit()
			created.append(doc.name)
		except Exception as exc:  # one employee must not stop the rest
			frappe.db.rollback(save_point="alphax_alloc")
			failed.append({"employee": p["employee"], "employee_name": p["employee_name"], "error": frappe.utils.strip_html(str(exc))[:300]})
			frappe.clear_messages()
	return {"created": created, "failed": failed, "skipped": [p for p in plan if p["action"] == "skip"]}


@frappe.whitelist(methods=["POST"])
def cancel(name: str):
	"""Cancel an allocation that has no approved leave against it."""
	require_hr_manager()
	doc = frappe.get_doc("Leave Allocation", name)
	if doc.docstatus != 1:
		frappe.throw(_("Only active allocations can be cancelled."))
	doc.cancel()
	return {"ok": True}
