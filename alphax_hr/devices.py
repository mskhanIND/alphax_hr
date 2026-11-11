"""Attendance devices: every punch, however it arrives, goes through one pipeline.

Sources: ZKTeco ADMS / iClock push (``alphax_hr.adms``), the push API for bridges and other brands
(``alphax_hr.api.devices.push``), a pull from the attendance software's database (BioTime, ZKTime / ZKAccess) and
log files exported from a device.

ingest() stores raw punches as *AlphaX Device Log* rows (duplicates ignored); process() matches the device user to an
employee and creates the standard HRMS *Employee Checkin*. Unmatched punches wait until HR links the device user to an
employee, then are processed again.
"""
from __future__ import annotations

import re
from datetime import timedelta

import frappe
from frappe import _
from frappe.utils import cint, get_datetime, getdate, now_datetime

DEVICE = "AlphaX Attendance Device"
LOG = "AlphaX Device Log"
IN_STATES = {"0", "3", "4", "i", "in", "checkin", "check-in", "breakin", "overtimein"}
OUT_STATES = {"1", "2", "5", "o", "out", "checkout", "check-out", "breakout", "overtimeout"}
IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)?$")


def device_by_sn(sn):
	if not sn:
		return None
	name = frappe.db.get_value(DEVICE, {"serial_number": str(sn).strip()}, "name")
	return frappe.get_doc(DEVICE, name) if name else None


def ip_allowed(dev, ip):
	allowed = [x.strip() for x in (dev.allowed_ips or "").splitlines() if x.strip()]
	return not allowed or (ip or "") in allowed


def touch(dev, ip=None, **values):
	"""Record that the device was in contact (without changing ``modified``)."""
	values.update({"last_contact": now_datetime()})
	if ip:
		values["last_ip"] = ip
	frappe.db.set_value(DEVICE, dev.name, values, update_modified=False)


def log_type(dev, state):
	rule = dev.punch_rule or ""
	if rule.startswith("All IN"):
		return "IN"
	if rule.startswith("All OUT"):
		return "OUT"
	if rule.startswith("Alternate") or rule.startswith("First IN"):
		return None  # the register reads the day: first punch IN, last punch OUT
	s = re.sub(r"[\s_]", "", str(state if state is not None else "").strip().lower())
	if s in IN_STATES:
		return "IN"
	if s in OUT_STATES:
		return "OUT"
	return None


def ingest(dev, rows, source):
	"""Store punches ``[{"user", "time", "state"}]`` from one device and process them. Returns counts."""
	offset = timedelta(minutes=cint(dev.time_offset_minutes))
	names, seen, dup, bad = [], set(), 0, 0
	latest = None
	for r in rows:
		user = str(r.get("user") or "").strip()
		try:
			when = get_datetime(r.get("time")) if r.get("time") else None
		except Exception:  # noqa: BLE001
			when = None
		if not user or not when:
			bad += 1
			continue
		when = (when + offset).replace(microsecond=0, tzinfo=None)
		key = (user, when)
		if key in seen or frappe.db.exists(LOG, {"device": dev.name, "device_user": user, "punch_time": when}):
			dup += 1
			continue
		seen.add(key)
		doc = frappe.get_doc({"doctype": LOG, "device": dev.name, "device_user": user, "punch_time": when,
							  "raw_state": None if r.get("state") is None else str(r.get("state"))[:40],
							  "log_type": log_type(dev, r.get("state")), "source": source, "status": "Pending"})
		doc.insert(ignore_permissions=True)
		names.append(doc.name)
		latest = max(latest, when) if latest else when
	if latest and (not dev.last_punch or get_datetime(dev.last_punch) < latest):
		frappe.db.set_value(DEVICE, dev.name, "last_punch", latest, update_modified=False)
	result = process(names) if names else {"imported": 0, "unmatched": 0, "duplicate": 0, "error": 0}
	return {"received": len(rows), "new": len(names), "already_had": dup, "unreadable": bad, **result}


def employee_for(dev, user):
	match = dev.match_by or "Attendance device ID"
	if match == "Employee ID":
		return user if frappe.db.exists("Employee", user) else None
	if match == "National ID / Iqama":
		field = "alphax_iqama_number" if frappe.get_meta("Employee").has_field("alphax_iqama_number") else None
		return frappe.db.get_value("Employee", {field: user}, "name") if field else None
	return frappe.db.get_value("Employee", {"attendance_device_id": user}, "name")


def process(names=None, device=None):
	"""Create Employee Checkins for pending / unmatched logs (the given ones, a device's, or all)."""
	filters = {"status": ["in", ["Pending", "Unmatched"]]}
	if names is not None:
		filters["name"] = ["in", names or [""]]
	if device:
		filters["device"] = device
	counts = {"imported": 0, "unmatched": 0, "duplicate": 0, "error": 0}
	devices, earlier = {}, set()
	for row in frappe.get_all(LOG, filters=filters, fields=["name", "device", "device_user", "punch_time", "log_type"],
							  order_by="punch_time asc", limit_page_length=5000):
		dev = devices.get(row.device) or devices.setdefault(row.device, frappe.get_cached_doc(DEVICE, row.device))
		employee = employee_for(dev, row.device_user)
		if not employee:
			frappe.db.set_value(LOG, row.name, {"status": "Unmatched", "message": _("No employee has this device user ID")},
								update_modified=False)
			counts["unmatched"] += 1
			continue
		outside = 0
		if dev.get("branch"):
			outside = int((frappe.get_cached_value("Employee", employee, "branch") or "") != dev.branch)
		existing = frappe.db.get_value("Employee Checkin", {"employee": employee, "time": row.punch_time}, "name")
		if existing:
			frappe.db.set_value(LOG, row.name, {"status": "Duplicate", "employee": employee, "employee_checkin": existing,
												"message": _("Already recorded")}, update_modified=False)
			counts["duplicate"] += 1
			continue
		frappe.db.savepoint("alphax_device_log")
		try:
			chk = frappe.get_doc({"doctype": "Employee Checkin", "employee": employee, "time": row.punch_time,
								  "log_type": row.log_type or None, "device_id": dev.device_name[:140]})
			chk.flags.ignore_permissions = True
			chk.insert()
			frappe.db.set_value(LOG, row.name, {"status": "Imported", "employee": employee, "employee_checkin": chk.name,
												"outside_branch": outside,
												"message": _("Punched at another branch's device") if outside else None},
								update_modified=False)
			counts["imported"] += 1
			earlier.add((employee, getdate(row.punch_time)))
		except Exception as exc:  # noqa: BLE001
			frappe.db.rollback(save_point="alphax_device_log")
			frappe.clear_messages()
			frappe.db.set_value(LOG, row.name, {"status": "Error", "employee": employee,
												"message": frappe.utils.strip_html(str(exc))[:300]}, update_modified=False)
			counts["error"] += 1
	if earlier:  # punches for days already past (device was offline): correct their attendance
		from alphax_hr.attendance_marking import remark_later

		remark_later(earlier)
	return counts


# ------------------------------------------------------------------ log files
def parse_file(content):
	"""ZKTeco USB exports (``1_attlog.dat``: user TAB time TAB state ...) and CSV files (user, time[, state])."""
	if isinstance(content, bytes):
		content = content.decode("utf-8-sig", errors="ignore")
	rows = []
	for line in content.splitlines():
		line = line.strip()
		if not line:
			continue
		parts = [p.strip() for p in (line.split("\t") if "\t" in line else line.split(","))]
		if len(parts) < 2 or not re.match(r"^\d{4}-\d{2}-\d{2}", parts[1]):
			continue  # header or a line that is not a punch
		rows.append({"user": parts[0], "time": parts[1], "state": parts[2] if len(parts) > 2 else None})
	return rows


# ------------------------------------------------------------------ database pull (BioTime, ZKTime / ZKAccess, custom)
PRESETS = {
	"BioTime (iclock_transaction)": ("iclock_transaction", "emp_code", "punch_time", "punch_state", "terminal_sn"),
	"ZKTime / ZKAccess (CHECKINOUT)": ("CHECKINOUT c JOIN USERINFO u ON u.USERID = c.USERID", "u.BADGENUMBER", "c.CHECKTIME",
									   "c.CHECKTYPE", "c.SENSORID"),
}


def _columns(dev):
	if dev.db_preset in PRESETS:
		return PRESETS[dev.db_preset]
	cols = (dev.db_table, dev.db_user_column, dev.db_time_column, dev.db_state_column, dev.db_sn_column)
	for c in cols[:3]:
		if not c or not IDENT.match(c):
			frappe.throw(_("Check the table and column names (letters, numbers and _ only)."))
	for c in cols[3:]:
		if c and not IDENT.match(c):
			frappe.throw(_("Check the table and column names (letters, numbers and _ only)."))
	return cols


def _connect(dev):
	from frappe.utils.password import get_decrypted_password

	password = get_decrypted_password(DEVICE, dev.name, "db_password", raise_exception=False) or ""
	kind = dev.db_type or ""
	if kind.startswith("MySQL"):
		import pymysql

		return pymysql.connect(host=dev.db_host, port=cint(dev.db_port) or 3306, user=dev.db_user, password=password,
							   database=dev.db_name, connect_timeout=10), "%s"
	if kind == "PostgreSQL":
		import psycopg2

		return psycopg2.connect(host=dev.db_host, port=cint(dev.db_port) or 5432, user=dev.db_user, password=password,
								dbname=dev.db_name, connect_timeout=10), "%s"
	if kind == "SQL Server":
		try:
			import pymssql
		except ImportError:
			frappe.throw(_("SQL Server needs the pymssql package on the server: bench pip install pymssql"))
		return pymssql.connect(server=dev.db_host, port=str(cint(dev.db_port) or 1433), user=dev.db_user, password=password,
							   database=dev.db_name, login_timeout=10), "%s"
	frappe.throw(_("Choose the database type."))


def _select(dev, since, limit=5000):
	table, user, when, state, sn = _columns(dev)
	top = f"TOP {int(limit)} " if dev.db_type == "SQL Server" else ""
	tail = "" if dev.db_type == "SQL Server" else f" LIMIT {int(limit)}"
	return (f"SELECT {top}{user}, {when}, {state or 'NULL'}, {sn or 'NULL'} FROM {table} "  # identifiers checked by IDENT / presets
			f"WHERE {when} > %s ORDER BY {when}{tail}")


def pull(dev, since=None):
	"""Read new punches from the attendance software's database and ingest them."""
	since = since or dev.db_last_time or "2000-01-01 00:00:00"
	conn, _param = _connect(dev)
	try:
		cur = conn.cursor()
		cur.execute(_select(dev, since), (str(since),))  # nosemgrep
		data = cur.fetchall()
	finally:
		conn.close()
	rows = [{"user": r[0], "time": r[1], "state": r[2]} for r in data]
	touch(dev)
	out = ingest(dev, rows, "Database pull")
	if data:
		frappe.db.set_value(DEVICE, dev.name, "db_last_time", get_datetime(data[-1][1]).replace(microsecond=0, tzinfo=None),
							update_modified=False)
	return out


def test_connection(dev):
	conn, _param = _connect(dev)
	try:
		table, _u, when, *_rest = _columns(dev)
		cur = conn.cursor()
		cur.execute(f"SELECT COUNT(*), MAX({when}) FROM {table}")  # nosemgrep  # identifiers checked by IDENT / presets
		count, last = cur.fetchone()
	finally:
		conn.close()
	return {"punches": count, "last": str(last) if last else None}


# ------------------------------------------------------------------ scheduler
def scheduled():
	"""Every 5 minutes: pull database devices that are due, and retry punches that are still pending."""
	if not frappe.db.exists("DocType", DEVICE):
		return
	now = now_datetime()
	for d in frappe.get_all(DEVICE, filters={"enabled": 1, "connection": ["like", "Database pull%"]},
							fields=["name", "last_contact", "pull_every"]):
		if d.last_contact and get_datetime(d.last_contact) > now - timedelta(minutes=max(cint(d.pull_every) or 15, 5)):
			continue
		try:
			pull(frappe.get_doc(DEVICE, d.name))
		except Exception:  # noqa: BLE001
			frappe.log_error(title=f"AlphaX device pull: {d.name}")
	if frappe.db.count(LOG, {"status": "Pending"}):
		process()
	offline_alerts(now)


def offline_alerts(now=None):
	"""Tell HR once when an enabled device stops contacting AlphaX for longer than its alert hours."""
	now = now or now_datetime()
	for d in frappe.get_all(DEVICE, filters={"enabled": 1, "offline_alert_hours": [">", 0], "last_contact": ["is", "set"],
											  "connection": ["!=", "File upload"]},
							fields=["name", "device_name", "location", "last_contact", "offline_alert_hours", "offline_alerted_on"]):
		last = get_datetime(d.last_contact)
		if last > now - timedelta(hours=cint(d.offline_alert_hours)):
			continue
		if d.offline_alerted_on and get_datetime(d.offline_alerted_on) >= last:
			continue  # already told for this outage
		from alphax_hr.api import alerts

		alerts.event("Device offline", _("Attendance device offline: {0}").format(d.device_name),
					 _("No contact since {0}{1}. Punches made meanwhile stay on the device and arrive when it reconnects; "
					   "check its power and network.").format(frappe.utils.format_datetime(last, "dd-MM-yyyy HH:mm"),
															  f" ({d.location})" if d.location else ""),
					 url="/alphax/attendance-devices", doc=(DEVICE, d.name), tag=f"offline-{d.name}")
		frappe.db.set_value(DEVICE, d.name, "offline_alerted_on", now, update_modified=False)
