"""Monthly attendance register, lateness and overtime for HR (Saudi Labor Law, Art. 107)."""
from __future__ import annotations

from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import add_days, get_datetime, get_first_day, get_last_day, getdate, nowdate

from alphax_hr.api import shifts as sh
from alphax_hr.api._common import require_hr
from alphax_hr.api._wages import wages
from alphax_hr.saudi import attendance as rules

CODES_LEGEND = {
	rules.PRESENT: "Present", rules.ABSENT: "Absent", rules.LEAVE: "On leave", rules.HALF_DAY: "Half day",
	rules.WFH: "Work from home", rules.HOLIDAY: "Holiday / weekly off", rules.MISSING_PUNCH: "Missing punch",
	rules.NOT_MARKED: "Not marked yet",
}


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
	days = [getdate(add_days(start, i)) for i in range((end - start).days + 1)]
	rows = []
	for e in emps:
		cells, totals = [], defaultdict(float)
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
			late = early = 0
			ot = 0.0
			st = types.get(shift) if shift else None
			worked = day_logs.hours if day_logs else 0.0
			if st and day_logs and code in (rules.PRESENT, rules.HALF_DAY, rules.MISSING_PUNCH):
				s, en = rules.shift_window(d, _time(st.start_time), _time(st.end_time))
				late = rules.late_minutes(s, day_logs.first_in, int(st.late_entry_grace_period or 0))
				early = rules.early_minutes(en, day_logs.last_out, int(st.early_exit_grace_period or 0)) if not day_logs.missing_punch else 0
				ot = rules.overtime_hours(worked, (en - s).total_seconds() / 3600)
			elif holiday and day_logs and worked:
				ot = round(worked, 2)  # work on a rest day / public holiday is all overtime
			if att and att.late_entry and not late:
				late = int(st.late_entry_grace_period or 0) + 1 if st else 1  # marked late by HRMS
			totals[code] += 1
			totals["late_count"] += 1 if late else 0
			totals["late_minutes"] += late
			totals["early_count"] += 1 if early else 0
			totals["early_minutes"] += early
			totals["overtime_hours"] += ot
			totals["worked_hours"] += worked
			cells.append({"date": str(d), "code": code, "shift": shift, "late": late, "early": early,
						  "overtime": ot, "hours": worked, "leave": leaves.get(e.name, {}).get(d),
						  "holiday": holiday, "first_in": str(day_logs.first_in) if day_logs and day_logs.first_in else None,
						  "last_out": str(day_logs.last_out) if day_logs and day_logs.last_out else None})
		rows.append({"employee": e.name, "employee_name": e.employee_name, "department": e.department,
					 "cells": cells, "totals": {k: round(v, 2) for k, v in totals.items()}})
	return {"month": str(start), "start": str(start), "end": str(end), "dates": [str(d) for d in days], "rows": rows,
			"legend": {k: _(v) for k, v in CODES_LEGEND.items()}}


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
