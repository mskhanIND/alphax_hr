"""Attendance devices for HR: register devices, see their status and punches, link device users to employees, send
commands, import log files; and the push endpoint used by bridges and non-ZKTeco devices."""
from __future__ import annotations

import json
from datetime import timedelta

import frappe
from frappe import _
from frappe.utils import add_days, cint, get_datetime, get_url, now_datetime

from alphax_hr import devices as dv
from alphax_hr.api._common import parse_json, require_hr, require_hr_manager

FIELDS = ["device_name", "enabled", "brand", "connection", "serial_number", "company", "location", "branch", "offline_alert_hours",
		  "match_by", "punch_rule",
		  "time_offset_minutes", "allowed_ips", "db_type", "db_host", "db_port", "db_name", "db_user", "db_preset", "db_table",
		  "db_user_column", "db_time_column", "db_state_column", "db_sn_column", "pull_every", "split_by_terminal",
		  "db_in_values", "db_out_values", "db_emp_table", "db_emp_id_column", "db_emp_key_column", "db_emp_name_column", "db_emp_no_column",
		  "db_device_table", "db_device_sn_column", "db_device_name_column", "db_device_active_column",
		  "db_device_ip_column", "db_device_location_column", "db_device_model_column"]
ONLINE_MINUTES = 10


def _status(d):
	if not cint(d.enabled) and d.get("connection") == dv.TERMINAL:
		return "Excluded"
	if not cint(d.enabled):
		return "Waiting for approval" if (d.device_name or "").startswith("New device ") else "Disabled"
	if cint(d.get("failures")) and (d.connection or "").startswith("Database pull"):
		return "Connection failed"
	if not d.last_contact:
		return "Never connected"
	if d.connection == dv.TERMINAL:  # no live link to a terminal: judge it by its last punch
		hours = cint(d.offline_alert_hours) or 24
		return "Active" if get_datetime(d.last_contact) > now_datetime() - timedelta(hours=hours) else "Quiet"
	limit = ONLINE_MINUTES if (d.connection or "").startswith("Device push") else max(cint(d.pull_every) or 15, 5) * 3
	return "Online" if get_datetime(d.last_contact) > now_datetime() - timedelta(minutes=limit) else "Offline"


@frappe.whitelist()
def overview():
	require_hr()
	rows = frappe.get_all(dv.DEVICE, fields=["name", *FIELDS, "last_contact", "last_punch", "last_ip", "model", "user_count", "db_last_time",
												  "source_device", "punch_count", "source_active",
												  "last_error", "last_error_on", "failures"],
						  order_by="device_name asc")
	since = now_datetime() - timedelta(days=1)
	for r in rows:
		r.status = _status(r)
		r.punches_24h = frappe.db.count(dv.LOG, {"device": r.name, "punch_time": [">=", since]})
		r.unmatched = frappe.db.count(dv.LOG, {"device": r.name, "status": "Unmatched"})
		r.has_token = bool(frappe.db.get_value(dv.DEVICE, r.name, "api_token"))
		r.outside_7d = frappe.db.count(dv.LOG, {"device": r.name, "outside_branch": 1, "punch_time": [">=", now_datetime() - timedelta(days=7)]})
		r.hint = None
		if (r.punch_rule or "").startswith("From the device"):
			week = {"device": r.name, "punch_time": [">=", now_datetime() - timedelta(days=7)]}
			total = frappe.db.count(dv.LOG, week)
			if total >= 20 and not frappe.db.count(dv.LOG, {**week, "log_type": "OUT"}):
				r.hint = _("Every punch from this device arrives as IN, so each day looks like a missing punch. Staff are probably "
						   "not pressing the IN/OUT keys: set IN / OUT to 'First IN, last OUT (ignore the keys)'.")
		for k in ("last_contact", "last_punch", "db_last_time"):
			r[k] = str(r[k]) if r[k] else None
	terminals = {}
	for r in rows:
		if r.source_device:
			terminals[r.source_device] = terminals.get(r.source_device, 0) + 1
	down = {r.name for r in rows if r.status == "Connection failed"}
	for r in rows:
		r.terminals = terminals.get(r.name, 0)
		if r.source_device in down and cint(r.enabled):
			r.status = "Source not reachable"
		if r.last_error_on:
			r.last_error_on = str(r.last_error_on)
	host = get_url().split("://", 1)[-1].split("/")[0]
	return {"devices": rows, "server": host, "push_url": get_url("/api/method/alphax_hr.api.devices.push"),
			"can_edit": bool(set(frappe.get_roles()) & {"HR Manager", "System Manager"}),
			"totals": {s: frappe.db.count(dv.LOG, {"status": s}) for s in ("Pending", "Unmatched", "Error")}}


@frappe.whitelist(methods=["POST"])
def save(data: str | dict | list, name: str | None = None):
	require_hr_manager()
	values = {k: v for k, v in (parse_json(data) or {}).items() if k in FIELDS}
	doc = frappe.get_doc(dv.DEVICE, name) if name else frappe.new_doc(dv.DEVICE)
	doc.update(values)
	if not (doc.device_name or "").strip():
		frappe.throw(_("Give the device a name."))
	if (doc.connection or "").startswith("Device push") and not doc.serial_number:
		frappe.throw(_("Device push needs the device's serial number."))
	if doc.connection == dv.TERMINAL and not doc.source_device:
		frappe.throw(_("Terminals are added by 'Find terminals' on their database connection."))
	if "db_password" in (parse_json(data) or {}) and (parse_json(data) or {}).get("db_password"):
		doc.db_password = parse_json(data)["db_password"]
	if name and values.get("device_name") and values["device_name"] != name:
		doc.save()
		frappe.rename_doc(dv.DEVICE, name, values["device_name"], force=True)
		return overview()
	doc.save()
	_to_terminals(doc)
	if (doc.connection or "").startswith("Database pull") and cint(doc.enabled) and cint(doc.split_by_terminal):
		frappe.db.commit()
		dv.auto_discover(doc, every_hours=0)  # terminals appear as soon as the connection is saved
	return overview()


def _to_terminals(doc):
	"""Reading rules set on a database connection apply to all its terminals."""
	if not (doc.connection or "").startswith("Database pull"):
		return
	values = {k: doc.get(k) for k in dv.COPY if k not in ("company", "brand")}
	for t in frappe.get_all(dv.DEVICE, filters={"source_device": doc.name}, pluck="name"):
		frappe.db.set_value(dv.DEVICE, t, values, update_modified=False)


def _draft(name, data=None):
	"""The saved connection with unsaved mapping changes from the form applied (nothing is stored)."""
	doc = frappe.get_doc(dv.DEVICE, name)
	values = {k: v for k, v in (parse_json(data) or {}).items() if k in FIELDS}
	doc.update(values)
	return doc


@frappe.whitelist(methods=["POST"])
def schema(name: str, data: str | dict | None = None, table: str | None = None):
	"""Tables of the attendance database and a proposed mapping; with ``table``, that table's columns."""
	require_hr_manager()
	doc = _draft(name, data)
	if table:
		return {"table": table, "columns": dv.columns(doc, table)}
	return dv.suggest_mapping(doc)


@frappe.whitelist(methods=["POST"])
def preview(name: str, data: str | dict | None = None):
	require_hr_manager()
	return dv.preview(_draft(name, data))


def _source(name):
	doc = frappe.get_doc(dv.DEVICE, name)
	return frappe.get_doc(dv.DEVICE, doc.source_device) if doc.connection == dv.TERMINAL and doc.source_device else doc


@frappe.whitelist()
def people(name: str):
	"""Everyone in the attendance database with the employee they match, or a suggestion."""
	require_hr_manager()
	return dv.people_matching(_source(name))


@frappe.whitelist(methods=["POST"])
def link_people(name: str, pairs: str | list):
	require_hr_manager()
	return dv.link_people(_source(name), parse_json(pairs) or [])


@frappe.whitelist()
def shift_gaps():
	"""Employees whose punches were refused because they have no shift, with what HR needs to fix it."""
	require_hr()
	rows = frappe.db.sql("""select employee, count(*) n, min(punch_time) first, max(punch_time) last,
			group_concat(distinct device separator ', ') devices
		from `tabAlphaX Device Log` where status='Error' and message like %s and employee is not null
		group by employee order by n desc limit 1000""", (dv.SHIFT_ERROR,), as_dict=True)
	out = []
	for r in rows:
		e = frappe.db.get_value("Employee", r.employee, ["employee_name", "department", "default_shift", "company", "branch"],
								as_dict=True) or {}
		current = frappe.get_all("Shift Assignment", filters={"employee": r.employee, "docstatus": 1, "status": "Active"},
								 fields=["shift_type", "start_date", "end_date"], order_by="start_date desc", limit=1)
		out.append({"employee": r.employee, "employee_name": e.get("employee_name"), "department": e.get("department"),
					"branch": e.get("branch"), "default_shift": e.get("default_shift"), "refused": r.n,
					"first": str(r.first), "last": str(r.last), "devices": r.devices,
					"assignment": ({**current[0], "start_date": str(current[0].start_date),
									"end_date": str(current[0].end_date) if current[0].end_date else None} if current else None)})
	types = frappe.get_all("Shift Type", fields=["name", "start_time", "end_time"], order_by="name")
	return {"employees": out, "refused": sum(r["refused"] for r in out),
			"shift_types": [{"name": t.name, "start_time": str(t.start_time), "end_time": str(t.end_time)} for t in types],
			"other_errors": frappe.db.count(dv.LOG, {"status": "Error", "message": ["not like", dv.SHIFT_ERROR]})}


@frappe.whitelist(methods=["POST"])
def fix_shift_gaps(employees: str | list, shift_type: str | None = None, start_date: str | None = None, use_default: int | str = 0):
	"""Assign a shift from ``start_date`` with no end date (or each employee's default shift), then import their refused
	punches."""
	require_hr_manager()
	from alphax_hr.api import shifts

	names = parse_json(employees) or []
	created, failed = [], []
	if cint(use_default):
		groups = {}
		for emp in names:
			default = frappe.db.get_value("Employee", emp, "default_shift")
			if default:
				groups.setdefault(default, []).append(emp)
			else:
				failed.append({"employee": emp, "error": _("No default shift on the profile")})
	else:
		if not shift_type:
			frappe.throw(_("Choose a shift type."))
		groups = {shift_type: names}
	for st, emps in groups.items():
		for i in range(0, len(emps), shifts.MAX_ASSIGN):
			res = shifts.assign(emps[i:i + shifts.MAX_ASSIGN], st, start_date or frappe.utils.today())
			created += res["created"]
			failed += res["failed"]
	frappe.flags.in_test or frappe.db.commit()
	counts = dv.retry_errors(employees=names, since=start_date, only_shift=True)
	return {"created": len(created), "failed": failed, **counts}


@frappe.whitelist(methods=["POST"])
def retry_errors(device: str | None = None):
	"""Try every refused punch again."""
	require_hr_manager()
	if device:
		names = frappe.get_all(dv.LOG, filters={"status": "Error", "device": device}, pluck="name")
		frappe.db.set_value(dv.LOG, {"name": ["in", names or ["-"]]}, "status", "Pending", update_modified=False)
		return dv.process(names)
	return dv.retry_errors()


@frappe.whitelist()
def sync_status(name: str, start: str | None = None, end: str | None = None):
	require_hr()
	return dv.sync_status(frappe.get_doc(dv.DEVICE, name), start or None, end or None)


@frappe.whitelist(methods=["POST"])
def backfill(name: str, start: str, end: str | None = None):
	"""Read a period again. Small periods run now; larger ones in the background."""
	require_hr_manager()
	doc = frappe.get_doc(dv.DEVICE, name)
	if doc.connection == dv.TERMINAL and doc.source_device:
		doc = frappe.get_doc(dv.DEVICE, doc.source_device)
	status = dv.sync_status(doc, start, end)
	if status["available"] <= 5000:
		return {"queued": False, **dv.backfill(doc, start, end)}
	frappe.enqueue("alphax_hr.devices.backfill_job", queue="long", timeout=7200, job_id=f"alphax-backfill-{doc.name}",
				   deduplicate=True, name=doc.name, start=start, end=end, enqueue_after_commit=True)
	return {"queued": True, "available": status["available"]}


@frappe.whitelist(methods=["POST"])
def delete(name: str):
	require_hr_manager()
	if frappe.db.count(dv.LOG, {"device": name, "status": "Imported"}):
		frappe.db.set_value(dv.DEVICE, name, "enabled", 0)
		return {"disabled": True, **overview()}
	for t in frappe.get_all(dv.DEVICE, filters={"source_device": name}, pluck="name"):
		if frappe.db.count(dv.LOG, {"device": t, "status": "Imported"}):
			frappe.db.set_value(dv.DEVICE, t, {"source_device": None, "enabled": 0})
		else:
			frappe.db.delete(dv.LOG, {"device": t})
			frappe.delete_doc(dv.DEVICE, t, ignore_permissions=True)
	frappe.db.delete(dv.LOG, {"device": name})
	frappe.db.delete("AlphaX Device Command", {"device": name})
	frappe.db.delete("AlphaX Device User", {"device": name})
	frappe.delete_doc(dv.DEVICE, name)
	return overview()


@frappe.whitelist(methods=["POST"])
def new_token(name: str):
	"""A new push-API token; shown once."""
	require_hr_manager()
	token = frappe.generate_hash(length=32)
	doc = frappe.get_doc(dv.DEVICE, name)
	doc.api_token = token
	doc.save()
	return {"token": token}


@frappe.whitelist(methods=["POST"])
def test(name: str):
	require_hr_manager()
	return dv.test_connection(frappe.get_doc(dv.DEVICE, name))


@frappe.whitelist(methods=["POST"])
def pull_now(name: str):
	require_hr_manager()
	doc = frappe.get_doc(dv.DEVICE, name)
	if doc.connection == dv.TERMINAL and doc.source_device:
		doc = frappe.get_doc(dv.DEVICE, doc.source_device)  # a terminal's punches come through its source
	return dv.pull(doc)


@frappe.whitelist(methods=["POST"])
def discover(name: str):
	"""Find the terminals in a central attendance database and list each one as a device."""
	require_hr_manager()
	doc = frappe.get_doc(dv.DEVICE, name)
	if not (doc.connection or "").startswith("Database pull"):
		frappe.throw(_("Finding terminals works for a database connection."))
	return {**dv.discover(doc), **overview()}


@frappe.whitelist(methods=["POST"])
def command(name: str, command: str, user: str | None = None):
	require_hr_manager()
	doc = frappe.get_doc(dv.DEVICE, name)
	if not (doc.connection or "").startswith("Device push"):
		frappe.throw(_("Commands are sent to devices that connect by device push (ADMS)."))
	payload = None
	if command == "Upload all logs again":
		start = add_days(now_datetime(), -31).strftime("%Y-%m-%d 00:00:00")
		payload = f"DATA QUERY ATTLOG StartTime={start}\tEndTime={now_datetime().strftime('%Y-%m-%d %H:%M:%S')}"
	elif command == "Send employees to device":
		filters = {"status": "Active", "attendance_device_id": ["is", "set"]}
		if doc.company:
			filters["company"] = doc.company
		emps = frappe.get_all("Employee", filters=filters, fields=["attendance_device_id", "employee_name"], limit=2000)
		lines = [f"DATA UPDATE USERINFO PIN={e.attendance_device_id}\tName={(e.employee_name or '')[:24]}\tPri=0"
				 for e in emps if str(e.attendance_device_id).strip().isdigit()]
		if not lines:
			frappe.throw(_("No active employee has a numeric attendance device ID to send."))
		payload = "\n".join(lines)
	elif command == "Remove left employees":
		left = [u for u in enrolment(name)["left_on_device"]]
		if not left:
			frappe.throw(_("No employee who has left is on this device."))
		payload = "\n".join(f"DATA DELETE USERINFO PIN={u['device_user']}" for u in left)
	elif command == "Delete user from device":
		user = (user or "").strip()
		if not user.isdigit():
			frappe.throw(_("Enter the user number on the device."))
		payload = f"DATA DELETE USERINFO PIN={user}"
	elif command == "Clear device logs":
		waiting = frappe.db.count(dv.LOG, {"device": name, "status": ["in", ["Pending", "Unmatched", "Error"]]})
		if waiting:
			frappe.throw(_("{0} punches from this device are not imported yet (unmatched users or errors). Fix them first: "
						   "clearing the device removes its copy for good.").format(waiting))
		if not frappe.db.count(dv.LOG, {"device": name}):
			frappe.throw(_("No punches from this device have been received yet."))
		payload = "CLEAR LOG"
	elif command not in ("Reboot", "Read device info"):
		frappe.throw(_("Unknown command."))
	frappe.get_doc({"doctype": "AlphaX Device Command", "device": name, "command": command, "payload": payload,
					"status": "Pending"}).insert(ignore_permissions=True)
	return commands(name)


@frappe.whitelist()
def commands(name: str):
	require_hr()
	rows = frappe.get_all("AlphaX Device Command", filters={"device": name}, fields=["name", "command", "status", "sent_at", "result",
																					  "creation"], order_by="creation desc", limit=20)
	for r in rows:
		r.sent_at, r.creation = (str(r.sent_at) if r.sent_at else None), str(r.creation)
	return rows


@frappe.whitelist()
def logs(device: str | None = None, status: str | None = None, employee: str | None = None, limit: int | str = 100):
	require_hr()
	filters = {}
	for k, v in (("device", device), ("status", status), ("employee", employee)):
		if v:
			filters[k] = v
	rows = frappe.get_all(dv.LOG, filters=filters, fields=["name", "device", "device_user", "punch_time", "log_type", "source",
														   "status", "employee", "message", "outside_branch"],
						  order_by="punch_time desc", limit=min(cint(limit) or 100, 500))
	names = {r.employee for r in rows if r.employee}
	labels = dict(frappe.get_all("Employee", filters={"name": ["in", list(names) or [""]]}, fields=["name", "employee_name"], as_list=True))
	for r in rows:
		r.punch_time = str(r.punch_time)
		r.employee_name = labels.get(r.employee)
	return rows


@frappe.whitelist()
def enrolment(name: str):
	"""Who is on the device and who should be: users of employees who left (remove them), active employees without a
	device ID, and employees with an ID who are not on the device yet."""
	require_hr()
	dev = frappe.get_doc(dv.DEVICE, name)
	users = frappe.get_all("AlphaX Device User", filters={"device": name}, fields=["device_user", "user_name"])
	filters = {"status": "Active"}
	if dev.company:
		filters["company"] = dev.company
	if dev.get("branch"):
		filters["branch"] = dev.branch
	active = frappe.get_all("Employee", filters=filters, fields=["name", "employee_name", "attendance_device_id", "department"])
	on_device = {str(u.device_user) for u in users}
	left = []
	for u in users:
		emp = dv.employee_for(dev, u.device_user)
		if emp:
			e = frappe.db.get_value("Employee", emp, ["employee_name", "status", "relieving_date"], as_dict=True)
			if e.status != "Active" or (e.relieving_date and frappe.utils.getdate(e.relieving_date) < frappe.utils.getdate()):
				left.append({"device_user": u.device_user, "user_name": u.user_name, "employee": emp, "employee_name": e.employee_name,
							 "status": e.status})
	return {"device_users": len(users), "users_known": bool(users),
			"left_on_device": left,
			"missing_id": [{"name": e.name, "employee_name": e.employee_name, "department": e.department}
						   for e in active if not e.attendance_device_id][:200],
			"not_on_device": [{"name": e.name, "employee_name": e.employee_name, "attendance_device_id": e.attendance_device_id}
							  for e in active if e.attendance_device_id and str(e.attendance_device_id) not in on_device][:200]
			if users else []}


@frappe.whitelist()
def unmatched():
	"""Device user IDs whose punches wait for an employee, with the name on the device and a suggested employee."""
	require_hr()
	rows = frappe.db.sql("""select device, device_user, count(*) n, max(punch_time) last from `tabAlphaX Device Log`
		where status='Unmatched' group by device, device_user order by n desc limit 500""", as_dict=True)
	for r in rows:
		r.last = str(r.last)
		r.user_name = frappe.db.get_value("AlphaX Device User", {"device": r.device, "device_user": r.device_user}, "user_name")
		if not r.user_name:
			src = frappe.db.get_value(dv.DEVICE, r.device, "source_device")
			if src:
				r.user_name = frappe.db.get_value("AlphaX Device User", {"device": src, "device_user": r.device_user}, "user_name")
		r.suggest = None
		if r.user_name:
			first = r.user_name.split()[0]
			hits = frappe.get_all("Employee", filters={"status": "Active", "employee_name": ["like", f"%{first}%"],
													   "attendance_device_id": ["is", "not set"]}, fields=["name", "employee_name"], limit=2)
			if len(hits) == 1:
				r.suggest = hits[0]
	return rows


@frappe.whitelist(methods=["POST"])
def link_user(device: str, device_user: str, employee: str):
	"""Link a device user to an employee (sets the employee's attendance device ID) and import the waiting punches."""
	require_hr_manager()
	dev = frappe.get_doc(dv.DEVICE, device)
	emp = frappe.get_doc("Employee", employee)
	emp.check_permission("write")
	group = [device]
	if dev.source_device:
		group += frappe.get_all(dv.DEVICE, filters={"source_device": dev.source_device}, pluck="name") + [dev.source_device]
	if dev.match_by == "National ID / Iqama":  # the value is a national ID / Iqama: put it on the employee
		import re

		if not re.fullmatch(r"[12]\d{9}", str(device_user)):  # no national ID in the source: link by device ID
			return dv.link_people(frappe.get_doc(dv.DEVICE, dev.source_device) if dev.source_device else dev,
								  [{"device_user": device_user, "employee": employee}])
		other = frappe.db.get_value("Employee", {"alphax_iqama_number": device_user, "name": ["!=", employee]}, "employee_name")
		if other:
			frappe.throw(_("{0} is already the Iqama of {1}.").format(device_user, other))
		if emp.get("alphax_iqama_number") and emp.alphax_iqama_number != device_user:
			frappe.throw(_("{0} already has Iqama {1}; correct it on the profile if it is wrong.").format(
				emp.employee_name, emp.alphax_iqama_number))
		frappe.db.set_value("Employee", employee, "alphax_iqama_number", device_user)
		names = frappe.get_all(dv.LOG, filters={"device": ["in", list(set(group))], "device_user": device_user,
												 "status": "Unmatched"}, pluck="name")
		return dv.process(names)
	if (dev.match_by or "Attendance device ID") != "Attendance device ID":
		frappe.throw(_("This device matches by {0}; fix that value on the employee instead.").format(_(dev.match_by)))
	other = frappe.db.get_value("Employee", {"attendance_device_id": device_user, "name": ["!=", employee]}, "employee_name")
	if other:
		frappe.throw(_("Device user {0} is already linked to {1}.").format(device_user, other))
	emp.attendance_device_id = device_user
	emp.flags.ignore_mandatory = True
	emp.save()
	frappe.db.sql("update `tabAlphaX Device User` set employee=%s where device=%s and device_user=%s", (employee, device, device_user))
	names = frappe.get_all(dv.LOG, filters={"device": device, "device_user": device_user, "status": "Unmatched"}, pluck="name")
	return dv.process(names)


@frappe.whitelist(methods=["POST"])
def reprocess(device: str | None = None):
	require_hr_manager()
	return dv.process(device=device)


@frappe.whitelist(methods=["POST"])
def upload(device: str, file_url: str):
	"""Import an attendance log file (ZKTeco attlog.dat from USB, or CSV: user, time[, state])."""
	require_hr_manager()
	f = frappe.get_doc("File", {"file_url": file_url})
	rows = dv.parse_file(f.get_content())
	if not rows:
		frappe.throw(_("No punches found in this file. Expected lines like: 12<TAB>2026-11-05 08:01:22<TAB>0"))
	return dv.ingest(frappe.get_doc(dv.DEVICE, device), rows, "File upload")


# ------------------------------------------------------------------ push API (bridges, Hikvision, Suprema, Anviz ...)
def _hikvision(payload):
	"""Hikvision ISAPI event (HTTP listening): AccessControllerEvent with employeeNoString."""
	ev = payload.get("AccessControllerEvent") or {}
	user = ev.get("employeeNoString") or ev.get("employeeNo")
	if not user:
		return []
	state = (ev.get("attendanceStatus") or "").lower()
	return [{"user": user, "time": (payload.get("dateTime") or "")[:19].replace("T", " "),
			 "state": "in" if state.startswith("checkin") else "out" if state.startswith("checkout") else None}]


# Public: devices and bridges send punches here; each call must carry the device's own token (checked below).
@frappe.whitelist(allow_guest=True, methods=["POST"])  # nosemgrep
def push(device: str | None = None, token: str | None = None, punches: str | dict | list | None = None):
	"""Punches from a bridge or a device: {"device": serial number or device name, "punches": [{"user", "time", "state"}]}.
	Token in the X-AlphaX-Device-Token header (or ``token``). Hikvision event notifications are accepted as they are."""
	from frappe.utils.password import get_decrypted_password

	req = frappe.local.request
	form = frappe.local.form_dict
	device = device or req.headers.get("X-AlphaX-Device") or form.get("sn")
	token = req.headers.get("X-AlphaX-Device-Token") or token
	name = frappe.db.get_value(dv.DEVICE, {"serial_number": device}, "name") or (device if device and frappe.db.exists(dv.DEVICE, device) else None)
	expected = get_decrypted_password(dv.DEVICE, name, "api_token", raise_exception=False) if name else None
	if not (name and expected and token and _same(token, expected)):
		frappe.local.response.http_status_code = 403
		return {"ok": False, "error": "unknown device or wrong token"}
	dev = frappe.get_doc(dv.DEVICE, name)
	ip = req.headers.get("X-Real-IP") or req.remote_addr
	if not cint(dev.enabled) or not dv.ip_allowed(dev, ip):
		frappe.local.response.http_status_code = 403
		return {"ok": False, "error": "device not allowed"}
	data = parse_json(punches) if punches is not None else None
	if data is None:
		raw = form.get("event_log") or (form if form.get("AccessControllerEvent") else None)
		if isinstance(raw, str):
			raw = json.loads(raw)
		data = _hikvision(raw) if isinstance(raw, dict) and raw.get("AccessControllerEvent") else []
	if isinstance(data, dict):
		data = _hikvision(data) if data.get("AccessControllerEvent") else [data]
	rows = [{"user": p.get("user") or p.get("user_id") or p.get("pin"), "time": p.get("time") or p.get("timestamp"),
			 "state": p.get("state") if p.get("state") is not None else p.get("type")} for p in (data or [])[:5000]]
	dv.touch(dev, ip)
	return {"ok": True, **dv.ingest(dev, rows, "Push API")}


def _same(a, b):
	import hmac

	return hmac.compare_digest(str(a), str(b))
