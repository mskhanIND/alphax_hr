"""Turn punches into HRMS Attendance, so payroll, leave and HRMS reports see the same days as AlphaX's register.

Only employees whose attendance comes from punches are marked: they have an attendance device ID or punched in the
last 30 days. For each past day the register's result becomes a submitted Attendance:

* present → Present (late entry / early exit flagged); fewer hours than the shift's half-day threshold → Half Day,
  fewer than its absent threshold → Absent;
* no punch on a working day → Absent (when "Mark absent days" is on);
* missing punch → left unmarked while it can still be corrected (attendance request), then Half Day;
* leave, holidays, exempt employees, today and future days → not touched (HRMS marks approved leave itself).

Attendance HR or an attendance request created is never changed. Attendance AlphaX created is corrected when punches
arrive late (a device that was offline): the old record is cancelled and a new one submitted, with a comment.
"""
from __future__ import annotations

from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import add_days, cint, flt, get_first_day, getdate, nowdate

from alphax_hr.saudi import attendance as rules

LOG = "AlphaX Attendance Mark"


def _conf():
	c = frappe.get_cached_doc("AlphaX HR Settings")
	return frappe._dict(enabled=cint(c.get("mark_attendance")) if c.get("mark_attendance") is not None else 1,
						absent=cint(c.get("mark_absent")) if c.get("mark_absent") is not None else 1,
						window=max(cint(c.get("attendance_recheck_days")) or 7, 1))


def punch_employees(names=None):
	"""Employees whose attendance comes from punches."""
	filters = {"status": "Active"}
	if names:
		filters["name"] = ["in", list(names)]
	with_id = set(frappe.get_all("Employee", filters={**filters, "attendance_device_id": ["is", "set"]}, pluck="name"))
	since = add_days(nowdate(), -30)
	punched = set(frappe.get_all("Employee Checkin", filters={"time": [">=", since], **({"employee": ["in", list(names)]} if names else {})},
								 pluck="employee", distinct=True))
	active = set(frappe.get_all("Employee", filters=filters, pluck="name"))
	return sorted((with_id | punched) & active)


def decide(cell, shift_type, conf, today, window):
	"""(status, late_entry, early_exit) for one register cell, or None to leave the day alone."""
	code, d = cell["code"], getdate(cell["date"])
	if cell.get("not_employed") or d >= today:
		return None
	if code == rules.PRESENT:
		hours = flt(cell.get("hours"))
		if shift_type and flt(shift_type.get("working_hours_threshold_for_absent")) and hours and \
				hours < flt(shift_type.working_hours_threshold_for_absent):
			return ("Absent", 0, 0) if conf.absent else None
		if shift_type and flt(shift_type.get("working_hours_threshold_for_half_day")) and hours and \
				hours < flt(shift_type.working_hours_threshold_for_half_day):
			return ("Half Day", cint(bool(cell.get("late"))), cint(bool(cell.get("early"))))
		return ("Present", cint(bool(cell.get("late"))), cint(bool(cell.get("early"))))
	if code == rules.ABSENT:
		return ("Absent", 0, 0) if conf.absent else None
	if code == rules.MISSING_PUNCH:
		# still correctable inside the window; after it, a lone punch counts as half a day
		return ("Half Day", cint(bool(cell.get("late"))), 0) if (today - d).days > window else None
	return None


def _existing(employees, start, end):
	out = {}
	for a in frappe.get_all("Attendance", filters={"employee": ["in", employees], "docstatus": 1,
												   "attendance_date": ["between", [start, end]]},
							fields=["name", "employee", "attendance_date", "status", "late_entry", "early_exit",
									"attendance_request", "leave_application"]):
		out[(a.employee, getdate(a.attendance_date))] = a
	return out


def _ours():
	return {r.attendance: r for r in frappe.get_all(LOG, filters={"active": 1}, fields=["name", "attendance", "employee", "attendance_date"])} \
		if frappe.db.exists("DocType", LOG) else {}


def _submit(employee, day, status, late, early, shift, company):
	a = frappe.get_doc({"doctype": "Attendance", "employee": employee, "attendance_date": day, "status": status,
						"late_entry": late, "early_exit": early, "shift": shift, "company": company})
	a.flags.ignore_permissions = True
	a.insert()
	a.submit()
	frappe.get_doc({"doctype": LOG, "attendance": a.name, "employee": employee, "attendance_date": day, "status": status,
					"active": 1}).insert(ignore_permissions=True)
	return a.name


def mark(employees=None, start=None, end=None):
	"""Mark the days from ``start`` to ``end`` (default: the re-check window up to yesterday). Returns counts."""
	conf = _conf()
	counts = defaultdict(int)
	if not conf.enabled or not frappe.db.exists("DocType", LOG):
		return dict(counts)
	from alphax_hr.api import shifts as sh
	from alphax_hr.api.attendance import month_data

	today = getdate(nowdate())
	end = min(getdate(end or add_days(today, -1)), getdate(add_days(today, -1)))
	start = getdate(start or add_days(end, -(conf.window - 1)))
	emps = punch_employees(employees)
	if not emps or start > end:
		return dict(counts)
	company = {e.name: e.company for e in frappe.get_all("Employee", filters={"name": ["in", emps]}, fields=["name", "company"])}
	types = sh.shift_types_map()
	existing, ours = _existing(emps, start, end), _ours()
	month = getdate(get_first_day(start))
	while month <= end:
		data = month_data(str(month), employees=emps, ignore_attendance=set(ours))
		for row in data["rows"]:
			emp = row["employee"]
			for cell in row["cells"]:
				d = getdate(cell["date"])
				if not start <= d <= end:
					continue
				want = decide(cell, types.get(cell.get("shift")) if cell.get("shift") else None, conf, today, conf.window)
				have = existing.get((emp, d))
				if not want:
					counts["left"] += 1
					continue
				if have and (have.name not in ours or have.attendance_request or have.leave_application):
					counts["kept"] += 1  # HR, an attendance request or leave marked it
					continue
				if have and (have.status, cint(have.late_entry), cint(have.early_exit)) == want:
					counts["unchanged"] += 1
					continue
				frappe.db.savepoint("alphax_mark")
				try:
					if have:  # ours, and the day changed (late punches): replace it
						old = frappe.get_doc("Attendance", have.name)
						old.flags.ignore_permissions = True
						old.add_comment("Comment", _("Replaced by AlphaX: punches changed this day to {0}.").format(_(want[0])))
						old.cancel()
						frappe.db.set_value(LOG, ours[have.name].name, "active", 0, update_modified=False)
						counts["corrected"] += 1
					else:
						counts["marked"] += 1
					_submit(emp, d, want[0], want[1], want[2], cell.get("shift"), company.get(emp))
				except Exception as exc:  # noqa: BLE001
					frappe.db.rollback(save_point="alphax_mark")
					frappe.clear_messages()
					counts["errors"] += 1
					frappe.log_error(title=f"AlphaX attendance marking: {emp} {d}", message=str(exc))
		month = getdate(add_days(frappe.utils.get_last_day(month), 1))
	return dict(counts)


def daily():
	"""Scheduled early morning: mark yesterday and re-check the window for late punches."""
	res = mark()
	frappe.cache().set_value("alphax:last_marking", {"at": str(frappe.utils.now_datetime()), **res})


def remark_later(pairs):
	"""After a device sends punches for earlier days: re-mark those employees (in the background, once)."""
	pairs = [(e, getdate(d)) for e, d in pairs if getdate(d) < getdate(nowdate())]
	if not pairs or not _conf().enabled or frappe.flags.alphax_no_remark:
		return
	emps = sorted({e for e, _ in pairs})
	start = min(d for _, d in pairs)
	frappe.enqueue("alphax_hr.attendance_marking.mark", queue="short", job_id=f"alphax-remark-{start}-{len(emps)}",
				   deduplicate=True, employees=emps, start=str(start), enqueue_after_commit=True)


@frappe.whitelist()
def status():
	"""HR: whether marking is on, the last run, and the days of the last week marked by AlphaX."""
	from alphax_hr.api._common import require_hr

	require_hr()
	conf = _conf()
	since = add_days(nowdate(), -7)
	by_status = frappe.get_all(LOG, filters={"active": 1, "attendance_date": [">=", since]}, fields=["status", "count(name) as n"],
							   group_by="status") if frappe.db.exists("DocType", LOG) else []
	return {"enabled": conf.enabled, "absent": conf.absent, "window": conf.window, "last": frappe.cache().get_value("alphax:last_marking"),
			"week": {r.status: r.n for r in by_status}, "employees": len(punch_employees())}


@frappe.whitelist(methods=["POST"])
def mark_now(start: str | None = None, end: str | None = None):
	from alphax_hr.api._common import require_hr_manager

	require_hr_manager()
	res = mark(start=start, end=end)
	frappe.cache().set_value("alphax:last_marking", {"at": str(frappe.utils.now_datetime()), **res})
	return res
