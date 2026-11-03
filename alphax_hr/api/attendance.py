"""Monthly attendance register, lateness and overtime for HR (Saudi Labor Law, Art. 107)."""
from __future__ import annotations

from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import add_days, cint, get_datetime, get_first_day, get_last_day, getdate, nowdate

from alphax_hr.api import shifts as sh
from alphax_hr.api._common import require_hr
from alphax_hr.api._wages import wages
from alphax_hr.saudi import attendance as rules

CODES_LEGEND = {
	rules.PRESENT: "Present", rules.ABSENT: "Absent", rules.LEAVE: "On leave", rules.HALF_DAY: "Half day",
	rules.WFH: "Work from home", rules.HOLIDAY: "Holiday / weekly off", rules.MISSING_PUNCH: "Missing punch",
	rules.NOT_MARKED: "Not marked yet", "X": "Exempt",
}
EXEMPT = "X"


def _checkins(employees, start, end):
	"""{employee: {shift_date: [(time, IN/OUT)]}}. Overnight logs belong to the day their shift started."""
	out = defaultdict(lambda: defaultdict(list))
	if not employees:
		return out
	meta = frappe.get_meta("Employee Checkin")
	fields = ["employee", "time", "log_type"] + (["shift_start"] if meta.has_field("shift_start") else [])
	rows = frappe.get_all("Employee Checkin", filters={
		"employee": ["in", list(employees)],
		"time": ["between", [f"{start} 00:00:00", f"{add_days(end, 1)} 12:00:00"]]}, fields=fields, order_by="time asc")
	for r in rows:
		t = get_datetime(r.time)
		day = getdate(r.get("shift_start")) if r.get("shift_start") else t.date()
		if start <= day <= end and r.log_type in ("IN", "OUT"):
			out[r.employee][day].append((t, r.log_type))
	return out


def _attendance(employees, start, end):
	out = defaultdict(dict)
	if not employees:
		return out
	for a in frappe.get_all("Attendance", filters={
			"employee": ["in", list(employees)], "docstatus": 1, "attendance_date": ["between", [start, end]]},
			fields=["employee", "attendance_date", "status", "late_entry", "early_exit", "working_hours", "shift"]):
		out[a.employee][getdate(a.attendance_date)] = a
	return out


def month_data(month=None, department=None, company=None):
	"""Everything the register and overtime views need, computed once."""
	ref = getdate(month or nowdate())
	start, end = getdate(get_first_day(ref)), getdate(get_last_day(ref))
	today = getdate(nowdate())
	emps = sh._employees(department, company)
	ids = [e.name for e in emps]
	assigned = sh.assignments(ids, start, end)
	types = sh.shift_types_map()
	hols = sh.holidays(emps, start, end)
	leaves = sh.approved_leaves(ids, start, end)
	logs = _checkins(ids, start, end)
	marked = _attendance(ids, start, end)
	from alphax_hr.api.requests import excused as _excused

	permits = _excused(ids, start, end)
	from alphax_hr.api import attendance_policy

	policy = attendance_policy.resolve([dict(e) for e in emps])
	days = [getdate(add_days(start, i)) for i in range((end - start).days + 1)]
	rows = []
	for e in emps:
		cells, totals = [], defaultdict(float)
		pol = policy.get(e.name)
		joined = getdate(e.date_of_joining) if e.date_of_joining else None
		left = getdate(e.relieving_date) if e.relieving_date else None
		for d in days:
			if (joined and d < joined) or (left and d > left):
				cells.append({"date": str(d), "code": rules.FUTURE, "not_employed": True, "late": 0, "early": 0,
							  "overtime": 0, "hours": 0})
				continue
			shift, _assignment = sh.shift_on(e.name, d, assigned, e.default_shift)
			day_logs = rules.pair_logs(logs[e.name][d]) if logs[e.name].get(d) else None
			att = marked[e.name].get(d)
			holiday = hols.get(e._holiday_list, {}).get(d)
			code = rules.day_code(day=d, today=today, holiday=bool(holiday), attendance_status=att.status if att else None,
								  on_leave=d in leaves.get(e.name, {}), logs=day_logs)
			if pol and pol.single_punch_ok and code == rules.MISSING_PUNCH:
				code = rules.PRESENT
			if pol and pol.exempt and code in (rules.ABSENT, rules.MISSING_PUNCH, rules.NOT_MARKED, rules.HALF_DAY, rules.PRESENT):
				code = EXEMPT
			late = early = 0
			ot = 0.0
			st = types.get(shift) if shift else None
			worked = day_logs.hours if day_logs else 0.0
			late_grace = int(st.late_entry_grace_period or 0) if st else 0
			early_grace = int(st.early_exit_grace_period or 0) if st else 0
			if pol and str(pol.late_grace_minutes or '').strip() != '':
				late_grace = cint(pol.late_grace_minutes)
			if pol and str(pol.early_grace_minutes or '').strip() != '':
				early_grace = cint(pol.early_grace_minutes)
			if st and day_logs and code in (rules.PRESENT, rules.HALF_DAY, rules.MISSING_PUNCH):
				s, en = rules.shift_window(d, _time(st.start_time), _time(st.end_time))
				late = rules.late_minutes(s, day_logs.first_in, late_grace)
				early = rules.early_minutes(en, day_logs.last_out, early_grace) if not day_logs.missing_punch else 0
				ot = rules.overtime_hours(worked, (en - s).total_seconds() / 3600)
			elif st and day_logs and code == EXEMPT:
				s, en = rules.shift_window(d, _time(st.start_time), _time(st.end_time))
				ot = rules.overtime_hours(worked, (en - s).total_seconds() / 3600)
			elif holiday and day_logs and worked:
				ot = round(worked, 2)  # work on a rest day / public holiday is all overtime
			if att and att.late_entry and not late and code != EXEMPT:
				late = late_grace + 1 if st else 1  # marked late by HRMS
			permit = permits.get((e.name, d))
			late_excused = early_excused = 0
			if permit and late and permit.get("late"):
				allowed = _permit_minutes(d, st, permit["late"], start_side=True) if st else None
				late_excused = late if allowed is None else min(late, allowed)
				late -= late_excused
			if permit and early and permit.get("early"):
				allowed = _permit_minutes(d, st, permit["early"], start_side=False) if st else None
				early_excused = early if allowed is None else min(early, allowed)
				early -= early_excused
			totals[code] += 1
			totals["late_count"] += 1 if late else 0
			totals["late_minutes"] += late
			totals["early_count"] += 1 if early else 0
			totals["early_minutes"] += early
			totals["overtime_hours"] += ot
			totals["worked_hours"] += worked
			totals["excused_minutes"] += late_excused + early_excused
			cells.append({"date": str(d), "code": code, "shift": shift, "late": late, "early": early,
						  "late_excused": late_excused, "early_excused": early_excused,
						  "overtime": ot, "hours": worked, "leave": leaves.get(e.name, {}).get(d),
						  "holiday": holiday, "first_in": str(day_logs.first_in) if day_logs and day_logs.first_in else None,
						  "last_out": str(day_logs.last_out) if day_logs and day_logs.last_out else None})
		if pol and cint(pol.monthly_late_allowance):
			forgiven = attendance_policy.apply_allowance([c for c in cells if not c.get("not_employed")], pol.monthly_late_allowance)
			if forgiven:
				totals["late_minutes"] -= forgiven
				totals["late_allowance_used"] = forgiven
				totals["late_count"] = sum(1 for c in cells if c.get("late"))
		rows.append({"employee": e.name, "employee_name": e.employee_name, "department": e.department,
					 "policy": pol.policy_name if pol else None, "no_penalties": bool(pol and (pol.no_penalties or pol.exempt)),
					 "cells": cells, "totals": {k: round(v, 2) for k, v in totals.items()}})
	return {"month": str(start), "start": str(start), "end": str(end), "dates": [str(d) for d in days], "rows": rows,
			"legend": {k: _(v) for k, v in CODES_LEGEND.items()}}


def _permit_minutes(day, st, permitted, start_side):
	"""Minutes a permission covers: shift start -> expected arrival, or leaving time -> shift end. None = whole."""
	if permitted is True:
		return None
	try:
		s, en = rules.shift_window(day, _time(st.start_time), _time(st.end_time))
		hh, mm = (int(x) for x in str(permitted).split(":")[:2])
		at = s.replace(hour=hh, minute=mm, second=0)
		if not start_side and at < s:
			at = at + __import__("datetime").timedelta(days=1)  # night shift
		minutes = (at - s).total_seconds() / 60 if start_side else (en - at).total_seconds() / 60
		return max(int(minutes), 0)
	except Exception:  # noqa: BLE001 - a bad time never blocks the register
		return None


def _time(value):
	from datetime import datetime, time, timedelta

	if isinstance(value, timedelta):
		return (datetime.min + value).time()
	if isinstance(value, time):
		return value
	return datetime.strptime(str(value), "%H:%M:%S").time()


@frappe.whitelist()
def register(month=None, department=None, company=None):
	require_hr()
	return month_data(month, department, company)


@frappe.whitelist()
def overtime(month=None, department=None, company=None, daily_hours=None):
	"""Overtime per employee for the month with the Art. 107 amount (wage from payslips/salary)."""
	require_hr()
	data = month_data(month, department, company)
	ids = [r["employee"] for r in data["rows"] if r["totals"].get("overtime_hours")]
	pay = wages(ids, getdate(data["start"]), getdate(data["end"])) if ids else {}
	hours_per_day = float(daily_hours or rules.DEFAULT_DAILY_HOURS)
	out = []
	for r in data["rows"]:
		hours = r["totals"].get("overtime_hours", 0)
		if not hours:
			continue
		w = pay.get(r["employee"], {})
		wage, basic = w.get("eosb_wage") or 0, w.get("basic") or 0
		out.append({"employee": r["employee"], "employee_name": r["employee_name"], "department": r["department"],
					"hours": hours, "days": [c["date"] for c in r["cells"] if c["overtime"]],
					"monthly_wage": wage, "monthly_basic": basic,
					"amount": rules.overtime_pay(hours, wage, basic, hours_per_day) if wage else None,
					"warning": None if wage else _("No wage found: map salary components in AlphaX HR Settings.")})
	return {"month": data["month"], "daily_hours": hours_per_day, "rows": out,
			"total_hours": round(sum(r["hours"] for r in out), 2),
			"total_amount": round(sum(r["amount"] or 0 for r in out), 2)}


@frappe.whitelist()
def export_register(month=None, department=None, company=None, file_format="xlsx"):
	require_hr()
	data = month_data(month, department, company)
	header = [_("Employee ID"), _("Employee"), _("Department")] + [d[-2:] for d in data["dates"]] + [
		_("Present"), _("Absent"), _("Leave"), _("Late (times)"), _("Late (minutes)"), _("Missing punch"), _("Overtime (hours)")]
	table = [header]
	for r in data["rows"]:
		t = r["totals"]
		table.append([r["employee"], r["employee_name"], r["department"] or ""] + [c["code"] for c in r["cells"]] + [
			t.get(rules.PRESENT, 0), t.get(rules.ABSENT, 0), t.get(rules.LEAVE, 0), t.get("late_count", 0),
			t.get("late_minutes", 0), t.get(rules.MISSING_PUNCH, 0), t.get("overtime_hours", 0)])
	table.append([])
	table.append([_("Legend")] + [f"{k} = {v}" for k, v in data["legend"].items()])
	name = f"attendance-{data['month'][:7]}"
	if file_format == "csv":
		from frappe.utils.csvutils import to_csv

		frappe.response["filecontent"] = to_csv(table).encode("utf-8-sig")
		frappe.response["filename"] = name + ".csv"
	else:
		from frappe.utils.xlsxutils import make_xlsx

		frappe.response["filecontent"] = make_xlsx(table, "Attendance").getvalue()
		frappe.response["filename"] = name + ".xlsx"
	frappe.response["type"] = "binary"


# ------------------------------------------------------------------ live movements
def _monitor_scope(user, department=None):
	from alphax_hr.api._common import is_hr

	filters = {"status": "Active"}
	if department:
		filters["department"] = department
	if is_hr(user):
		return frappe.get_all("Employee", filters=filters, fields=["name", "employee_name", "department", "designation", "image", "company"])
	me = frappe.db.get_value("Employee", {"user_id": user}, "name")
	or_filters = {"leave_approver": user}
	if me:
		or_filters["reports_to"] = me
	rows = frappe.get_all("Employee", filters=filters, or_filters=or_filters, fields=["name", "employee_name", "department", "designation", "image", "company"])
	if not rows:
		frappe.throw(_("Only HR and managers can see check-ins."), frappe.PermissionError)
	return rows


@frappe.whitelist()
def live(date=None, department=None):
	"""Today's (or a day's) check-ins with locations: who is in, out, not in yet or on leave, and punches outside work locations."""
	user = frappe.session.user
	day = getdate(date or nowdate())
	emps = _monitor_scope(user, department)
	ids = [e.name for e in emps]
	fields = ["employee", "time", "log_type", "latitude", "longitude"]
	if frappe.get_meta("Employee Checkin").has_field("alphax_location"):
		fields += ["alphax_location", "alphax_distance_m", "alphax_outside", "alphax_source"]
	logs = defaultdict(list)
	for r in frappe.get_all("Employee Checkin", filters={"employee": ["in", ids or [""]], "time": ["between", [f"{day} 00:00:00", f"{day} 23:59:59"]]},
							fields=fields, order_by="time asc"):
		logs[r.employee].append({**r, "time": str(r.time)})
	on_leave = {r.employee: r.leave_type for r in frappe.get_all("Leave Application", filters={
		"employee": ["in", ids or [""]], "docstatus": 1, "status": "Approved", "from_date": ["<=", day], "to_date": [">=", day]},
		fields=["employee", "leave_type"])}
	rows = []
	for e in emps:
		p = logs.get(e.name, [])
		state = "on_leave" if e.name in on_leave else ("in" if p and p[-1]["log_type"] == "IN" else "out" if p else "not_in")
		rows.append({**e, "state": state, "leave_type": on_leave.get(e.name), "punches": p,
					 "first_in": next((x["time"] for x in p if x["log_type"] == "IN"), None),
					 "last_out": next((x["time"] for x in reversed(p) if x["log_type"] == "OUT"), None),
					 "outside": sum(1 for x in p if x.get("alphax_outside")), "no_location": sum(1 for x in p if not x.get("latitude"))})
	rows.sort(key=lambda r: ({"in": 0, "out": 1, "not_in": 2, "on_leave": 3}[r["state"]], r["employee_name"] or ""))
	summary = {k: sum(1 for r in rows if r["state"] == k) for k in ("in", "out", "not_in", "on_leave")}
	summary["outside"] = sum(1 for r in rows if r["outside"])
	return {"date": str(day), "rows": rows, "summary": summary,
			"departments": sorted({e.department for e in emps if e.department}),
			"locations": frappe.get_all("AlphaX Work Location", filters={"enabled": 1}, fields=["name", "latitude", "longitude", "radius_m"])
			if frappe.db.exists("DocType", "AlphaX Work Location") else []}


@frappe.whitelist()
def work_locations():
	require_hr()
	return frappe.get_all("AlphaX Work Location", fields=["name", "location_name", "enabled", "company", "address", "latitude", "longitude", "radius_m"],
						  order_by="location_name asc")


@frappe.whitelist(methods=["POST"])
def save_work_location(data, name=None):
	from alphax_hr.api._common import parse_json, require_hr_manager

	require_hr_manager()
	d = parse_json(data, {}) or {}
	doc = frappe.get_doc("AlphaX Work Location", name) if name else frappe.new_doc("AlphaX Work Location")
	if not name:
		doc.location_name = (d.get("location_name") or "").strip()
	for k in ("enabled", "company", "address", "latitude", "longitude", "radius_m"):
		if k in d:
			doc.set(k, d[k] if d[k] != "" else None)
	from frappe.utils import flt as _flt

	if not (-90 <= _flt(doc.latitude) <= 90 and -180 <= _flt(doc.longitude) <= 180) or (not _flt(doc.latitude) and not _flt(doc.longitude)):
		frappe.throw(_("Enter a valid latitude and longitude (e.g. 24.7136, 46.6753)."))
	if (doc.radius_m or 0) < 20:
		frappe.throw(_("The radius must be at least 20 metres (phone GPS is not more precise)."))
	doc.save()
	return {"name": doc.name}


@frappe.whitelist(methods=["POST"])
def delete_work_location(name):
	from alphax_hr.api._common import require_hr_manager

	require_hr_manager()
	frappe.delete_doc("AlphaX Work Location", name)
	return {"ok": True}
