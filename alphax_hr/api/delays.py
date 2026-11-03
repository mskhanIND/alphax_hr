"""Approval delay control: remind slow approvers, escalate to their manager and HR, and show where requests wait."""
from __future__ import annotations

from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import add_days, cint, get_datetime, now_datetime

from alphax_hr.api import alerts
from alphax_hr.api._common import is_hr, login_required
from alphax_hr.api.approvals import SOURCES

HR = "HR"
MANAGEMENT = "Management"
LINKS = {"Leave Application": "/alphax/approvals", "AlphaX Request": "/alphax/approvals", "AlphaX Leave Plan": "/alphax/approvals",
		 "Expense Claim": "/alphax/approvals", "Attendance Request": "/alphax/approvals", "Shift Request": "/alphax/approvals",
		 "Compensatory Leave Request": "/alphax/approvals"}
LABELS = {"Leave Application": "Leave", "AlphaX Request": "Request", "AlphaX Leave Plan": "Vacation plan",
		  "Expense Claim": "Expense", "Attendance Request": "Attendance correction", "Shift Request": "Shift change",
		  "Compensatory Leave Request": "Compensatory leave"}


def _hours():
	conf = frappe.get_cached_doc("AlphaX HR Settings")
	return cint(conf.get("approval_remind_hours")), cint(conf.get("leave_escalation_hours"))


def pending_items():
	"""Every open approval with who it waits for and since when."""
	out = []
	for dt, conf in SOURCES.items():
		if not frappe.db.exists("DocType", dt):
			continue
		meta = frappe.get_meta(dt)
		fields = ["name", "creation", "employee", "employee_name"]
		if conf.get("approver_field") and meta.has_field(conf["approver_field"]):
			fields.append(conf["approver_field"])
		if conf.get("status_field") and meta.has_field(conf["status_field"]):
			fields.append(conf["status_field"])
		if meta.has_field("decided_on"):
			fields.append("decided_on")
		for extra in ("leave_type", "request_type"):
			if meta.has_field(extra):
				fields.append(extra)
		filters = {"docstatus": 0, **conf["open"]}
		for row in frappe.get_all(dt, filters=filters, fields=list(dict.fromkeys(fields)), limit=2000):
			status = row.get(conf.get("status_field") or "") if conf.get("status_field") else None
			approver = row.get(conf.get("approver_field") or "") if conf.get("approver_field") else None
			waiting_since = row.creation
			if conf.get("engine"):
				if status != conf["approver_open"]:
					approver = MANAGEMENT if status == conf.get("management_open") else HR  # after the manager, or HR-only types
					waiting_since = row.get("decided_on") or row.creation
			if not approver:
				approver = HR
			out.append(frappe._dict(doctype=dt, name=row.name, employee=row.employee, employee_name=row.employee_name,
									what=row.get("leave_type") or row.get("request_type") or _(LABELS.get(dt, dt)),
									status=status, approver=approver, since=get_datetime(waiting_since)))
	return out


def _approver_users(approver):
	if approver == MANAGEMENT:
		from alphax_hr.api.requests import management_users

		return management_users()
	return list(alerts.hr_users()) if approver == HR else [approver]


def _group_name(approver):
	return {HR: _("HR team"), MANAGEMENT: _("Management")}.get(approver) or frappe.utils.get_fullname(approver)


def _approver_manager(approver):
	if approver in (HR, MANAGEMENT):
		return []
	emp = frappe.db.get_value("Employee", {"user_id": approver, "status": "Active"}, "name")
	boss = alerts.manager_user(emp) if emp else None
	return [boss] if boss and boss != approver else []


def _already(item, stage):
	return frappe.db.exists("AlphaX Approval Reminder", {"reference_doctype": item.doctype, "reference_name": item.name,
														 "stage": stage, "approver": item.approver})


def escalate_pending_approvals():
	"""Hourly: one reminder after the reminder hours, one escalation after the escalation hours, per approval step."""
	if not frappe.db.exists("DocType", "AlphaX Approval Reminder"):
		return
	remind, escalate = _hours()
	if not remind and not escalate:
		return
	now = now_datetime()
	for item in pending_items():
		age = (now - item.since).total_seconds() / 3600
		subject_bits = f"{item.employee_name or ''} · {item.what}"
		ref = (item.doctype, item.name)
		if escalate and age >= escalate and not _already(item, "Escalation"):
			to = alerts.event("Approval escalation", _("Waiting {0} hours: {1}").format(int(age), subject_bits),
							  _("Pending with {0} since {1}.").format(_group_name(item.approver),
																  frappe.utils.format_datetime(item.since, "dd-MM-yyyy HH:mm")),
							  employee=item.employee, managers=_approver_manager(item.approver) + _approver_users(item.approver),
							  url=LINKS.get(item.doctype, "/alphax/approvals"), doc=ref, tag=f"esc-{item.name}")
			alerts._log_reminder(item.doctype, item.name, "Escalation", item.approver, to)
			if not _already(item, "Reminder"):
				alerts._log_reminder(item.doctype, item.name, "Reminder", item.approver, set())  # escalation covers it
		elif remind and age >= remind and not _already(item, "Reminder"):
			to = alerts.event("Approval reminder", _("Waiting for your decision: {0}").format(subject_bits),
							  _("Submitted {0}, about {1} hours ago.").format(frappe.utils.format_datetime(item.since, "dd-MM-yyyy HH:mm"), int(age)),
							  employee=item.employee, managers=_approver_users(item.approver),
							  url=LINKS.get(item.doctype, "/alphax/approvals"), doc=ref, tag=f"rem-{item.name}")
			alerts._log_reminder(item.doctype, item.name, "Reminder", item.approver, to)


def _turnaround(days=90):
	"""Average hours from submission to decision, per decider, over recent decisions."""
	since = add_days(now_datetime(), -days)
	per = defaultdict(list)
	for dt in ("AlphaX Request", "AlphaX Leave Plan"):
		if frappe.db.exists("DocType", dt):
			for r in frappe.get_all(dt, filters={"decided_on": [">=", since], "decided_by": ["is", "set"]},
									fields=["decided_by", "creation", "decided_on"], limit=5000):
				per[r.decided_by].append((get_datetime(r.decided_on) - get_datetime(r.creation)).total_seconds() / 3600)
	for r in frappe.get_all("Leave Application", filters={"docstatus": 1, "modified": [">=", since], "status": ["in", ["Approved", "Rejected"]]},
							fields=["leave_approver", "modified_by", "creation", "modified"], limit=5000):
		per[r.modified_by or r.leave_approver].append((get_datetime(r.modified) - get_datetime(r.creation)).total_seconds() / 3600)
	return {u: (round(sum(v) / len(v), 1), len(v)) for u, v in per.items() if v}


@frappe.whitelist()
def report():
	"""Where requests wait. HR sees everything; a manager sees what waits for them and their team's approvers."""
	user = login_required()
	hr = is_hr(user)
	remind, escalate = _hours()
	now = now_datetime()
	items = pending_items()
	if not hr:
		from alphax_hr.api.requests import is_management

		mgmt = is_management(user)
		items = [i for i in items if i.approver == user or (mgmt and i.approver == MANAGEMENT)]
	marks = {(r.reference_doctype, r.reference_name, r.stage) for r in frappe.get_all(
		"AlphaX Approval Reminder", filters={"reference_name": ["in", [i.name for i in items] or ["-"]]},
		fields=["reference_doctype", "reference_name", "stage"])} if frappe.db.exists("DocType", "AlphaX Approval Reminder") else set()
	rows = []
	for i in items:
		age = round((now - i.since).total_seconds() / 3600, 1)
		if (i.doctype, i.name, "Escalation") in marks:
			stage = "Escalated"
		elif escalate and age >= escalate:
			stage = "Overdue"
		elif (i.doctype, i.name, "Reminder") in marks:
			stage = "Reminded"
		else:
			stage = "On time"
		rows.append({"doctype": i.doctype, "name": i.name, "kind": _(LABELS.get(i.doctype, i.doctype)), "what": i.what,
					 "employee": i.employee, "employee_name": i.employee_name, "status": i.status,
					 "approver": i.approver, "approver_name": _group_name(i.approver),
					 "since": str(i.since), "age_hours": age, "stage": stage})
	rows.sort(key=lambda r: -r["age_hours"])
	turn = _turnaround() if hr else {}
	by = defaultdict(lambda: {"pending": 0, "oldest_hours": 0, "overdue": 0})
	for r in rows:
		b = by[r["approver"]]
		b["approver"], b["approver_name"] = r["approver"], r["approver_name"]
		b["pending"] += 1
		b["oldest_hours"] = max(b["oldest_hours"], r["age_hours"])
		b["overdue"] += 1 if r["stage"] in ("Escalated", "Overdue") else 0
	for u, (avg, n) in turn.items():
		b = by[u]
		b.setdefault("approver", u)
		b.setdefault("approver_name", frappe.utils.get_fullname(u))
		b["avg_hours"], b["decided"] = avg, n
	approvers = sorted(by.values(), key=lambda b: (-b["overdue"], -b["pending"]))
	return {"rows": rows, "approvers": approvers, "remind_hours": remind, "escalate_hours": escalate, "is_hr": hr,
			"counts": {s: sum(1 for r in rows if r["stage"] == s) for s in ("On time", "Reminded", "Overdue", "Escalated")}}
