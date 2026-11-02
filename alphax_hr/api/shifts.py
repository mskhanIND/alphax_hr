"""Shifts and roster for HR, inside /alphax. Built on HRMS Shift Type / Shift Assignment."""
from __future__ import annotations

from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import add_days, date_diff, getdate

from alphax_hr.api._common import parse_json, require_hr

MAX_DAYS = 62
MAX_ASSIGN = 500


def _employees(department=None, company=None, names=None):
	filters = {"status": "Active"}
	if department:
		filters["department"] = department
	if company:
		filters["company"] = company
	if names:
		filters["name"] = ["in", list(names)]
	return frappe.get_list("Employee", filters=filters, order_by="employee_name asc", page_length=5000,
						   fields=["name", "employee_name", "department", "designation", "default_shift",
								   "holiday_list", "company", "date_of_joining", "relieving_date"])


def shift_types_map():
	fields = ["name", "start_time", "end_time", "late_entry_grace_period", "early_exit_grace_period"]
	if frappe.get_meta("Shift Type").has_field("color"):
		fields.append("color")
	return {s.name: s for s in frappe.get_all("Shift Type", fields=fields)}


def assignments(employees, start, end):
	"""{employee: [(from, to|None, shift_type, name)]} of submitted, active assignments overlapping the range."""
	if not employees:
		return {}
	rows = frappe.get_all("Shift Assignment", filters={
		"employee": ["in", list(employees)], "docstatus": 1, "status": "Active", "start_date": ["<=", end]},
		or_filters=[["end_date", "is", "not set"], ["end_date", ">=", start]],
		fields=["name", "employee", "shift_type", "start_date", "end_date"], order_by="start_date asc")
	out = defaultdict(list)
	for r in rows:
		out[r.employee].append((getdate(r.start_date), getdate(r.end_date) if r.end_date else None, r.shift_type, r.name))
	return out


def shift_on(emp, day, assigned, default_shift):
	"""Assigned shift for the day (latest assignment wins), else the employee's default shift."""
	hit = None
	for start, end, shift, name in assigned.get(emp, ()):
		if start <= day and (end is None or end >= day):
			hit = (shift, name)
	return hit or (default_shift, None)


def holidays(employees, start, end):
	"""{holiday_list: {date: description}} for the lists these employees use (own list or company default)."""
	lists = {}
	for e in employees:
		hl = e.holiday_list or frappe.get_cached_value("Company", e.company, "default_holiday_list")
		e["_holiday_list"] = hl
		if hl:
			lists[hl] = {}
	if lists:
		for h in frappe.get_all("Holiday", filters={"parent": ["in", list(lists)], "holiday_date": ["between", [start, end]]},
								fields=["parent", "holiday_date", "description", "weekly_off"]):
			lists[h.parent][getdate(h.holiday_date)] = "weekly_off" if h.weekly_off else (h.description or "holiday")
	return lists


def approved_leaves(employees, start, end):
	"""{employee: {date: leave_type}} for approved leave in the range."""
	out = defaultdict(dict)
	if not employees:
		return out
	for la in frappe.get_all("Leave Application", filters={
			"employee": ["in", list(employees)], "status": "Approved", "docstatus": 1,
			"from_date": ["<=", end], "to_date": [">=", start]},
			fields=["employee", "from_date", "to_date", "leave_type"]):
		d = max(getdate(la.from_date), start)
		while d <= min(getdate(la.to_date), end):
			out[la.employee][d] = la.leave_type
			d = add_days(d, 1)
	return out


def _range(start, days):
	start = getdate(start)
	days = max(1, min(int(days or 7), MAX_DAYS))
	return start, add_days(start, days - 1), days


@frappe.whitelist()
def roster(start, days=7, department=None, company=None):
	"""Employees x days: shift, leave and holidays, for the roster grid."""
	require_hr()
	start, end, days = _range(start, days)
	emps = _employees(department, company)
	ids = [e.name for e in emps]
	assigned = assignments(ids, start, end)
	hols = holidays(emps, start, end)
	leaves = approved_leaves(ids, start, end)
	dates = [add_days(start, i) for i in range(days)]
	rows = []
	for e in emps:
		cells = []
		for d in dates:
			d = getdate(d)
			shift, assignment = shift_on(e.name, d, assigned, e.default_shift)
			cells.append({"date": str(d), "shift": shift, "assignment": assignment,
						  "leave": leaves.get(e.name, {}).get(d),
						  "holiday": hols.get(e._holiday_list, {}).get(d)})
		rows.append({"employee": e.name, "employee_name": e.employee_name, "department": e.department,
					 "designation": e.designation, "default_shift": e.default_shift, "cells": cells})
	types = shift_types_map()
	return {"start": str(start), "end": str(end), "dates": [str(d) for d in dates], "rows": rows,
			"shift_types": [{"name": n, "start_time": str(s.start_time), "end_time": str(s.end_time),
							 "color": s.get("color")} for n, s in sorted(types.items())]}


@frappe.whitelist()
def assign(employees, shift_type, start_date, end_date=None):
	"""Create and submit Shift Assignments. HRMS refuses overlapping ones; those are reported per employee."""
	require_hr()
	names = parse_json(employees, [])
	if not names or not isinstance(names, list):
		frappe.throw(_("Choose at least one employee."))
	if len(names) > MAX_ASSIGN:
		frappe.throw(_("Assign at most {0} employees at a time.").format(MAX_ASSIGN))
	if not frappe.db.exists("Shift Type", shift_type):
		frappe.throw(_("Unknown shift type."))
	start = getdate(start_date)
	end = getdate(end_date) if end_date else None
	if end and date_diff(end, start) < 0:
		frappe.throw(_("End date is before the start date."))
	created, failed = [], []
	companies = {e.name: e.company for e in _employees(names=names)}
	for emp in names:
		if emp not in companies:
			failed.append({"employee": emp, "error": _("Not an active employee you can access.")})
			continue
		frappe.db.savepoint("alphax_shift")
		try:
			doc = frappe.get_doc({"doctype": "Shift Assignment", "employee": emp, "shift_type": shift_type,
								  "company": companies[emp], "start_date": start, "end_date": end, "status": "Active"})
			doc.insert()
			doc.submit()
			created.append(doc.name)
		except Exception as exc:
			frappe.db.rollback(save_point="alphax_shift")
			frappe.clear_messages()
			failed.append({"employee": emp, "error": str(exc)[:300]})
	return {"created": created, "failed": failed}


@frappe.whitelist()
def end_assignment(name, end_date=None):
	"""Stop an assignment (from a date) instead of deleting history."""
	require_hr()
	doc = frappe.get_doc("Shift Assignment", name)
	doc.check_permission("cancel")
	end = getdate(end_date) if end_date else None
	if end and end >= getdate(doc.start_date):
		doc.end_date = end  # editable after submit; HRMS re-checks overlaps
		doc.save()
	else:
		doc.cancel()
	return {"name": doc.name, "docstatus": doc.docstatus}


@frappe.whitelist()
def set_week_off(employees, weekdays, start_date, end_date, replace=1):
	"""Roster: chosen weekdays become week-offs for these employees in the date range."""
	require_hr()
	from alphax_hr import week_off

	names = parse_json(employees, [])
	days = [int(d) for d in parse_json(weekdays, [])]
	if not names or not days or any(d < 0 or d > 6 for d in days):
		frappe.throw(_("Choose employees and at least one weekday."))
	if len(names) > MAX_ASSIGN:
		frappe.throw(_("At most {0} employees at a time.").format(MAX_ASSIGN))
	allowed = {e.name for e in _employees(names=names)}
	done, failed = [], []
	for emp in names:
		if emp not in allowed:
			failed.append({"employee": emp, "error": _("Not an active employee you can access.")})
			continue
		frappe.db.savepoint("alphax_weekoff")
		try:
			done.append(week_off.set_week_offs(emp, days, start_date, end_date, replace=bool(int(replace))))
		except Exception as exc:
			frappe.db.rollback(save_point="alphax_weekoff")
			frappe.clear_messages()
			failed.append({"employee": emp, "error": str(exc)[:300]})
	return {"done": done, "failed": failed}


@frappe.whitelist()
def toggle_week_off(employee, date):
	require_hr()
	from alphax_hr import week_off

	if employee not in {e.name for e in _employees(names=[employee])}:
		frappe.throw(_("Not an active employee you can access."), frappe.PermissionError)
	return week_off.toggle_week_off(employee, date)
