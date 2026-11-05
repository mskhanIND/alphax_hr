"""ZKTeco ADMS / iClock push protocol: the device calls the site and sends its punches.

On the device: Menu → Comm. → Cloud Server Setting (ADMS): server address = this site's domain, port 443 (HTTPS) or 80.
The device is accepted only when its serial number is registered and enabled in AlphaX (Attendance devices); an unknown
device is listed there as a new disabled device for HR to enable. Allowed IP addresses can be set per device.

Endpoints (plain text, as the firmware expects):
  GET  /iclock/cdata?SN=...            handshake: options the device should use
  POST /iclock/cdata?SN=...&table=ATTLOG    punches: PIN TAB time TAB state ...
  POST /iclock/cdata?SN=...&table=OPERLOG   operation log, incl. USER PIN=.. Name=.. lines
  GET  /iclock/getrequest?SN=...       pending commands (C:<id>:<command>), or OK
  POST /iclock/devicecmd?SN=...        command results: ID=..&Return=..&CMD=..
"""
from __future__ import annotations

from urllib.parse import parse_qsl

import frappe
from frappe.utils import cint, now_datetime
from werkzeug.wrappers import Response

from alphax_hr import devices


def _text(body, status=200):
	return Response(body, status=status, mimetype="text/plain")


class ADMSRenderer:
	"""Frappe page renderer for /iclock/* (hooks.page_renderer)."""

	def __init__(self, path=None, http_status_code=None):
		self.path = (path or frappe.local.request.path).strip("/ ")

	def can_render(self):
		return self.path.lower().startswith("iclock/") or self.path.lower() == "iclock"

	def render(self):
		try:
			return handle(self.path.split("/", 1)[-1].lower(), frappe.local.request)
		except Exception:  # noqa: BLE001
			frappe.log_error(title="AlphaX ADMS")
			return _text("ERROR", 500)


def _body(request):
	data = request.get_data(cache=False) or b""
	return data.decode("utf-8", errors="ignore")


def handle(endpoint, request):
	args = request.args
	sn = (args.get("SN") or args.get("sn") or "").strip()
	ip = request.headers.get("X-Real-IP") or request.headers.get("X-Forwarded-For", "").split(",")[0].strip() or request.remote_addr
	frappe.local.flags.commit = True  # GET handshakes also update the device's last contact
	if endpoint in ("ping",):
		return _text("OK")
	dev = devices.device_by_sn(sn)
	if not dev:
		if sn and endpoint == "cdata" and not frappe.db.exists(devices.DEVICE, {"serial_number": sn}):
			_register_unknown(sn, ip)
		return _text("UNKNOWN DEVICE", 403)
	if not cint(dev.enabled) or not devices.ip_allowed(dev, ip):
		return _text("DEVICE NOT ALLOWED", 403)
	if endpoint == "cdata" and request.method == "GET":
		devices.touch(dev, ip)
		return _text(_options(dev))
	if endpoint == "cdata":
		table = (args.get("table") or "").upper()
		body = _body(request)
		if table == "ATTLOG":
			rows = _attlog(body)
			out = devices.ingest(dev, rows, "Device push")
			devices.touch(dev, ip, log_stamp=args.get("Stamp") or dev.log_stamp)
			return _text(f"OK: {out['received']}")
		if table == "OPERLOG":
			_users(dev, body)
			devices.touch(dev, ip, oplog_stamp=args.get("OpStamp") or args.get("Stamp") or dev.oplog_stamp)
			return _text("OK")
		if table in ("OPTIONS", "INFO") or body.startswith("~"):
			_info(dev, body)
		devices.touch(dev, ip)
		return _text("OK")
	if endpoint == "getrequest":
		info = args.get("INFO")
		extra = {}
		if info:
			parts = info.split(",")
			extra["model"] = parts[0][:140]
			if len(parts) > 1 and parts[1].isdigit():
				extra["user_count"] = cint(parts[1])
		devices.touch(dev, ip, **extra)
		return _text(_commands(dev))
	if endpoint == "devicecmd":
		_results(dev, _body(request))
		devices.touch(dev, ip)
		return _text("OK")
	devices.touch(dev, ip)
	return _text("OK")  # fdata (photos), registry and other firmware calls


def _register_unknown(sn, ip):
	doc = frappe.get_doc({"doctype": devices.DEVICE, "device_name": f"New device {sn}"[:140], "serial_number": sn, "enabled": 0,
						  "brand": "ZKTeco", "connection": "Device push (ZKTeco ADMS / iClock)", "last_contact": now_datetime(),
						  "last_ip": ip})
	doc.insert(ignore_permissions=True)


def _options(dev):
	return "\n".join([
		f"GET OPTION FROM: {dev.serial_number}",
		f"ATTLOGStamp={dev.log_stamp or 0}",
		f"OPERLOGStamp={dev.oplog_stamp or 0}",
		"ATTPHOTOStamp=None",
		"ErrorDelay=30",
		"Delay=10",
		"TransTimes=00:00;14:05",
		"TransInterval=1",
		"TransFlag=TransData AttLog OpLog EnrollUser ChgUser",
		"Realtime=1",
		"Encrypt=None",
	]) + "\n"


def _attlog(body):
	rows = []
	for line in body.splitlines():
		parts = line.strip().split("\t")
		if len(parts) >= 2 and parts[0] and parts[1]:
			rows.append({"user": parts[0].strip(), "time": parts[1].strip(), "state": parts[2].strip() if len(parts) > 2 else None})
	return rows


def _users(dev, body):
	"""USER PIN=12  Name=Ahmed ... lines: remember who is on the device, for matching to employees."""
	for line in body.splitlines():
		line = line.strip()
		if not line.upper().startswith("USER "):
			continue
		fields = dict(p.split("=", 1) for p in line[5:].split("\t") if "=" in p)
		pin = (fields.get("PIN") or "").strip()
		if not pin:
			continue
		name = frappe.db.get_value("AlphaX Device User", {"device": dev.name, "device_user": pin}, "name")
		values = {"user_name": (fields.get("Name") or "").strip()[:140]}
		if name:
			frappe.db.set_value("AlphaX Device User", name, values, update_modified=False)
		else:
			frappe.get_doc({"doctype": "AlphaX Device User", "device": dev.name, "device_user": pin, **values}).insert(ignore_permissions=True)


def _info(dev, body):
	info = dict(p.split("=", 1) for p in body.replace("~", "").replace(",", "\n").splitlines() if "=" in p)
	model = " ".join(x for x in (info.get("DeviceName"), info.get("FWVersion") or info.get("FirmVer")) if x)
	values = {}
	if model:
		values["model"] = model[:140]
	if (info.get("UserCount") or "").isdigit():
		values["user_count"] = cint(info["UserCount"])
	if values:
		frappe.db.set_value(devices.DEVICE, dev.name, values, update_modified=False)


COMMAND_TEXT = {"Reboot": "REBOOT", "Read device info": "INFO"}


def command_lines(cmd):
	if cmd.command in COMMAND_TEXT:
		return [COMMAND_TEXT[cmd.command]]
	return [x for x in (cmd.payload or "").splitlines() if x.strip()]


def _commands(dev):
	pending = frappe.get_all("AlphaX Device Command", filters={"device": dev.name, "status": "Pending"},
							 fields=["name", "command", "payload"], order_by="creation asc", limit=20)
	if not pending:
		return "OK"
	out = []
	for cmd in pending:
		for i, line in enumerate(command_lines(cmd)):
			out.append(f"C:{cmd.name}.{i}:{line}")
		frappe.db.set_value("AlphaX Device Command", cmd.name, {"status": "Sent", "sent_at": now_datetime()}, update_modified=False)
	return "\n".join(out) + "\n"


def _results(dev, body):
	for line in body.splitlines():
		fields = dict(parse_qsl(line.strip()))
		ident = (fields.get("ID") or "").split(".")[0]
		if not ident or not frappe.db.exists("AlphaX Device Command", {"name": ident, "device": dev.name}):
			continue
		ok = str(fields.get("Return", "0")).strip() in ("0", "")
		prev = frappe.db.get_value("AlphaX Device Command", ident, "status")
		frappe.db.set_value("AlphaX Device Command", ident, {
			"status": "Failed" if not ok or prev == "Failed" else "Done",
			"result": f"{fields.get('CMD', '')} → {fields.get('Return', '')}"[:300]}, update_modified=False)
