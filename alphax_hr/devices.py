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
	raw = str(state if state is not None else "").strip().lower()
	ins = {x.strip().lower() for x in (dev.get("db_in_values") or "").split(",") if x.strip()}
	outs = {x.strip().lower() for x in (dev.get("db_out_values") or "").split(",") if x.strip()}
	if ins or outs:
		return "IN" if raw in ins else "OUT" if raw in outs else None
	s = re.sub(r"[\s_]", "", raw)
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
		meta = frappe.get_meta("Employee")
		for field in ("alphax_iqama_number", "iqama_national_id"):  # AlphaX field, then the older custom field
			if meta.has_field(field):
				name = frappe.db.get_value("Employee", {field: user}, "name")
				if name:
					return name
		return None
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
# Presets described as a mapping (punch table c, optional people table e and devices table d), the same shape HR fills in
# for Custom. ADMS server database: users missing from EmpDetails still come in, under their device user ID.
MAPS = {
	"ADMS (CheckInOut + EmpDetails)": {
		"db_table": "CheckInOut", "db_user_column": "UserId", "db_time_column": "CheckTime", "db_state_column": "CheckType",
		"db_sn_column": "SN", "db_emp_table": "EmpDetails", "db_emp_id_column": "Id", "db_emp_key_column": "NationalId",
		"db_emp_name_column": "EmpName", "db_device_table": "Devices", "db_device_sn_column": "SN",
		"db_device_name_column": "DeviceName", "db_device_active_column": "IsActive"},
}
MAP_FIELDS = ("db_table", "db_user_column", "db_time_column", "db_state_column", "db_sn_column", "db_emp_table",
			  "db_emp_id_column", "db_emp_key_column", "db_emp_name_column", "db_device_table", "db_device_sn_column",
			  "db_device_name_column", "db_device_active_column")
COLUMN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def mapping(dev):
	"""Table and column names in use: the preset's, with anything HR filled in on top (so a preset can be adjusted)."""
	base = dict(MAPS.get(dev.db_preset) or {})
	for k in MAP_FIELDS:
		if dev.get(k):
			base[k] = dev.get(k).strip()
	return base


def _check(name, table=False):
	if not name:
		return None
	if not (IDENT if table else COLUMN).match(name):
		frappe.throw(_("Check the table and column names (letters, numbers and _ only): {0}").format(name))
	return name


def _columns(dev):
	"""(table expression, user, time, state, device serial) for the punch query."""
	if dev.db_preset in PRESETS:
		return PRESETS[dev.db_preset]
	m = mapping(dev)
	table, user, when = _check(m.get("db_table"), True), _check(m.get("db_user_column")), _check(m.get("db_time_column"))
	if not (table and user and when):
		frappe.throw(_("Choose the punch table and its user and time columns."))
	state, sn = _check(m.get("db_state_column")), _check(m.get("db_sn_column"))
	emp, emp_id, key = _check(m.get("db_emp_table"), True), _check(m.get("db_emp_id_column")), _check(m.get("db_emp_key_column"))
	if emp and emp_id and key:  # match by a value from the people table; users missing there keep their punch user ID
		return (f"{table} c LEFT JOIN {emp} e ON e.{emp_id} = c.{user}",
				f"COALESCE(NULLIF(CONCAT('', e.{key}), ''), CONCAT('', c.{user}))", f"c.{when}",
				f"c.{state}" if state else None, f"c.{sn}" if sn else None)
	return (f"{table} c", f"c.{user}", f"c.{when}", f"c.{state}" if state else None, f"c.{sn}" if sn else None)


def _host_port(host, port):
	"""'server:1441', 'server,1441' (SQL Server style) or 'tcp:server' are read as host and port."""
	host = (host or "").strip()
	if host.lower().startswith("tcp:"):
		host = host[4:]
	m = re.match(r"^(.+?)[:,](\d{2,5})$", host)
	if m and "]" not in host:
		host, port = m.group(1), cint(port) or cint(m.group(2))
	return host, cint(port)


def _explain(e, host, port):
	"""Turn a driver error into what HR / IT should check."""
	text = str(e)
	low = text.lower()
	if "timed out" in low or "unavailable or does not exist" in low or "unreachable" in low:
		frappe.throw(_("This server cannot reach {0} on port {1} (no answer). Check the port number, and ask the database "
					   "owner to open that port in their firewall for this server's public IP address.").format(host, port),
					 title=_("Database not reachable"))
	if "login failed" in low or "18456" in low:
		frappe.throw(_("The database answered but refused the user name or password. Check them, and that the user may open "
					   "this database."), title=_("Login refused"))
	if "cannot open database" in low or "4060" in low:
		frappe.throw(_("Signed in, but the database name was not found or the user has no access to it."),
					 title=_("Database not found"))
	frappe.throw(_("Could not connect to the database: {0}").format(text[:300]))


def _connect(dev):
	from frappe.utils.password import get_decrypted_password

	password = get_decrypted_password(DEVICE, dev.name, "db_password", raise_exception=False) or ""
	kind = dev.db_type or ""
	host, port = _host_port(dev.db_host, dev.db_port)
	if kind.startswith("MySQL"):
		import pymysql

		return pymysql.connect(host=host, port=port or 3306, user=dev.db_user, password=password,
							   database=dev.db_name, connect_timeout=10), "%s"
	if kind == "PostgreSQL":
		import psycopg2

		return psycopg2.connect(host=host, port=port or 5432, user=dev.db_user, password=password,
								dbname=dev.db_name, connect_timeout=10), "%s"
	if kind == "SQL Server":
		try:
			import pymssql
		except ImportError:
			frappe.throw(_("SQL Server needs the pymssql package on the server: bench pip install pymssql"))
		try:
			return pymssql.connect(server=host, port=str(port or 1433), user=dev.db_user, password=password,
								   database=dev.db_name, login_timeout=10), "%s"
		except Exception as e:  # noqa: BLE001
			_explain(e, host, port or 1433)
	frappe.throw(_("Choose the database type."))


def _select(dev, since, limit=5000, until=False, inclusive=False):
	table, user, when, state, sn = _columns(dev)
	top = f"TOP {int(limit)} " if dev.db_type == "SQL Server" else ""
	tail = "" if dev.db_type == "SQL Server" else f" LIMIT {int(limit)}"
	upper = f" AND {when} <= %s" if until else ""
	return (f"SELECT {top}{user}, {when}, {state or 'NULL'}, {sn or 'NULL'} FROM {table} "  # identifiers checked by IDENT / presets
			f"WHERE {when} {'>=' if inclusive else '>'} %s{upper} ORDER BY {when}{tail}")


def _query(dev, sql, params=()):
	conn, _param = _connect(dev)
	try:
		cur = conn.cursor()
		cur.execute(sql, params)  # nosemgrep  # identifiers checked by IDENT / presets, values as parameters
		return cur.fetchall()
	finally:
		conn.close()


def pull(dev, since=None):
	"""Read new punches from the attendance software's database and ingest them, keeping the connection's health:
	each failure is recorded with its reason; when it works again HR is told it recovered (if it was reported down)."""
	try:
		out = _pull(dev, since)
	except Exception as e:  # noqa: BLE001
		frappe.db.rollback()
		reason = frappe.utils.strip_html(str(getattr(e, "message", None) or e)).strip()[:500] or type(e).__name__
		frappe.db.set_value(DEVICE, dev.name, {"last_error": reason, "failures": cint(dev.get("failures")) + 1,
											   "last_error_on": dev.get("last_error_on") or now_datetime()}, update_modified=False)
		frappe.db.commit()
		raise
	if cint(dev.get("failures")) or dev.get("last_error"):
		was_reported = dev.get("offline_alerted_on") and dev.get("last_error_on") and \
			get_datetime(dev.offline_alerted_on) >= get_datetime(dev.last_error_on)
		frappe.db.set_value(DEVICE, dev.name, {"last_error": None, "failures": 0, "last_error_on": None}, update_modified=False)
		if was_reported:
			from alphax_hr.api import alerts

			alerts.event("Device offline", _("Attendance database connected again: {0}").format(dev.device_name),
						 _("The connection works again and punches made meanwhile are being read now."),
						 url="/alphax/attendance-devices", doc=(DEVICE, dev.name), tag=f"offline-{dev.name}")
	return out


def _pull(dev, since=None):
	since = since or dev.db_last_time or "2000-01-01 00:00:00"
	data = _query(dev, _select(dev, since), (str(since),))
	touch(dev)
	out = _file(dev, data)
	if data:
		frappe.db.set_value(DEVICE, dev.name, "db_last_time", get_datetime(data[-1][1]).replace(microsecond=0, tzinfo=None),
							update_modified=False)
	return out


def _file(dev, data):
	"""Ingest rows (user, time, state, serial) under the terminal each was made on. Punches of terminals HR excluded
	(disabled) are skipped; read them later with a backfill."""
	if cint(dev.get("split_by_terminal")) and _columns(dev)[4]:
		groups = {}
		for r in data:
			groups.setdefault(str(r[3]).strip() if r[3] not in (None, "") else "", []).append(
				{"user": r[0], "time": r[1], "state": r[2]})
		out = {"skipped": 0}
		for sn, rows in groups.items():
			target = terminal(dev, sn) if sn else dev
			if target.name != dev.name and not cint(target.enabled):
				out["skipped"] += len(rows)
				continue
			if target.name != dev.name:
				latest = max(get_datetime(x["time"]) for x in rows).replace(microsecond=0, tzinfo=None)
				frappe.db.set_value(DEVICE, target.name, "last_contact", latest, update_modified=False)
			for k, v in ingest(target, rows, "Database pull").items():
				out[k] = out.get(k, 0) + v
		if len(out) == 1:
			out.update(ingest(dev, [], "Database pull"))
		return out
	return ingest(dev, [{"user": r[0], "time": r[1], "state": r[2]} for r in data], "Database pull")


def backfill(dev, start, end=None, chunk=5000):
	"""Read punches between ``start`` and ``end`` again (for history, or a terminal included later). Already imported
	punches are skipped; the regular pull position is not moved."""
	since, total = str(get_datetime(start)), {}
	end = str(get_datetime(end)) if end else None
	first = True
	while True:
		params = (since, end) if end else (since,)
		data = _query(dev, _select(dev, since, chunk, until=bool(end), inclusive=first), params)
		first = False
		for k, v in _file(dev, data).items():
			total[k] = total.get(k, 0) + v
		frappe.db.commit()
		if len(data) < chunk:
			break
		last = str(get_datetime(data[-1][1]).replace(microsecond=0, tzinfo=None))
		if last == since:
			break
		since = last
	return total


TERMINAL = "Via database source"
COPY = ("match_by", "punch_rule", "time_offset_minutes", "company", "brand", "db_in_values", "db_out_values")


def terminal(source, sn, **values):
	"""The device record for terminal ``sn`` of a database source; created the first time the terminal is seen.

	A device already registered with this serial number (for example one that also pushes) is reused, so punches are
	never split across two records; duplicates are ignored by ingest()."""
	sn = str(sn).strip()[:140]
	name = frappe.db.get_value(DEVICE, {"serial_number": sn}, "name")
	if name:
		values.pop("label", None)
		values.pop("enabled", None)  # HR's include / exclude choice is kept
		doc = frappe.get_doc(DEVICE, name)
		if values:
			frappe.db.set_value(DEVICE, name, values, update_modified=False)
		return doc
	base = (values.pop("label", None) or f"{source.device_name} · {sn}")[:140]
	label, n = base, 2
	while frappe.db.exists(DEVICE, label):
		label, n = f"{base} ({n})", n + 1
	values.setdefault("enabled", 1)
	doc = frappe.get_doc({"doctype": DEVICE, "device_name": label, "serial_number": sn, "connection": TERMINAL,
						  "source_device": source.name, "location": source.location, "branch": None,
						  "offline_alert_hours": 72, "split_by_terminal": 0,
						  **{k: source.get(k) for k in COPY}, **values})
	doc.insert(ignore_permissions=True)
	return doc


def _device_table(dev):
	"""{serial: (name, active)} from the source's devices table, when it has one."""
	m = mapping(dev)
	table, sn = _check(m.get("db_device_table"), True), _check(m.get("db_device_sn_column"))
	if not (table and sn):
		return {}
	name, active = _check(m.get("db_device_name_column")), _check(m.get("db_device_active_column"))
	try:
		rows = _query(dev, f"SELECT {sn}, {name or 'NULL'}, {active or '1'} FROM {table}")
	except Exception:  # noqa: BLE001  a missing devices table must not stop discovery
		frappe.log_error(title=f"AlphaX devices table: {dev.name}")
		return {}
	out = {}
	for code, label, on in rows:
		if code in (None, ""):
			continue
		flag = str(on).strip().lower() not in ("0", "false", "no", "n", "none", "") if on is not None else True
		out[str(code).strip()] = ((str(label).strip() or None) if label else None, flag)
	return out


def _people(dev):
	"""Names from the source's people table, kept as device users so unmatched punches show who they are."""
	m = mapping(dev)
	table, key, name = _check(m.get("db_emp_table"), True), _check(m.get("db_emp_key_column")), _check(m.get("db_emp_name_column"))
	if not (table and key and name):
		return 0
	try:
		rows = _query(dev, f"SELECT {key}, {name} FROM {table}")
	except Exception:  # noqa: BLE001
		frappe.log_error(title=f"AlphaX people table: {dev.name}")
		return 0
	have = {r.device_user: r for r in frappe.get_all("AlphaX Device User", filters={"device": dev.name},
													  fields=["name", "device_user", "user_name"])}
	n = 0
	for code, label in rows:
		code, label = str(code or "").strip(), str(label or "").strip()[:140]
		if not code or not label:
			continue
		if code in have:
			if have[code].user_name != label:
				frappe.db.set_value("AlphaX Device User", have[code].name, "user_name", label, update_modified=False)
			continue
		frappe.get_doc({"doctype": "AlphaX Device User", "device": dev.name, "device_user": code, "user_name": label}).insert(
			ignore_permissions=True)
		n += 1
	return n


def discover(dev):
	"""Find every terminal (serial number) in the source database and list it as its own device. No punches are read."""
	table, _u, when, _s, sn = _columns(dev)
	if not sn:
		frappe.throw(_("This database has no device column, so terminals cannot be told apart."))
	conn, _param = _connect(dev)
	try:
		cur = conn.cursor()
		cur.execute(f"SELECT {sn}, COUNT(*), MAX({when}) FROM {table} GROUP BY {sn}")  # nosemgrep  # identifiers checked
		data = cur.fetchall()
	finally:
		conn.close()
	touch(dev)
	listed = _device_table(dev)
	stats = {str(code).strip(): (count, last) for code, count, last in data if code not in (None, "")}
	for code in listed:
		stats.setdefault(code, (0, None))
	found, new = [], 0
	for code, (count, last) in stats.items():
		existed = frappe.db.exists(DEVICE, {"serial_number": code})
		values = {"punch_count": cint(count)}
		if code in listed:
			label, active = listed[code]
			values["source_active"] = 1 if active else 0
			if label:
				values["label"] = label
			values["enabled"] = 1 if active else 0
		if last:
			values["last_punch"] = values["last_contact"] = get_datetime(last).replace(microsecond=0, tzinfo=None)
		doc = terminal(dev, code, **values)
		new += 0 if existed else 1
		found.append({"name": doc.name, "serial_number": code, "punches": cint(count), "label": listed.get(code, (None,))[0],
					  "active": listed.get(code, (None, True))[1], "last": str(values.get("last_punch") or "") or None,
					  "new": not existed})
	_people(dev)
	if not cint(dev.get("split_by_terminal")):
		frappe.db.set_value(DEVICE, dev.name, "split_by_terminal", 1, update_modified=False)
	return {"terminals": found, "new": new}


# ------------------------------------------------------------------ schema: tables, columns, suggestions, preview
GUESS = {
	"db_table": ["checkinout", "iclock_transaction", "transaction", "punch", "attlog", "attendance", "checkinout_log"],
	"db_emp_table": ["empdetails", "userinfo", "personnel_employee", "employee", "employees", "users", "emp"],
	"db_device_table": ["devices", "machines", "iclock_terminal", "terminal", "terminals", "device"],
	"db_user_column": ["userid", "user_id", "emp_code", "empid", "emp_id", "badgenumber", "pin", "enrollnumber"],
	"db_time_column": ["checktime", "punch_time", "punchtime", "checkdatetime", "logtime", "datetime", "time"],
	"db_state_column": ["checktype", "punch_state", "punchstate", "state", "inoutmode", "type", "status"],
	"db_sn_column": ["sn", "terminal_sn", "serialnumber", "serial_number", "sensorid", "deviceid", "device_sn", "machineno"],
	"db_emp_id_column": ["id", "userid", "user_id", "empid", "emp_id"],
	"db_emp_key_column": ["nationalid", "national_id", "iqama", "iqamano", "idno", "ssn", "empno", "emp_code", "badgenumber"],
	"db_emp_name_column": ["empname", "name", "fullname", "full_name", "employeename", "first_name"],
	"db_device_sn_column": ["sn", "serialnumber", "serial_number", "terminal_sn"],
	"db_device_name_column": ["devicename", "device_name", "alias", "machinealias", "terminal_name", "name"],
	"db_device_active_column": ["isactive", "is_active", "active", "enabled", "state"],
}


def _norm(name):
	return re.sub(r"[^a-z0-9_]", "", (name or "").split(".")[-1].lower())


def guess(kind, names):
	"""The best of ``names`` for ``kind``: exact matches first, in the order of GUESS, then names containing a hint."""
	norm = {n: _norm(n) for n in names}
	for hint in GUESS.get(kind, []):
		for n, v in norm.items():
			if v == hint:
				return n
	for hint in GUESS.get(kind, []):
		if len(hint) < 4:
			continue
		for n, v in norm.items():
			if hint in v:
				return n
	return None


def tables(dev):
	kind = dev.db_type or ""
	if kind.startswith("MySQL"):
		rows = _query(dev, "SELECT table_name FROM information_schema.tables WHERE table_schema = %s ORDER BY table_name",
					  (dev.db_name,))
		return [r[0] for r in rows]
	rows = _query(dev, "SELECT table_schema, table_name FROM information_schema.tables "
					   "WHERE table_schema NOT IN ('information_schema', 'pg_catalog', 'sys') ORDER BY table_schema, table_name")
	return [f"{a}.{b}" for a, b in rows]


def columns(dev, table):
	_check(table, True)
	schema, _sep, name = table.rpartition(".")
	if (dev.db_type or "").startswith("MySQL"):
		rows = _query(dev, "SELECT column_name FROM information_schema.columns WHERE table_schema = %s AND table_name = %s "
						   "ORDER BY ordinal_position", (dev.db_name, name))
	elif schema:
		rows = _query(dev, "SELECT column_name FROM information_schema.columns WHERE table_schema = %s AND table_name = %s "
						   "ORDER BY ordinal_position", (schema, name))
	else:
		rows = _query(dev, "SELECT column_name FROM information_schema.columns WHERE table_name = %s ORDER BY ordinal_position",
					  (name,))
	return [r[0] for r in rows]


def suggest_mapping(dev):
	"""Read the database and propose the whole mapping: tables, then columns in each."""
	names = tables(dev)
	out = {"tables": names, "columns": {}, "mapping": {}}
	for kind, cols in (("db_table", ("db_user_column", "db_time_column", "db_state_column", "db_sn_column")),
					   ("db_emp_table", ("db_emp_id_column", "db_emp_key_column", "db_emp_name_column")),
					   ("db_device_table", ("db_device_sn_column", "db_device_name_column", "db_device_active_column"))):
		table = guess(kind, names)
		if not table:
			continue
		out["mapping"][kind] = table
		cs = columns(dev, table)
		out["columns"][table] = cs
		for c in cols:
			hit = guess(c, cs)
			if hit:
				out["mapping"][c] = hit
	return out


def preview(dev, limit=10):
	"""The latest punches as AlphaX will read them: user, time, IN/OUT, terminal, and the employee found."""
	table, user, when, state, sn = _columns(dev)
	top = f"TOP {int(limit)} " if dev.db_type == "SQL Server" else ""
	tail = "" if dev.db_type == "SQL Server" else f" LIMIT {int(limit)}"
	rows = _query(dev, f"SELECT {top}{user}, {when}, {state or 'NULL'}, {sn or 'NULL'} FROM {table} ORDER BY {when} DESC{tail}")
	out, states = [], set()
	for u, t, st, code in rows:
		emp = employee_for(dev, str(u or "").strip())
		states.add(None if st is None else str(st))
		out.append({"user": str(u), "time": str(t), "state": None if st is None else str(st), "terminal": code,
					"log_type": log_type(dev, st),
					"employee": emp, "employee_name": frappe.db.get_value("Employee", emp, "employee_name") if emp else None})
	return {"rows": out, "states": sorted(x for x in states if x is not None)}


def sync_status(dev, start=None, end=None):
	"""How far AlphaX has read and how complete it is: punches in the source vs. imported, per terminal, for a window."""
	table, _u, when, _s, sn = _columns(dev)
	start = get_datetime(start or getdate().replace(day=1))
	end = get_datetime(end) if end else None
	params = (str(start), str(end)) if end else (str(start),)
	cond = f"{when} >= %s" + (f" AND {when} <= %s" if end else "")
	oldest = _query(dev, f"SELECT MIN({when}) FROM {table}")[0][0]
	if sn:
		per = _query(dev, f"SELECT {sn}, COUNT(*) FROM {table} WHERE {cond} GROUP BY {sn}", params)
	else:
		per = [(None, _query(dev, f"SELECT COUNT(*) FROM {table} WHERE {cond}", params)[0][0])]
	offset = timedelta(minutes=cint(dev.time_offset_minutes))
	window = {"punch_time": [">=", start + offset]} if not end else {"punch_time": ["between", [start + offset, end + offset]]}
	terms = {}
	for t in frappe.get_all(DEVICE, filters={"source_device": dev.name}, fields=["name", "serial_number", "device_name", "enabled"]):
		terms[str(t.serial_number)] = t
	rows, available, synced = [], 0, 0
	for code, count in per:
		code = str(code).strip() if code not in (None, "") else ""
		t = terms.get(code)
		target = t.name if t else dev.name
		have = frappe.db.count(LOG, {"device": target, **window})
		if not t or cint(t.enabled):  # excluded terminals are not expected in AlphaX
			available += cint(count)
			synced += have
		rows.append({"serial_number": code or None, "device": target, "device_name": t.device_name if t else dev.device_name,
					 "included": bool(cint(t.enabled)) if t else True, "available": cint(count), "synced": have})
	return {"from": str(start), "to": str(end) if end else None, "oldest": str(oldest) if oldest else None,
			"watermark": str(dev.db_last_time) if dev.db_last_time else None,
			"last_success": str(dev.last_contact) if dev.last_contact else None, "connected": not cint(dev.get("failures")),
			"last_error": dev.get("last_error"), "available": available, "synced": synced,
			"gap": max(available - synced, 0), "terminals": sorted(rows, key=lambda r: -r["available"])}


def backfill_job(name, start, end=None):
	return backfill(frappe.get_doc(DEVICE, name), start, end)


def test_connection(dev):
	conn, _param = _connect(dev)
	try:
		table, _u, when, _s, sn = _columns(dev)
		cur = conn.cursor()
		cur.execute(f"SELECT COUNT(*), MAX({when}) FROM {table}")  # nosemgrep  # identifiers checked by IDENT / presets
		count, last = cur.fetchone()
		terminals = None
		if sn:
			cur.execute(f"SELECT COUNT(DISTINCT {sn}) FROM {table}")  # nosemgrep  # identifiers checked by IDENT / presets
			terminals = cur.fetchone()[0]
	finally:
		conn.close()
	return {"punches": count, "last": str(last) if last else None, "terminals": terminals}


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
							fields=["name", "device_name", "location", "last_contact", "offline_alert_hours", "offline_alerted_on",
									"connection", "last_error"]):
		last = get_datetime(d.last_contact)
		if last > now - timedelta(hours=cint(d.offline_alert_hours)):
			continue
		if d.offline_alerted_on and get_datetime(d.offline_alerted_on) >= last:
			continue  # already told for this outage
		from alphax_hr.api import alerts

		if (d.connection or "").startswith("Database pull"):
			alerts.event("Device offline", _("Attendance database not reachable: {0}").format(d.device_name),
						 _("No successful read since {0}. Punches are safe in the attendance database and are read as soon as the "
						   "connection works again. Reason: {1}").format(frappe.utils.format_datetime(last, "dd-MM-yyyy HH:mm"),
																		d.last_error or _("unknown")),
						 url="/alphax/attendance-devices", doc=(DEVICE, d.name), tag=f"offline-{d.name}")
			frappe.db.set_value(DEVICE, d.name, "offline_alerted_on", now, update_modified=False)
			continue
		if d.connection == TERMINAL:
			continue  # a terminal that is quiet may just be closed (weekend); its source is watched instead
		alerts.event("Device offline", _("Attendance device offline: {0}").format(d.device_name),
					 _("No contact since {0}{1}. Punches made meanwhile stay on the device and arrive when it reconnects; "
					   "check its power and network.").format(frappe.utils.format_datetime(last, "dd-MM-yyyy HH:mm"),
															  f" ({d.location})" if d.location else ""),
					 url="/alphax/attendance-devices", doc=(DEVICE, d.name), tag=f"offline-{d.name}")
		frappe.db.set_value(DEVICE, d.name, "offline_alerted_on", now, update_modified=False)
