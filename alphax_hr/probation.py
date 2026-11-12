"""Probation: who is on it, when it ends, reminders, and the decision (confirm, extend, not confirmed).

Saudi Labour Law (Art. 53): probation up to 180 days, agreed in writing; it can be extended by written agreement as long
as the total stays within 180 days. Eid al-Fitr and Eid al-Adha holidays and sick leave are not counted, so the period
moves by those days: AlphaX suggests the adjusted end date and HR applies it.
"""
from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import add_days, cint, date_diff, getdate, nowdate

MAX_DAYS = 180
REMIND = (30, 7)
STATUSES = ("On probation", "Extended", "Confirmed", "Not confirmed")
OPEN = ("", None, "On probation", "Extended")


def _has_fields():
	return frappe.get_meta("Employee").has_field("alphax_probation_status")


def _excluded_days(emp, start, end):
	"""Eid holidays and approved sick leave inside the probation period (they do not count)."""
	days = set()
	hl = frappe.db.get_value("Employee", emp, "holiday_list") or frappe.db.get_value(
		"Company", frappe.db.get_value("Employee", emp, "company"), "default_holiday_list")
	if hl:
		for h in frappe.get_all("Holiday", filters={"parent": hl, "holiday_date": ["between", [start, end]], "weekly_off": 0},
								fields=["holiday_date", "description"]):
			text = (h.description or "").lower()
			if "eid" in text or "عيد" in text or "fitr" in text or "adha" in text:
				days.add(getdate(h.holiday_date))
	sick = [n for n in frappe.get_all("Leave Type", pluck="name") if "sick" in n.lower() or "مرض" in n]
	if sick:
		for la in frappe.get_all("Leave Application", filters={"employee": emp, "docstatus": 1, "status": "Approved",
																 "leave_type": ["in", sick], "from_date": ["<=", end],
																 "to_date": [">=", start]}, fields=["from_date", "to_date"]):
			d = max(getdate(la.from_date), getdate(start))
			while d <= min(getdate(la.to_date), getdate(end)):
				days.add(d)
				d = add_days(d, 1)
	return days


def suggested_end(emp, join, end):
	"""The planned end moved by the days that do not count (repeated, since the moved period can hold more of them)."""
	if not (join and end):
		return None, 0
	join, end = getdate(join), getdate(end)
	extra, current = 0, end
	for _i in range(5):
		n = len(_excluded_days(emp, join, current))
		if n == extra:
			break
		extra, current = n, add_days(end, n)
	return current, extra


def rows(scope_employees=None):
	if not _has_fields():
		return []
	filters = {"status": "Active", "alphax_probation_end_date": ["is", "set"]}
	if scope_employees is not None:
		filters["name"] = ["in", list(scope_employees) or [""]]
	today = getdate(nowdate())
	out = []
	for e in frappe.get_all("Employee", filters=filters, fields=[
			"name", "employee_name", "department", "designation", "date_of_joining", "reports_to", "image",
			"alphax_probation_end_date", "alphax_probation_status", "alphax_probation_decided_on", "alphax_probation_note"]):
		status = e.alphax_probation_status or ("On probation" if getdate(e.alphax_probation_end_date) >= add_days(today, -60) else "")
		if not status:
			continue  # an old end date with no decision recorded: treated as history, not a task
		end = getdate(e.alphax_probation_end_date)
		left = date_diff(end, today)
		sug, extra = suggested_end(e.name, e.date_of_joining, end) if status in ("On probation", "Extended") else (None, 0)
		used = date_diff(end, e.date_of_joining) + 1 if e.date_of_joining else None
		out.append({"employee": e.name, "employee_name": e.employee_name, "department": e.department, "designation": e.designation,
					"date_of_joining": str(e.date_of_joining) if e.date_of_joining else None, "end": str(end), "days_left": left,
					"status": status, "decided_on": str(e.alphax_probation_decided_on) if e.alphax_probation_decided_on else None,
					"note": e.alphax_probation_note, "image": e.image,
					"manager": frappe.db.get_value("Employee", e.reports_to, "employee_name") if e.reports_to else None,
					"overdue": status in ("On probation", "Extended") and left < 0,
					"ending_soon": status in ("On probation", "Extended") and 0 <= left <= 30,
					"suggested_end": str(sug) if sug and sug != end else None, "excluded_days": extra, "length_days": used,
					"max_end": str(add_days(e.date_of_joining, MAX_DAYS - 1 + extra)) if e.date_of_joining else None})
	return sorted(out, key=lambda r: (r["status"] not in ("On probation", "Extended"), r["days_left"]))


def _team():
	"""Employees whose probation the current user may see and decide: HR all, a manager their reports."""
	from alphax_hr.api._common import current_employee, is_hr

	if is_hr():
		return None
	me = current_employee(required=False)
	if not me:
		frappe.throw(_("Not permitted."), frappe.PermissionError)
	return frappe.get_all("Employee", filters={"reports_to": me, "status": "Active"}, pluck="name")


@frappe.whitelist()
def overview():
	scope = _team()
	data = rows(scope)
	return {"rows": data, "counts": {
		"open": sum(1 for r in data if r["status"] in ("On probation", "Extended")),
		"ending_soon": sum(1 for r in data if r["ending_soon"]), "overdue": sum(1 for r in data if r["overdue"]),
		"extended": sum(1 for r in data if r["status"] == "Extended"),
		"confirmed": sum(1 for r in data if r["status"] == "Confirmed")}, "max_days": MAX_DAYS, "is_hr": scope is None}


@frappe.whitelist(methods=["POST"])
def decide(employee: str, decision: str, note: str | None = None, new_end: str | None = None):
	"""Confirm, extend (within 180 days counted from joining, plus days that do not count), or not confirmed."""
	scope = _team()
	if scope is not None and employee not in scope:
		frappe.throw(_("Only HR or the employee's manager can decide the probation."), frappe.PermissionError)
	if decision not in ("Confirmed", "Extended", "Not confirmed", "Adjust end"):
		frappe.throw(_("Unknown decision."))
	e = frappe.get_doc("Employee", employee)
	values = {}
	if decision in ("Extended", "Adjust end"):
		if not new_end:
			frappe.throw(_("Choose the new end date."))
		_sug, extra = suggested_end(employee, e.date_of_joining, new_end)
		limit = add_days(e.date_of_joining, MAX_DAYS - 1 + extra)
		if getdate(new_end) > getdate(limit):
			frappe.throw(_("Probation cannot be longer than {0} days (counted without Eid holidays and sick leave): the latest "
						   "end date is {1}.").format(MAX_DAYS, frappe.utils.format_date(limit)))
		if decision == "Extended" and getdate(new_end) <= getdate(e.alphax_probation_end_date):
			frappe.throw(_("An extension must end after the current end date."))
		values["alphax_probation_end_date"] = new_end
		if decision == "Extended":
			if not (note or "").strip():
				frappe.throw(_("Write the reason: an extension must be agreed with the employee in writing."))
			values["alphax_probation_status"] = "Extended"
	else:
		if decision == "Not confirmed" and not (note or "").strip():
			frappe.throw(_("Write the reason."))
		values["alphax_probation_status"] = decision
		values["alphax_probation_decided_on"] = nowdate()
	if note:
		values["alphax_probation_note"] = note.strip()[:1000]
	frappe.db.set_value("Employee", employee, values)
	text = {"Confirmed": _("Probation confirmed"), "Extended": _("Probation extended to {0}").format(new_end),
			"Not confirmed": _("Probation not confirmed"), "Adjust end": _("Probation end moved to {0}").format(new_end)}[decision]
	frappe.get_doc("Employee", employee).add_comment("Comment", f"{text}{': ' + note.strip() if note else ''}")
	return {"ok": True, "decision": decision}


def daily():
	"""Remind the manager and HR 30 and 7 days before the end, and once when it passed without a decision."""
	if not _has_fields():
		return
	from alphax_hr.api import alerts

	today = getdate(nowdate())
	for r in rows():
		if r["status"] not in ("On probation", "Extended"):
			continue
		left = r["days_left"]
		if left in REMIND:
			subject = _("Probation of {0} ends in {1} days").format(r["employee_name"], left)
		elif left == -1:
			subject = _("Probation of {0} ended yesterday without a decision").format(r["employee_name"])
		else:
			continue
		alerts.event("Probation ending", subject,
					 _("End date {0}. Confirm, extend (within {1} days in total) or record that it is not confirmed.").format(
						 frappe.utils.format_date(r["end"]), MAX_DAYS),
					 employee=r["employee"], url="/alphax/probation", doc=("Employee", r["employee"]),
					 tag=f"probation-{r['employee']}-{left}")
