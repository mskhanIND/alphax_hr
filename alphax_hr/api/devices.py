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

FIELDS = ["device_name", "enabled", "brand", "connection", "serial_number", "company", "location", "match_by", "punch_rule",
		  "time_offset_minutes", "allowed_ips", "db_type", "db_host", "db_port", "db_name", "db_user", "db_preset", "db_table",
		  "db_user_column", "db_time_column", "db_state_column", "db_sn_column", "pull_every"]
ONLINE_MINUTES = 10


def _status(d):
	if not cint(d.enabled):
		return "Waiting for approval" if (d.device_name or "").startswith("New device ") else "Disabled"
	if not d.last_contact:
		return "Never connected"
	limit = ONLINE_MINUTES if (d.connection or "").startswith("Device push") else max(cint(d.pull_every) or 15, 5) * 3
	return "Online" if get_datetime(d.last_contact) > now_datetime() - timedelta(minutes=limit) else "Offline"


@frappe.whitelist()
def overview():
	require_hr()
	rows = frappe.get_all(dv.DEVICE, fields=["name", *FIELDS, "last_contact", "last_punch", "last_ip", "model", "user_count", "db_last_time"],
						  order_by="device_name asc")
	since = now_datetime() - timedelta(days=1)
	for r in rows:
		r.status = _status(r)
		r.punches_24h = frappe.db.count(dv.LOG, {"device": r.name, "punch_time": [">=", since]})
		r.unmatched = frappe.db.count(dv.LOG, {"device": r.name, "status": "Unmatched"})
		r.has_token = bool(frappe.db.get_value(dv.DEVICE, r.name, "api_token"))
		for k in ("last_contact", "last_punch", "db_last_time"):
			r[k] = str(r[k]) if r[k] else None
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
	if "db_password" in (parse_json(data) or {}) and (parse_json(data) or {}).get("db_password"):
		doc.db_password = parse_json(data)["db_password"]
	if name and values.get("device_name") and values["device_name"] != name:
		doc.save()
		frappe.rename_doc(dv.DEVICE, name, values["device_name"], force=True)
		return overview()
	doc.save()
	return overview()


@frappe.whitelist(methods=["POST"])
def delete(name: str):
	require_hr_manager()
	if frappe.db.count(dv.LOG, {"device": name, "status": "Imported"}):
		frappe.db.set_value(dv.DEVICE, name, "enabled", 0)
		return {"disabled": True, **overview()}
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
	return dv.pull(frappe.get_doc(dv.DEVICE, name))


@frappe.whitelist(methods=["POST"])
def command(name: str, command: str):
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
														   "status", "employee", "message"],
						  order_by="punch_time desc", limit=min(cint(limit) or 100, 500))
	names = {r.employee for r in rows if r.employee}
	labels = dict(frappe.get_all("Employee", filters={"name": ["in", list(names) or [""]]}, fields=["name", "employee_name"], as_list=True))
	for r in rows:
		r.punch_time = str(r.punch_time)
		r.employee_name = labels.get(r.employee)
	return rows


@frappe.whitelist()
def unmatched():
	"""Device user IDs whose punches wait for an employee, with the name on the device and a suggested employee."""
	require_hr()
	rows = frappe.db.sql("""select device, device_user, count(*) n, max(punch_time) last from `tabAlphaX Device Log`
		where status='Unmatched' group by device, device_user order by n desc limit 500""", as_dict=True)
	for r in rows:
		r.last = str(r.last)
		r.user_name = frappe.db.get_value("AlphaX Device User", {"device": r.device, "device_user": r.device_user}, "user_name")
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
