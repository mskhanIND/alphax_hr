"""Attendance health: the problems that stop punches from becoming correct attendance, in go-live order, each with a fix.

Found on real migrations: national IDs kept in the device ID field, devices sending IN for every punch, double taps,
employees without a shift or holiday list, punches refused by a check another app added, unmatched device users.
"""
from __future__ import annotations

import re
from datetime import timedelta

import frappe
from frappe import _
from frappe.utils import add_days, cint, get_datetime, getdate, now_datetime, nowdate

from alphax_hr import devices as dv

OK, WARN, ERROR = "ok", "warn", "error"
NATIONAL_ID = re.compile(r"^[12]\d{9}$")
CORE_APPS = {"frappe", "erpnext", "hrms", "alphax_hr", "payments", "lending"}
DOUBLE_TAP_SECONDS = 60


def _row(rows, key, step, status, value, title, detail, fix=None, link=None):
	rows.append({"key": key, "step": step, "status": status, "value": value, "title": title,
				 "detail": detail if status != OK else None, "fix": fix if status != OK else None,
				 "link": link if status != OK else None})


def _punchers():
	from alphax_hr.attendance_marking import punch_employees

	return punch_employees()


# ------------------------------------------------------------------ individual checks (each returns affected records)
def national_id_in_device_id():
	"""Employees whose device ID is a national ID / Iqama while the Iqama field is empty."""
	if not frappe.get_meta("Employee").has_field("alphax_iqama_number"):
		return []
	rows = frappe.get_all("Employee", filters={"status": "Active", "attendance_device_id": ["is", "set"]},
						  fields=["name", "employee_name", "attendance_device_id", "alphax_iqama_number"])
	return [r for r in rows if NATIONAL_ID.match(str(r.attendance_device_id).strip()) and not r.alphax_iqama_number]


def duplicate_ids():
	"""The same device ID or Iqama on two active employees: punches can only go to one of them."""
	out = []
	for field, label in (("attendance_device_id", "Device ID"), ("alphax_iqama_number", "Iqama")):
		if not frappe.get_meta("Employee").has_field(field):
			continue
		for r in frappe.db.sql(f"""select `{field}` v, group_concat(name separator ', ') emps, count(*) n from tabEmployee
				where status='Active' and ifnull(`{field}`, '') != '' group by `{field}` having n > 1 limit 200""", as_dict=True):
			out.append({"field": label, "value": r.v, "employees": r.emps})
	return out


def all_in_sources(days=7):
	"""Connections / devices whose punches are nearly all IN: staff do not press the keys."""
	out = []
	since = add_days(nowdate(), -days)
	for r in frappe.db.sql("""select l.device, sum(l.log_type='IN') ins, sum(l.log_type='OUT') outs, count(*) n
			from `tabAlphaX Device Log` l where l.punch_time >= %s and l.status='Imported' group by l.device""", (since,), as_dict=True):
		if r.n < 20 or r.ins < 0.95 * r.n:
			continue
		d = frappe.db.get_value(dv.DEVICE, r.device, ["name", "device_name", "punch_rule", "source_device"], as_dict=True)
		if not d or (d.punch_rule or "").startswith("First IN"):
			continue
		owner = d.source_device or d.name
		if not any(o["device"] == owner for o in out):
			out.append({"device": owner, "device_name": frappe.db.get_value(dv.DEVICE, owner, "device_name"),
						"punches": r.n, "in_share": round(100 * r.ins / r.n)})
	return out


def double_taps(days=30):
	"""Check-ins of the same employee within a minute of the previous one (not yet set aside)."""
	since = add_days(nowdate(), -days)
	return frappe.db.sql("""select c.name, c.employee, c.time from `tabEmployee Checkin` c
		join `tabEmployee Checkin` p on p.employee = c.employee and p.time < c.time
			and timestampdiff(second, p.time, c.time) <= %s and ifnull(p.skip_auto_attendance, 0) = 0
		where c.time >= %s and ifnull(c.skip_auto_attendance, 0) = 0
		group by c.name limit 5000""", (DOUBLE_TAP_SECONDS, since), as_dict=True)


def without_shift():
	"""Punch employees with no active shift today and no default shift."""
	emps = _punchers()
	if not emps:
		return []
	today = getdate(nowdate())
	covered = set(frappe.get_all("Shift Assignment", filters={"employee": ["in", emps], "docstatus": 1, "status": "Active",
															   "start_date": ["<=", today]},
								 or_filters=[["end_date", "is", "not set"], ["end_date", ">=", today]], pluck="employee"))
	rows = frappe.get_all("Employee", filters={"name": ["in", [e for e in emps if e not in covered]]},
						  fields=["name", "employee_name", "default_shift", "department"])
	return [r for r in rows if not r.default_shift]


def without_holiday_list():
	emps = _punchers()
	if not emps:
		return []
	rows = frappe.get_all("Employee", filters={"name": ["in", emps], "holiday_list": ["is", "not set"]},
						  fields=["name", "employee_name", "company"])
	defaults = {c.name: c.default_holiday_list for c in frappe.get_all("Company", fields=["name", "default_holiday_list"])}
	return [r for r in rows if not defaults.get(r.company)]


def checkin_blockers():
	"""Rules added by other apps or server scripts that can refuse a check-in (e.g. 'no shift assignment')."""
	out = []
	if frappe.db.exists("DocType", "Server Script"):
		for s in frappe.get_all("Server Script", filters={"disabled": 0, "script_type": "DocType Event",
														   "reference_doctype": "Employee Checkin"},
								fields=["name", "doctype_event"]):
			out.append({"kind": "Server Script", "name": s.name, "when": s.doctype_event})
	hooks = frappe.get_hooks("doc_events") or {}
	for event, paths in (hooks.get("Employee Checkin") or {}).items():
		for path in (paths if isinstance(paths, list) else [paths]):
			app = str(path).split(".")[0]
			if app not in CORE_APPS and event in ("validate", "before_insert", "before_save"):
				out.append({"kind": "App", "name": path, "when": event})
	return out


def unmatched_users(days=30):
	since = add_days(nowdate(), -days)
	return frappe.db.sql("""select device_user, count(*) n from `tabAlphaX Device Log` where status='Unmatched'
		and punch_time >= %s group by device_user order by n desc limit 500""", (since,), as_dict=True)


def refused(days=60):
	since = add_days(nowdate(), -days)
	return frappe.db.sql("""select message, count(*) n from `tabAlphaX Device Log` where status='Error' and punch_time >= %s
		group by message order by n desc limit 20""", (since,), as_dict=True)


# ------------------------------------------------------------------ the list
def checks():
	rows = []
	now = now_datetime()
	sources = frappe.get_all(dv.DEVICE, filters={"enabled": 1, "connection": ["!=", dv.TERMINAL]},
							 fields=["name", "device_name", "connection", "last_contact", "failures", "last_error"])
	failing = [s for s in sources if cint(s.failures)]
	silent = [s for s in sources if not s.last_contact or get_datetime(s.last_contact) < now - timedelta(hours=24)]
	_row(rows, "connection", 1, ERROR if not sources or failing else WARN if silent else OK,
		 len(sources), _("Devices or attendance database connected"),
		 _("No device or attendance database is set up.") if not sources else
		 _("Not reachable: {0}").format(", ".join(f"{s.device_name} ({(s.last_error or '')[:80]})" for s in failing)) if failing else
		 _("No contact for 24 hours: {0}").format(", ".join(s.device_name for s in silent)), link="/attendance-devices")

	from alphax_hr.attendance_marking import _conf

	on = _conf().enabled
	_row(rows, "marking", 2, WARN if not on else OK, int(on), _("Attendance marked from punches"),
		 _("Punches are read but attendance is not marked from them."), fix="turn_on_marking")

	um = unmatched_users()
	_row(rows, "unmatched", 3, WARN if um else OK, len(um), _("Every device user matched to an employee"),
		 _("{0} device users with punches in the last 30 days are not linked to an employee.").format(len(um)), fix="match")

	nid = national_id_in_device_id()
	_row(rows, "national_id_in_device_id", 3, WARN if nid else OK, len(nid), _("National IDs kept in the right field"),
		 _("{0} employees have their national ID / Iqama in the Device ID field and an empty Iqama field. Copying it fills "
		   "the Iqama (the Device ID is kept).").format(len(nid)), fix="copy_iqama")

	dup = duplicate_ids()
	_row(rows, "duplicate_ids", 3, ERROR if dup else OK, len(dup), _("No two employees share a device ID or Iqama"),
		 "; ".join(f"{d['field']} {d['value']}: {d['employees']}" for d in dup[:5]) + (" …" if len(dup) > 5 else ""),
		 link="/people")

	allin = all_in_sources()
	_row(rows, "all_in", 4, WARN if allin else OK, len(allin), _("IN and OUT read correctly"),
		 _("Nearly every punch arrives as IN, so staff do not press the keys: {0}. Reading the day as first IN, last OUT "
		   "fixes check-outs and missing punches.").format(", ".join(f"{a['device_name']} ({a['in_share']}% IN)" for a in allin)),
		 fix="first_in_last_out")

	taps = double_taps()
	_row(rows, "double_taps", 4, WARN if taps else OK, len(taps), _("No double taps"),
		 _("{0} check-ins came within a minute of the previous one. Setting them aside keeps them on record but out of "
		   "attendance.").format(len(taps)), fix="skip_double_taps")

	ns = without_shift()
	_row(rows, "no_shift", 5, WARN if ns else OK, len(ns), _("Every punching employee has a shift"),
		 _("{0} employees punch but have no shift today and no default shift: late arrivals, half days and overtime cannot "
		   "be worked out.").format(len(ns)), fix="assign_shifts")

	nh = without_holiday_list()
	_row(rows, "no_holiday_list", 5, WARN if nh else OK, len(nh), _("Every punching employee has a holiday list"),
		 _("{0} employees have no holiday list (and their company has no default): weekends would count as absent.").format(len(nh)),
		 link="/holiday-lists")

	bl = checkin_blockers()
	_row(rows, "checkin_blockers", 6, WARN if bl else OK, len(bl), _("Nothing else refuses check-ins"),
		 _("These can refuse a check-in: {0}.").format(", ".join(f"{b['kind']} {b['name']} ({b['when']})" for b in bl)),
		 fix="disable_checkin_scripts" if any(b["kind"] == "Server Script" for b in bl) else None)

	rf = refused()
	n = sum(r.n for r in rf)
	_row(rows, "refused", 6, WARN if n else OK, n, _("No refused punches waiting"),
		 _("{0} punches were refused in the last 60 days. Most common: {1}").format(n, (rf[0].message or "")[:140] if rf else ""),
		 fix="retry")
	counts = {s: sum(1 for r in rows if r["status"] == s) for s in (OK, WARN, ERROR)}
	return {"checks": rows, "counts": counts, "as_of": str(now)}


# ------------------------------------------------------------------ API
def _hr():
	from alphax_hr.api._common import require_hr

	require_hr()


def _manager():
	from alphax_hr.api._common import require_hr_manager

	require_hr_manager()


@frappe.whitelist()
def overview():
	_hr()
	return checks()


@frappe.whitelist()
def details(key: str):
	"""The records behind one check."""
	_hr()
	fn = {"national_id_in_device_id": national_id_in_device_id, "duplicate_ids": duplicate_ids, "all_in": all_in_sources,
		  "no_shift": without_shift, "no_holiday_list": without_holiday_list, "checkin_blockers": checkin_blockers,
		  "unmatched": unmatched_users, "refused": refused,
		  "double_taps": lambda: double_taps()[:300]}.get(key)
	if not fn:
		frappe.throw(_("Unknown check."))
	return [dict(r) for r in fn()]


@frappe.whitelist(methods=["POST"])
def fix(key: str):
	"""Apply the one-click fix of a check. Nothing is deleted: values are filled, punches set aside, scripts turned off."""
	_manager()
	if key == "turn_on_marking":
		frappe.db.set_single_value("AlphaX HR Settings", "mark_attendance", 1)
		return {"done": 1}
	if key == "copy_iqama":
		done, skipped = 0, []
		for r in national_id_in_device_id():
			value = str(r.attendance_device_id).strip()
			if frappe.db.exists("Employee", {"alphax_iqama_number": value, "name": ["!=", r.name]}):
				skipped.append(f"{r.employee_name}: {value}")
				continue
			frappe.db.set_value("Employee", r.name, "alphax_iqama_number", value)
			done += 1
		return {"done": done, "skipped": skipped}
	if key == "first_in_last_out":
		done = 0
		for a in all_in_sources():
			rule = "First IN, last OUT (ignore the keys)"
			frappe.db.set_value(dv.DEVICE, a["device"], "punch_rule", rule)
			for t in frappe.get_all(dv.DEVICE, filters={"source_device": a["device"]}, pluck="name"):
				frappe.db.set_value(dv.DEVICE, t, "punch_rule", rule, update_modified=False)
			done += 1
		return {"done": done, "note": _("Run 'Update past days' to recalculate earlier days with the new reading.")}
	if key == "skip_double_taps":
		names = [r.name for r in double_taps()]
		if names:
			frappe.db.set_value("Employee Checkin", {"name": ["in", names]}, "skip_auto_attendance", 1, update_modified=False)
		return {"done": len(names)}
	if key == "disable_checkin_scripts":
		names = [b["name"] for b in checkin_blockers() if b["kind"] == "Server Script"]
		for n in names:
			frappe.db.set_value("Server Script", n, "disabled", 1)
		frappe.clear_cache()
		return {"done": len(names), "names": names}
	if key == "retry":
		return {"done": 1, **dv.retry_errors(since=add_days(nowdate(), -60))}
	frappe.throw(_("This check has no automatic fix."))
