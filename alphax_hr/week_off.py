"""Per-employee week-offs on top of HRMS holiday lists.

HRMS already lets each employee have their own Holiday List, and leave day
counts, auto attendance and payroll payment days all read it. A roster
week-off therefore becomes a weekly-off row in the employee's *personal*
list. The personal list starts as a copy of the employee's current list, and
public holidays added to that base list later are copied across on save.
"""
from __future__ import annotations

from datetime import date, timedelta

import frappe
from frappe import _
from frappe.utils import getdate

WEEK_OFF_TEXT = "Week off"


def dates_for(weekdays, start: date, end: date):
	"""Dates in [start, end] whose weekday (0=Mon .. 6=Sun) is chosen."""
	chosen = {int(w) for w in weekdays}
	d = start
	while d <= end:
		if d.weekday() in chosen:
			yield d
		d += timedelta(days=1)


def base_list(emp):
	return emp.holiday_list or frappe.get_cached_value("Company", emp.company, "default_holiday_list")


def personal_list(employee: str):
	"""The employee's personal Holiday List, created from their current list when missing."""
	emp = frappe.db.get_value("Employee", employee, ["name", "employee_name", "company", "holiday_list"], as_dict=True)
	current = base_list(emp)
	if not current:
		frappe.throw(_("{0} has no holiday list (and the company has no default).").format(emp.employee_name))
	if frappe.db.get_value("Holiday List", current, "alphax_employee") == employee:
		return frappe.get_doc("Holiday List", current)
	src = frappe.get_doc("Holiday List", current)
	name = f"{src.name} · {employee}"[:140]
	if frappe.db.exists("Holiday List", name):
		doc = frappe.get_doc("Holiday List", name)
	else:
		doc = frappe.get_doc({
			"doctype": "Holiday List", "holiday_list_name": name, "from_date": src.from_date, "to_date": src.to_date,
			"alphax_employee": employee, "alphax_base_list": src.name,
			"holidays": [{"holiday_date": h.holiday_date, "description": h.description, "weekly_off": h.weekly_off}
						 for h in src.holidays],
		})
		doc.insert(ignore_permissions=True)
	frappe.db.set_value("Employee", employee, "holiday_list", doc.name)
	return doc


def set_week_offs(employee: str, weekdays, start, end, replace=True):
	"""Make the chosen weekdays the employee's week-offs between start and end."""
	start, end = getdate(start), getdate(end)
	doc = personal_list(employee)
	beyond_base = _extend(doc, start, end)
	public = {getdate(h.holiday_date) for h in doc.holidays if not h.weekly_off}
	if replace:  # drop the old week-offs in the range, keep public holidays
		doc.holidays = [h for h in doc.holidays if not (h.weekly_off and start <= getdate(h.holiday_date) <= end)]
	have = {getdate(h.holiday_date) for h in doc.holidays}
	added = 0
	for d in dates_for(weekdays, start, end):
		if d not in have and d not in public:
			doc.append("holidays", {"holiday_date": d, "description": _(WEEK_OFF_TEXT), "weekly_off": 1})
			added += 1
	doc.holidays.sort(key=lambda h: getdate(h.holiday_date))
	doc.save(ignore_permissions=True)
	return {"employee": employee, "holiday_list": doc.name, "added": added, "beyond_company_list": beyond_base}


def _extend(doc, start, end):
	"""Grow the personal list to cover [start, end]. Returns True when that goes past the base (company) list,
	whose public holidays for those dates are therefore not known yet."""
	lo, hi = getdate(doc.from_date), getdate(doc.to_date)
	if start < lo:
		doc.from_date = start
	if end > hi:
		doc.to_date = end
	base = doc.get("alphax_base_list")
	if not base:
		return False
	b_lo, b_hi = (getdate(x) for x in frappe.db.get_value("Holiday List", base, ["from_date", "to_date"]))
	return start < b_lo or end > b_hi


def toggle_week_off(employee: str, day):
	"""Add or remove a single week-off day (public holidays are never removed here)."""
	day = getdate(day)
	doc = personal_list(employee)
	_extend(doc, day, day)
	row = next((h for h in doc.holidays if getdate(h.holiday_date) == day), None)
	if row and not row.weekly_off:
		frappe.throw(_("{0} is a public holiday.").format(day))
	if row:
		doc.holidays = [h for h in doc.holidays if h is not row]
		state = False
	else:
		doc.append("holidays", {"holiday_date": day, "description": _(WEEK_OFF_TEXT), "weekly_off": 1})
		doc.holidays.sort(key=lambda h: getdate(h.holiday_date))
		state = True
	doc.save(ignore_permissions=True)
	return {"employee": employee, "date": str(day), "off": state}


def sync_public_holidays(doc, method=None):
	"""Holiday List on_update: copy public holidays of a base list into its personal lists."""
	if doc.get("alphax_employee"):
		return
	public = {getdate(h.holiday_date): h.description for h in doc.holidays if not h.weekly_off}
	for name in frappe.get_all("Holiday List", filters={"alphax_base_list": doc.name}, pluck="name"):
		p = frappe.get_doc("Holiday List", name)
		lo, hi = getdate(p.from_date), getdate(p.to_date)
		rows = [h for h in p.holidays if h.weekly_off and getdate(h.holiday_date) not in public]
		rows += [frappe._dict(holiday_date=d, description=desc, weekly_off=0) for d, desc in public.items() if lo <= d <= hi]
		p.holidays = []
		for h in sorted(rows, key=lambda h: getdate(h.holiday_date)):
			p.append("holidays", {"holiday_date": h.holiday_date, "description": h.description, "weekly_off": h.weekly_off})
		p.save(ignore_permissions=True)
