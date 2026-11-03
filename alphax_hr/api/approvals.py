"""One approval inbox for managers and HR across HRMS request types.

If a doctype has an active Workflow, only the transitions Frappe offers the
user are allowed (any action name, including one literally called "Submit").
Without a workflow, the named approver (or HR) may approve or reject.
"""
from __future__ import annotations

import frappe
from frappe import _
from frappe.model.workflow import apply_workflow, get_transitions, get_workflow_name
from frappe.utils import cint

from alphax_hr.api._common import is_hr, login_required

# doctype -> how a non-workflow approval works
SOURCES = {
	"Leave Application": {
		"approver_field": "leave_approver",
		"open": {"status": "Open"},
		"status_field": "status",
		"values": {"Approve": "Approved", "Reject": "Rejected"},
		"fields": ["employee", "employee_name", "leave_type", "from_date", "to_date", "total_leave_days", "description", "status",
				   "alphax_event_date", "alphax_relation", "alphax_sick_breakdown"],
		"submit_on_decision": True,
	},
	"Expense Claim": {
		"approver_field": "expense_approver",
		"open": {"approval_status": "Draft"},
		"status_field": "approval_status",
		"values": {"Approve": "Approved", "Reject": "Rejected"},
		"fields": ["employee", "employee_name", "posting_date", "total_claimed_amount", "approval_status", "remark"],
		"submit_on_decision": False,  # accounts submit after payment set-up
	},
	"Attendance Request": {
		"approver_field": None,
		"open": {},
		"status_field": None,
		"values": {"Approve": None},
		"fields": ["employee", "employee_name", "from_date", "to_date", "reason", "explanation"],
		"submit_on_decision": True,
	},
	"Shift Request": {
		"approver_field": "approver",
		"open": {"status": "Draft"},
		"status_field": "status",
		"values": {"Approve": "Approved", "Reject": "Rejected"},
		"fields": ["employee", "employee_name", "shift_type", "from_date", "to_date", "status"],
		"submit_on_decision": True,
	},
	"Compensatory Leave Request": {
		"approver_field": None,
		"open": {},
		"status_field": None,
		"values": {"Approve": None},
		"fields": ["employee", "employee_name", "leave_type", "work_from_date", "work_end_date", "reason"],
		"submit_on_decision": True,
	},
	# AlphaX's own requests run on alphax_hr.api.requests (not docstatus based).
	"AlphaX Request": {
		"engine": "alphax_hr.api.requests",
		"approver_open": "Pending Manager",
		"closed": ["Completed", "Rejected", "Cancelled"],
		"approver_field": "approver",
		"open": {"status": ["in", ["Pending Manager", "Pending HR", "Pending Management", "Approved"]]},
		"management_open": "Pending Management",
		"status_field": "status",
		"values": {"Approve": None, "Reject": None},
		"fields": ["employee", "employee_name", "request_type", "status", "due_on", "reason", "details"],
		"submit_on_decision": False,
	},
	"AlphaX Leave Plan": {
		"engine": "alphax_hr.api.leave_plan",
		"approver_open": "Submitted",
		"closed": ["Approved", "Rejected", "Changes requested"],
		"approver_field": "approver",
		"open": {"status": "Submitted"},
		"status_field": "status",
		"values": {"Approve": None, "Reject": None},
		"fields": ["employee", "employee_name", "year", "status", "total_days", "entitlement", "department"],
		"submit_on_decision": False,
	},
}


def _installed(dt):
	return bool(frappe.db.exists("DocType", dt))


def _row_fields(dt):
	meta = frappe.get_meta(dt)
	base = ["name", "owner", "modified", "docstatus"]
	return base + [f for f in SOURCES[dt]["fields"] if meta.has_field(f)] + (
		[meta.get("workflow_state_field") or "workflow_state"] if meta.has_field("workflow_state") else []
	)


def _actions_for(doc, user, workflow):
	if SOURCES[doc.doctype].get("engine"):
		return [a for a in frappe.get_attr(SOURCES[doc.doctype]["engine"] + ".actions_for")(doc, user) if a != "Cancel"]
	if workflow:
		return [t.action for t in get_transitions(doc)]
	conf = SOURCES[doc.doctype]
	if doc.docstatus != 0 or doc.owner == user and not is_hr(user):
		return []
	approver_field = conf["approver_field"]
	if approver_field and doc.get(approver_field) != user and not is_hr(user):
		return []
	if not approver_field and not is_hr(user):
		return []
	return list(conf["values"].keys())


@frappe.whitelist()
def inbox(doctype=None, limit=100):
	user = login_required()
	results = []
	targets = [doctype] if doctype in SOURCES else list(SOURCES)
	for dt in targets:
		if not _installed(dt) or not frappe.has_permission(dt, "read"):
			continue
		workflow = get_workflow_name(dt)
		filters = {"docstatus": 0}
		or_filters = None
		conf = SOURCES[dt]
		if conf.get("engine"):
			workflow = None
			filters.update(conf["open"])
			if not is_hr(user):
				extra = conf.get("management_open")
				if extra and frappe.get_attr(conf["engine"] + ".is_management")(user):
					filters["status"] = ["in", [conf["approver_open"], extra]]
					or_filters = [[dt, "approver", "=", user], [dt, "status", "=", extra]]
				else:
					filters["approver"] = user
					filters["status"] = conf["approver_open"]
		elif not workflow:
			filters.update(conf["open"])
			if conf["approver_field"] and not is_hr(user):
				filters[conf["approver_field"]] = user
		rows = frappe.get_list(dt, filters=filters, or_filters=or_filters, fields=list(dict.fromkeys(_row_fields(dt))),
							   order_by="modified desc", page_length=min(cint(limit) or 100, 200))
		for row in rows:
			doc = frappe.get_doc(dt, row.name)
			actions = _actions_for(doc, user, workflow)
			if not actions:
				continue
			row.update({"doctype": dt, "actions": actions, "workflow": bool(workflow),
						"attachments": frappe.db.count("File", {"attached_to_doctype": dt, "attached_to_name": row.name})})
			results.append(row)
	results.sort(key=lambda r: str(r.get("modified")), reverse=True)
	counts = {}
	for r in results:
		counts[r["doctype"]] = counts.get(r["doctype"], 0) + 1
	return {"items": results, "counts": counts, "total": len(results)}


@frappe.whitelist()
def act(doctype, name, action, comment=None):
	user = login_required()
	if doctype not in SOURCES:
		frappe.throw(_("Unsupported request type."), frappe.PermissionError)
	if SOURCES[doctype].get("engine"):
		return frappe.get_attr(SOURCES[doctype]["engine"] + ".decide")(name, action, comment)
	doc = frappe.get_doc(doctype, name)
	doc.check_permission("read")
	workflow = get_workflow_name(doctype)
	allowed = _actions_for(doc, user, workflow)
	if action not in allowed:
		frappe.throw(_("You cannot perform '{0}' on this request.").format(action), frappe.PermissionError)
	if comment:
		doc.add_comment("Comment", frappe.utils.escape_html(str(comment)[:2000]))
	if workflow:
		doc = apply_workflow(doc, action)
	else:
		conf = SOURCES[doctype]
		value = conf["values"].get(action)
		if conf["status_field"] and value:
			doc.set(conf["status_field"], value)
			doc.save()
		if conf["submit_on_decision"] and (action == "Approve" or conf["status_field"]):
			doc.check_permission("submit")
			doc.submit()
	return {"name": doc.name, "docstatus": doc.docstatus, "status": doc.get("status") or doc.get("approval_status"),
			"workflow_state": doc.get("workflow_state")}


def _who(user):
	return {"user": user, "name": frappe.utils.get_fullname(user) if user else None}


def pending_with(doc):
	"""Who the request is waiting for: workflow roles, the named approver, or HR."""
	engine = SOURCES.get(doc.doctype, {}).get("engine")
	if engine == "alphax_hr.api.requests":
		if doc.status == "Pending Manager" and doc.approver:
			return [_who(doc.approver)]
		return [{"role": "HR Manager"}] if doc.status in ("Pending HR", "Approved") else []
	if engine:
		return frappe.get_attr(engine + ".pending_with")(doc)
	if doc.docstatus != 0:
		return []
	workflow = get_workflow_name(doc.doctype)
	if workflow:
		state = doc.get(doc.meta.get("workflow_state_field") or "workflow_state")
		roles = frappe.get_all("Workflow Transition", filters={"parent": workflow, "state": state}, pluck="allowed", distinct=True)
		return [{"role": r} for r in roles]
	field = SOURCES[doc.doctype]["approver_field"]
	if field and doc.get(field):
		return [_who(doc.get(field))]
	return [{"role": "HR Manager"}]


@frappe.whitelist()
def activity(doctype, name):
	"""Full trail of one request (see alphax_hr.api.activity.trail)."""
	if doctype not in SOURCES:
		frappe.throw(_("Unsupported request type."), frappe.PermissionError)
	from alphax_hr.api.activity import trail

	return trail(doctype, name)


@frappe.whitelist()
def decided(doctype=None, limit=50):
	"""Requests that are no longer waiting (approved, rejected, cancelled) that the user may read."""
	user = login_required()
	out = []
	for dt in ([doctype] if doctype in SOURCES else list(SOURCES)):
		if not _installed(dt) or not frappe.has_permission(dt, "read"):
			continue
		conf = SOURCES[dt]
		filters = {"status": ["in", conf["closed"]]} if conf.get("engine") else {"docstatus": ["in", [1, 2]]}
		or_filters = None
		if conf.get("engine") and not is_hr(user):
			or_filters = [[dt, "approver", "=", user], [dt, "decided_by", "=", user]]  # includes management decisions
		elif conf["approver_field"] and not is_hr(user):
			filters[conf["approver_field"]] = user
		rows = frappe.get_list(dt, filters=filters, or_filters=or_filters, fields=list(dict.fromkeys(_row_fields(dt))),
							   order_by="modified desc", page_length=min(cint(limit) or 50, 200))
		for r in rows:
			r["doctype"] = dt
			out.append(r)
	out.sort(key=lambda r: str(r.get("modified")), reverse=True)
	return {"items": out[: min(cint(limit) or 50, 200)]}


@frappe.whitelist()
def team_leave_calendar(start, end):
	"""Approved/open leave of employees the user approves (or everyone for HR)."""
	user = login_required()
	filters = {"from_date": ["<=", end], "to_date": [">=", start], "status": ["in", ["Open", "Approved"]], "docstatus": ["<", 2]}
	if not is_hr(user):
		filters["leave_approver"] = user
	return frappe.get_list(
		"Leave Application", filters=filters,
		fields=["name", "employee", "employee_name", "leave_type", "from_date", "to_date", "status", "total_leave_days"],
		order_by="from_date asc", page_length=500,
	)
