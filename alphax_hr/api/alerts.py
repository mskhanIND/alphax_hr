"""One place that decides who hears about what, and how (email, in-app + phone push).

HR switches each event on/off and picks channels and recipients in AlphaX HR Settings → Notifications by event.
Every sender goes through ``event()``; a delivery failure is logged and never blocks the record being saved.
"""
from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import add_to_date, cint, get_datetime, get_url, getdate, now_datetime, nowdate

from alphax_hr.api._common import require_hr, require_hr_manager, parse_json

# event: (enabled, email, app, to_employee, to_manager, to_hr, minutes)
DEFAULTS = {
	"Leave request": (1, 1, 1, 0, 1, 0, 0),
	"Leave decision": (1, 1, 1, 1, 0, 0, 0),
	"Emergency leave": (1, 1, 1, 0, 1, 1, 0),
	"Request submitted": (1, 1, 1, 0, 1, 0, 0),
	"Request decision": (1, 1, 1, 1, 0, 0, 0),
	"Check-in confirmation": (1, 0, 1, 1, 0, 0, 0),
	"Late arrival": (1, 0, 1, 1, 1, 0, 0),
	"Missing check-in": (1, 0, 1, 1, 0, 0, 60),
	"Approval reminder": (1, 1, 1, 0, 1, 0, 0),
	"Approval escalation": (1, 1, 1, 0, 1, 1, 0),
	"Announcement": (1, 0, 1, 1, 0, 0, 0),
}
FLAGS = ("enabled", "email", "app", "to_employee", "to_manager", "to_hr", "minutes")
HELP = {
	"Leave request": "To the leave approver when an employee applies.",
	"Leave decision": "To the employee when leave is approved or rejected.",
	"Emergency leave": "At once, for leave types marked as emergency.",
	"Request submitted": "To whoever must act on a new request (manager or HR).",
	"Request decision": "To the employee when a request moves on or is decided.",
	"Check-in confirmation": "To the employee after each check-in and check-out.",
	"Late arrival": "When a check-in is later than the shift start plus grace (minutes = extra tolerance).",
	"Missing check-in": "When no check-in arrives this many minutes after the shift starts.",
	"Approval reminder": "To the approver when a request has waited the reminder hours.",
	"Approval escalation": "To the approver's manager (and HR) after the escalation hours.",
	"Announcement": "When HR publishes an announcement.",
}


def _defaults_row(event):
	return dict(zip(FLAGS, DEFAULTS[event]), event=event)


def seed_rules():
	"""Add missing events to settings (HR's choices are kept)."""
	if not frappe.db.exists("DocType", "AlphaX HR Settings"):
		return
	conf = frappe.get_single("AlphaX HR Settings")
	if not conf.meta.has_field("notify_rules"):
		return
	have = {r.event for r in conf.notify_rules}
	missing = [e for e in DEFAULTS if e not in have]
	if not missing:
		return
	for e in missing:
		conf.append("notify_rules", _defaults_row(e))
	conf.flags.ignore_mandatory = True
	conf.save(ignore_permissions=True)


def rule(event):
	conf = frappe.get_cached_doc("AlphaX HR Settings") if frappe.db.exists("DocType", "AlphaX HR Settings") else None
	for r in (conf.get("notify_rules") or []) if conf else []:
		if r.event == event:
			return frappe._dict({k: r.get(k) for k in FLAGS}, event=event)
	return frappe._dict(_defaults_row(event)) if event in DEFAULTS else None


def hr_users():
	users = frappe.get_all("Has Role", filters={"role": "HR Manager", "parenttype": "User"}, pluck="parent")
	return {u for u in users if u not in ("Administrator", "Guest") and frappe.db.get_value("User", u, "enabled")}


def employee_user(employee):
	return frappe.db.get_value("Employee", employee, "user_id") if employee else None


def manager_user(employee):
	boss = frappe.db.get_value("Employee", employee, "reports_to") if employee else None
	return frappe.db.get_value("Employee", boss, "user_id") if boss else None


def recipients(r, employee=None, managers=None):
	users = set()
	if cint(r.to_employee) and employee_user(employee):
		users.add(employee_user(employee))
	if cint(r.to_manager):
		users |= {u for u in (managers if managers is not None else [manager_user(employee)]) if u}
	if cint(r.to_hr):
		users |= hr_users()
	return {u for u in users if u not in ("Guest",)}


TARGETS = ("All employees", "Department", "Branch", "Designation", "Role", "Employee", "User")


def audience_users(target_type, target):
	"""Enabled users behind one audience row."""
	if target_type == "User":
		return {target} if target and frappe.db.get_value("User", target, "enabled") else set()
	if target_type == "Role":
		return {u for u in frappe.get_all("Has Role", filters={"role": target, "parenttype": "User"}, pluck="parent")
				if u not in ("Administrator", "Guest")}
	filters = {"status": "Active", "user_id": ["is", "set"]}
	if target_type == "Employee":
		filters["name"] = target
	elif target_type in ("Department", "Branch", "Designation"):
		filters[target_type.lower()] = target
	elif target_type != "All employees":
		return set()
	return set(frappe.get_all("Employee", filters=filters, pluck="user_id"))


def apply_audience(name, users, service=None):
	"""HR's extra recipients and exceptions for this event (and service): add first, then remove."""
	conf = frappe.get_cached_doc("AlphaX HR Settings") if frappe.db.exists("DocType", "AlphaX HR Settings") else None
	rows = [r for r in (conf.get("notify_audience") or []) if conf] if conf and conf.meta.has_field("notify_audience") else []
	rows = [r for r in rows if r.event in (name, "All events") and (not r.service or r.service == service)]
	users = set(users)
	for r in rows:
		if r.action == "Also notify":
			users |= audience_users(r.target_type, r.target)
	for r in rows:
		if r.action == "Never notify":
			users -= audience_users(r.target_type, r.target)
	return users


def _email_html(subject, message, url):
	link = get_url(url) if url else get_url("/alphax")
	return (f"<div style=\"font-family:system-ui,Segoe UI,Arial,sans-serif;font-size:14px;color:#111\">"
			f"<p style=\"font-size:16px;font-weight:600;margin:0 0 8px\">{frappe.utils.escape_html(subject)}</p>"
			f"<p style=\"margin:0 0 16px\">{frappe.utils.escape_html(message)}</p>"
			f"<a href=\"{link}\" style=\"display:inline-block;background:#0f766e;color:#fff;padding:8px 14px;"
			f"border-radius:8px;text-decoration:none\">{_('Open in {0}').format(frappe.utils.escape_html(frappe.get_cached_doc('AlphaX HR Settings').get('portal_title') or 'AlphaX HR'))}</a></div>")


def event(name, subject, message="", employee=None, managers=None, url="/alphax", doc=None, users=None, tag=None, service=None):
	"""Send ``name`` per HR's rule. ``managers``: approver users for this step (defaults to the reports-to manager).
	``users``: an explicit recipient set (overrides employee/manager/HR choice). ``service``: the request or leave type,
	for HR's per-service recipients and exceptions. Returns the users reached."""
	try:
		r = rule(name)
		if not r or not cint(r.enabled):
			return set()
		to = set(users) if users is not None else recipients(r, employee, managers)
		to = apply_audience(name, to, service)
		to = {u for u in to if u and frappe.db.get_value("User", u, "enabled")}
		if not to:
			return set()
		if cint(r.app):
			from alphax_hr.api import notify

			for u in to:
				log = frappe.get_doc({"doctype": "Notification Log", "for_user": u, "type": "Alert", "subject": subject,
									  "email_content": message, "from_user": frappe.session.user if frappe.session.user != "Guest" else None,
									  "document_type": doc[0] if doc else None, "document_name": doc[1] if doc else None,
									  "link": url or "/alphax"})
				log.flags.alphax_pushed = True
				log.insert(ignore_permissions=True)
			notify.send(list(to), subject, message or subject, url, tag=tag)
		if cint(r.email):
			emails = [e for e in (frappe.db.get_value("User", u, "email") for u in to) if e]
			if emails:
				frappe.sendmail(recipients=emails, subject=subject, message=_email_html(subject, message, url),
								reference_doctype=doc[0] if doc else None, reference_name=doc[1] if doc else None,
								delayed=True)
		return to
	except Exception:  # noqa: BLE001
		frappe.log_error(title=f"AlphaX notification: {name}")
		return set()


# ----------------------------------------------------------- settings API
@frappe.whitelist()
def settings():
	require_hr()
	seed_rules()
	conf = frappe.get_single("AlphaX HR Settings")
	rows = [{"event": r.event, **{k: cint(r.get(k)) for k in FLAGS}, "help": HELP.get(r.event, "")}
			for r in conf.get("notify_rules") or [] if r.event in DEFAULTS]
	rows.sort(key=lambda r: list(DEFAULTS).index(r["event"]))
	audience = [{k: r.get(k) for k in ("event", "service", "action", "target_type", "target")} for r in conf.get("notify_audience") or []] \
		if conf.meta.has_field("notify_audience") else []
	services = sorted(set(frappe.get_all("AlphaX Request Type", pluck="name") + frappe.get_all("Leave Type", pluck="name"))) \
		if frappe.db.exists("DocType", "AlphaX Request Type") else frappe.get_all("Leave Type", pluck="name")
	return {"rules": rows, "audience": audience, "services": services, "targets": list(TARGETS),
			"events": ["All events"] + list(DEFAULTS), "bell_all": cint(conf.get("bell_all")),
			"can_edit": bool(set(frappe.get_roles()) & {"HR Manager", "System Manager"}),
			"approval_remind_hours": cint(conf.get("approval_remind_hours")),
			"leave_escalation_hours": cint(conf.get("leave_escalation_hours"))}


@frappe.whitelist(methods=["POST"])
def save_settings(rules: str | dict | list, audience: str | dict | list | None = None, bell_all: int | str | None = None):
	require_hr_manager()
	rules = parse_json(rules) or []
	conf = frappe.get_single("AlphaX HR Settings")
	if audience is not None and conf.meta.has_field("notify_audience"):
		conf.set("notify_audience", [])
		for a in parse_json(audience) or []:
			if a.get("event") not in ["All events", *DEFAULTS] or a.get("target_type") not in TARGETS:
				frappe.throw(_("Check the extra recipients and exceptions: event or 'who' is not valid."))
			if a.get("target_type") != "All employees" and not (a.get("target") or "").strip():
				frappe.throw(_("Choose the {0} for each extra recipient or exception.").format(_(a.get("target_type")).lower()))
			conf.append("notify_audience", {"event": a["event"], "service": (a.get("service") or "").strip() or None,
											"action": "Never notify" if a.get("action") == "Never notify" else "Also notify",
											"target_type": a["target_type"], "target": (a.get("target") or "").strip() or None})
	if bell_all is not None and conf.meta.has_field("bell_all"):
		conf.bell_all = cint(bell_all)
	by_event = {r.event: r for r in conf.notify_rules}
	for row in rules:
		ev = row.get("event")
		if ev not in DEFAULTS:
			continue
		target = by_event.get(ev) or conf.append("notify_rules", _defaults_row(ev))
		for k in FLAGS:
			if k in row:
				target.set(k, cint(row[k]) if k != "minutes" else max(0, cint(row[k])))
	conf.save()
	frappe.clear_document_cache("AlphaX HR Settings", "AlphaX HR Settings")
	return settings()


# ------------------------------------------------------- my notifications
HR_DOCTYPES = ["Leave Application", "Leave Allocation", "Leave Encashment", "Compensatory Leave Request", "Attendance",
			   "Attendance Request", "Employee Checkin", "Shift Request", "Shift Assignment", "Expense Claim", "Employee Advance",
			   "Salary Slip", "Payroll Entry", "Additional Salary", "Salary Structure Assignment", "Appraisal",
			   "Employee Performance Feedback", "Employee", "Employee Grievance", "Employee Separation", "Employee Onboarding",
			   "Employee Promotion", "Employee Transfer", "Travel Request", "Full and Final Statement", "Training Event",
			   "Job Applicant", "Job Offer", "Interview"]
# Shown by the AlphaX bell unless HR turns on "The bell shows every notification".
HR_FILTERS = [["document_type", "in", HR_DOCTYPES], ["document_type", "like", "AlphaX %"], ["link", "like", "/alphax%"]]

@frappe.whitelist()
def inbox(limit: int | str = 30):
	user = frappe.session.user
	if user == "Guest":
		raise frappe.PermissionError
	hr_only = not cint(frappe.db.get_single_value("AlphaX HR Settings", "bell_all")) \
		if frappe.get_meta("AlphaX HR Settings").has_field("bell_all") else False
	or_filters = HR_FILTERS if hr_only else None
	rows = frappe.get_all("Notification Log", filters={"for_user": user}, or_filters=or_filters,
						  fields=["name", "subject", "email_content", "document_type", "document_name", "read", "creation", "type", "link"],
						  order_by="creation desc", limit=min(cint(limit) or 30, 100))
	for r in rows:
		r.subject = frappe.utils.strip_html(r.subject or "")
		r.email_content = frappe.utils.strip_html(r.email_content or "")[:240]
	unread = len(frappe.get_all("Notification Log", filters={"for_user": user, "read": 0}, or_filters=or_filters, pluck="name",
								 limit=1000))
	return {"items": rows, "unread": unread}


@frappe.whitelist(methods=["POST"])
def mark_read(name: str | None = None):
	user = frappe.session.user
	if user == "Guest":
		raise frappe.PermissionError
	filters = {"for_user": user, "read": 0}
	if name:
		filters["name"] = name
	hr_only = not cint(frappe.db.get_single_value("AlphaX HR Settings", "bell_all")) \
		if frappe.get_meta("AlphaX HR Settings").has_field("bell_all") else False
	# "Mark all read" only touches what the bell shows; other apps' alerts stay unread in the Desk.
	for n in frappe.get_all("Notification Log", filters=filters, or_filters=HR_FILTERS if hr_only and not name else None,
							pluck="name", limit=500):
		frappe.db.set_value("Notification Log", n, "read", 1, update_modified=False)
	return inbox()


# --------------------------------------------------------- attendance
def _shift_today(employee, day):
	from alphax_hr.api import shifts as sh
	from alphax_hr.api.attendance import _time
	from alphax_hr.saudi import attendance as att_rules

	default_shift = frappe.db.get_value("Employee", employee, "default_shift")
	shift, _a = sh.shift_on(employee, day, sh.assignments([employee], day, day), default_shift)
	st = sh.shift_types_map().get(shift) if shift else None
	if not st or st.start_time is None:  # 00:00 is a valid start
		return None, None
	start, _end = att_rules.shift_window(day, _time(st.start_time), _time(st.end_time))
	return st, start


def _late_grace(employee, st):
	from alphax_hr.api import attendance_policy

	pol = attendance_policy.for_employee(employee)
	if pol and pol.exempt:
		return None
	grace = int(st.late_entry_grace_period or 0)
	if pol and str(pol.late_grace_minutes or "").strip() != "":
		grace = cint(pol.late_grace_minutes)
	return grace


def on_checkin(employee, log_type, when, location=None):
	"""Called after a punch from the app: confirmation, and late arrival on the first IN of the day."""
	name = frappe.db.get_value("Employee", employee, "employee_name")
	where = f" · {location}" if location else ""
	event("Check-in confirmation", _("Checked {0} at {1}").format(_("in") if log_type == "IN" else _("out"), when.strftime("%H:%M")),
		  _("{0}{1}").format(name, where), employee=employee, url="/alphax/me/attendance", tag=f"punch-{employee}")
	if log_type != "IN":
		return
	day = getdate(when)
	earlier = frappe.db.count("Employee Checkin", {"employee": employee, "log_type": "IN",
												   "time": ["between", [f"{day} 00:00:00", when]]})
	if earlier > 1:
		return
	try:
		st, start = _shift_today(employee, day)
	except Exception:  # noqa: BLE001
		return
	if not st:
		return
	grace = _late_grace(employee, st)
	r = rule("Late arrival")
	if grace is None or not r:
		return
	late = int((get_datetime(when) - start).total_seconds() // 60)
	if late > grace + cint(r.minutes):
		event("Late arrival", _("{0} checked in {1} min late").format(name, late),
			  _("Shift {0} starts at {1}.").format(st.name, start.strftime("%H:%M")), employee=employee,
			  url="/alphax/me/attendance", tag=f"late-{employee}-{day}")


def missing_checkins():
	"""Every 15 minutes: employees whose shift started ``minutes`` ago with no IN punch, not on leave or holiday."""
	r = rule("Missing check-in")
	if not r or not cint(r.enabled):
		return
	from alphax_hr.api import shifts as sh

	now = now_datetime()
	day = getdate(nowdate())
	wait = cint(r.minutes) or 60
	emps = frappe.get_all("Employee", filters={"status": "Active", "user_id": ["is", "set"]},
														fields=["name", "employee_name", "default_shift", "holiday_list", "company"])
	if not emps:
		return
	ids = [e.name for e in emps]
	hols = sh.holidays(emps, day, day)
	leaves = sh.approved_leaves(ids, day, day)
	punched = set(frappe.get_all("Employee Checkin", filters={"employee": ["in", ids], "time": [">=", f"{day} 00:00:00"]},
								 pluck="employee"))
	assigned = sh.assignments(ids, day, day)
	types = sh.shift_types_map()
	sent = set(frappe.get_all("AlphaX Approval Reminder", filters={"reference_doctype": "Employee", "stage": "Missing check-in",
								"creation": [">=", f"{day} 00:00:00"]}, pluck="reference_name"))
	from alphax_hr.api import attendance_policy
	from alphax_hr.api.attendance import _time
	from alphax_hr.saudi import attendance as att_rules

	policies = attendance_policy.resolve([dict(e) for e in emps])
	for e in emps:
		if e.name in punched or e.name in sent or day in leaves.get(e.name, {}) or hols.get(e._holiday_list, {}).get(day):
			continue
		pol = policies.get(e.name)
		if pol and pol.exempt:
			continue
		shift, _a = sh.shift_on(e.name, day, assigned, e.default_shift)
		st = types.get(shift) if shift else None
		if not st or st.start_time is None:
			continue
		start, _end = att_rules.shift_window(day, _time(st.start_time), _time(st.end_time))
		if not (add_to_date(start, minutes=wait) <= now < add_to_date(start, hours=6)):
			continue
		to = event("Missing check-in", _("No check-in yet today"),
				   _("Your shift {0} started at {1}. Check in from the app, or ask for an attendance correction.").format(
					   st.name, start.strftime("%H:%M")), employee=e.name, url="/alphax/me/attendance", tag=f"miss-{e.name}-{day}")
		_log_reminder("Employee", e.name, "Missing check-in", None, to)


def _log_reminder(doctype, name, stage, approver, to):
	if not frappe.db.exists("DocType", "AlphaX Approval Reminder"):
		return
	frappe.get_doc({"doctype": "AlphaX Approval Reminder", "reference_doctype": doctype, "reference_name": name,
					"stage": stage, "approver": approver, "sent_to": ", ".join(sorted(to or []))[:1000]}).insert(ignore_permissions=True)
