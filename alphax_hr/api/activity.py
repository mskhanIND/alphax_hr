"""System-wide activity trail for HR records: who changed what, and when.

Built on Frappe's own audit data (Version, Comment, Workflow Action, File,
Deleted Document), so it covers changes made in /alphax, in the desk, by
imports and by scheduled jobs alike.
"""
from __future__ import annotations

from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import add_days, cint, getdate, nowdate

from alphax_hr.api._common import login_required, require_hr

AUDITED = (
	"Employee", "Leave Application", "Leave Allocation", "Leave Type", "Leave Policy Assignment", "Compensatory Leave Request",
	"Attendance", "Attendance Request", "Employee Checkin", "Shift Type", "Shift Assignment", "Shift Request",
	"Holiday List", "Expense Claim", "Employee Advance", "Salary Structure Assignment", "Salary Slip", "Payroll Entry",
	"Additional Salary", "Employee Separation", "AlphaX Request", "AlphaX Request Type", "AlphaX Penalty", "AlphaX Violation Type", "AlphaX Payroll Period", "AlphaX Final Settlement", "Appraisal", "Appraisal Cycle", "Full and Final Statement", "AlphaX HR Settings",
)
SKIP_FIELDS = {"modified", "modified_by", "idx", "lft", "rgt", "old_parent", "_user_tags", "_comments", "_assign",
			   "_liked_by", "_seen"}
COMMENT_TYPES = ["Comment", "Workflow", "Info", "Attachment", "Attachment Removed", "Submitted", "Cancelled",
				 "Assigned", "Assignment Completed", "Shared", "Unshared", "Edit", "Deleted", "Created"]


def _audited(dt):
	return dt in AUDITED and frappe.db.exists("DocType", dt)


def _who(user):
	return {"user": user, "name": frappe.utils.get_fullname(user) if user else None}


def _label(meta, field):
	if field == "docstatus":
		return _("Document status")
	return _(meta.get_label(field)) if meta.has_field(field) else field


def _version_changes(meta, data):
	changes = [{"field": f, "label": _label(meta, f), "from": old, "to": new}
			   for f, old, new in data.get("changed", []) if f not in SKIP_FIELDS]
	for key, verb in (("added", "added"), ("removed", "removed")):
		for table, row in data.get(key, []) or []:
			changes.append({"field": table, "label": f"{_label(meta, table)} · {_(verb)}", "from": None,
							"to": ", ".join(f"{k}: {v}" for k, v in (row or {}).items()
											if k not in ("name", "idx", "parent", "parenttype", "parentfield", "doctype", "owner", "creation", "modified", "modified_by", "docstatus"))[:300]})
	for table, idx, name, rows in data.get("row_changed", []) or []:
		for f, old, new in rows:
			if f not in SKIP_FIELDS:
				changes.append({"field": f"{table}.{f}", "label": f"{_label(meta, table)} #{idx} · {f}", "from": old, "to": new})
	return changes


def _title(doctype, name):
	meta = frappe.get_meta(doctype)
	for f in ("employee_name", "title", meta.title_field):
		if f and meta.has_field(f):
			return frappe.db.get_value(doctype, name, f) or name
	return name


@frappe.whitelist()
def trail(doctype, name):
	"""Every change, comment, workflow step and attachment of one record."""
	login_required()
	if not _audited(doctype):
		frappe.throw(_("Activity is not available for this record type."), frappe.PermissionError)
	doc = frappe.get_doc(doctype, name)
	doc.check_permission("read")
	meta = doc.meta
	events = [{"at": str(doc.creation), "kind": "created", **_who(doc.owner)}]
	for v in frappe.get_all("Version", filters={"ref_doctype": doctype, "docname": name},
							fields=["owner", "creation", "data"], order_by="creation asc", limit_page_length=1000):
		try:
			data = frappe.parse_json(v.data) or {}
		except Exception:
			continue
		changes = _version_changes(meta, data)
		if changes:
			events.append({"at": str(v.creation), "kind": "changed", "changes": changes, **_who(v.owner)})
	for c in frappe.get_all("Comment", filters={"reference_doctype": doctype, "reference_name": name,
												"comment_type": ["in", COMMENT_TYPES]},
							fields=["comment_type", "content", "owner", "creation", "comment_email"], order_by="creation asc"):
		events.append({"at": str(c.creation), "kind": c.comment_type.lower().replace(" ", "_"),
					   "text": frappe.utils.strip_html(c.content or "")[:1000], **_who(c.comment_email or c.owner)})
	if frappe.db.exists("DocType", "Workflow Action"):
		for wa in frappe.get_all("Workflow Action", filters={"reference_doctype": doctype, "reference_name": name,
															 "status": "Completed"},
								 fields=["workflow_state", "completed_by", "modified"], order_by="modified asc"):
			events.append({"at": str(wa.modified), "kind": "workflow_action", "text": wa.workflow_state, **_who(wa.completed_by)})
	events.sort(key=lambda e: e["at"])
	files = frappe.get_all("File", filters={"attached_to_doctype": doctype, "attached_to_name": name},
						   fields=["file_name", "file_url", "owner", "creation", "is_private"], order_by="creation asc")
	status_field = meta.get("workflow_state_field") or "workflow_state"
	out = {
		"doctype": doctype, "name": name, "title": _title(doctype, name),
		"status": doc.get(status_field) or doc.get("status") or doc.get("approval_status")
				  or {0: "Draft", 1: "Submitted", 2: "Cancelled"}[doc.docstatus],
		"docstatus": doc.docstatus, "pending_with": [], "events": events, "files": files,
		"desk_url": f"/app/{frappe.scrub(doctype).replace('_', '-')}/{name}",
	}
	from alphax_hr.api import approvals

	if doctype in approvals.SOURCES:
		out["pending_with"] = approvals.pending_with(doc)
	return out


def _employee_records(employee):
	"""{doctype: [names]} of records belonging to one employee (for the feed filter)."""
	out = {"Employee": [employee]}
	for dt in AUDITED:
		if dt == "Employee" or not frappe.db.exists("DocType", dt):
			continue
		if frappe.get_meta(dt).has_field("employee"):
			names = frappe.get_all(dt, filters={"employee": employee}, pluck="name", limit_page_length=2000)
			if names:
				out[dt] = names
	return out


@frappe.whitelist()
def feed(doctype=None, user=None, employee=None, from_date=None, to_date=None, start=0, limit=50):
	"""HR: recent changes across HR records, newest first."""
	require_hr()
	limit = min(cint(limit) or 50, 200)
	start = max(cint(start), 0)
	to_date = getdate(to_date or nowdate())
	from_date = getdate(from_date or add_days(to_date, -30))
	dts = [doctype] if doctype and _audited(doctype) else [d for d in AUDITED if frappe.db.exists("DocType", d)]
	period = ["between", [f"{from_date} 00:00:00", f"{to_date} 23:59:59"]]
	vf = {"ref_doctype": ["in", dts], "creation": period}
	cf = {"reference_doctype": ["in", dts], "creation": period, "comment_type": ["in", COMMENT_TYPES]}
	if user:
		vf["owner"] = user
		cf["owner"] = user
	only = None
	if employee:
		only = _employee_records(employee)
	versions = frappe.get_all("Version", filters=vf, fields=["ref_doctype", "docname", "owner", "creation", "data"],
							  order_by="creation desc", limit_page_length=2000)
	comments = frappe.get_all("Comment", filters=cf, fields=["reference_doctype", "reference_name", "comment_type", "content",
															 "owner", "creation", "comment_email"],
							  order_by="creation desc", limit_page_length=2000)
	items = []
	for v in versions:
		if only is not None and v.docname not in set(only.get(v.ref_doctype, ())):
			continue
		try:
			changes = _version_changes(frappe.get_meta(v.ref_doctype), frappe.parse_json(v.data) or {})
		except Exception:
			continue
		if changes:
			items.append({"at": str(v.creation), "kind": "changed", "doctype": v.ref_doctype, "docname": v.docname,
						  "changes": changes[:6], "more": max(0, len(changes) - 6), **_who(v.owner)})
	for c in comments:
		if only is not None and c.reference_name not in set(only.get(c.reference_doctype, ())):
			continue
		items.append({"at": str(c.creation), "kind": c.comment_type.lower().replace(" ", "_"), "doctype": c.reference_doctype,
					  "docname": c.reference_name, "text": frappe.utils.strip_html(c.content or "")[:300],
					  **_who(c.comment_email or c.owner)})
	items.sort(key=lambda i: i["at"], reverse=True)
	page = items[start:start + limit]
	seen = {}
	for i in page:
		key = (i["doctype"], i["docname"])
		if key not in seen:
			exists = bool(frappe.db.exists(*key))
			seen[key] = (_title(*key) if exists else i["docname"], exists)  # deleted records keep their name
		i["title"], i["exists"] = seen[key]
	by_type = defaultdict(int)
	for i in items:
		by_type[i["doctype"]] += 1
	return {"from_date": str(from_date), "to_date": str(to_date), "total": len(items), "start": start,
			"items": page, "by_type": dict(by_type), "doctypes": list(dts)}
