"""HR screens for approval policies: list, edit, try on an employee, and the approval chain of one document."""
from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import cint, flt

from alphax_hr import approval_policy as ap
from alphax_hr.api._common import parse_json, require_hr, require_hr_manager

FIELDS = ["policy_name", "enabled", "applies_to", "priority", "description", "request_type", "leave_type", "company", "department",
		  "branch", "designation", "min_amount", "min_days", "escalate_after_days", "remind_after_days", "auto_reject",
		  "reject_after_days", "rejection_comment", "multi_level", "restart_rule", "skip_repeat"]
LEVEL_FIELDS = ["level_label", "approver_type", "user", "min_amount", "min_days"]
KINDS = ["All approvals", "Requests", "Leave", "Expense claims", "Attendance corrections", "Shift changes", "Compensatory leave",
		 "Vacation plans"]


def _dict(doc):
	out = {k: doc.get(k) for k in FIELDS}
	out["name"] = doc.name
	out["levels"] = [{k: r.get(k) for k in LEVEL_FIELDS} for r in doc.levels or []]
	out["auto_reject_supported"] = out["applies_to"] not in ("Attendance corrections", "Compensatory leave")
	out["levels_supported"] = out["applies_to"] in ("Requests", "Leave")
	out["total_days"] = (cint(doc.escalate_after_days) + cint(doc.remind_after_days) + cint(doc.reject_after_days)
						 if cint(doc.auto_reject) else None)
	return out


@frappe.whitelist()
def overview():
	require_hr()
	names = frappe.get_all(ap.POLICY, order_by="enabled desc, priority desc, policy_name asc", pluck="name")
	return {"policies": [_dict(frappe.get_doc(ap.POLICY, n)) for n in names], "kinds": KINDS, "level_types": list(ap.LEVEL_TYPES),
			"restart_rules": ["From the first level", ap.RESUME], "default_comment": _(ap.DEFAULT_COMMENT),
			"can_edit": "HR Manager" in frappe.get_roles() or "System Manager" in frappe.get_roles()}


@frappe.whitelist(methods=["POST"])
def save(data: str | dict | list, name: str | None = None):
	require_hr_manager()
	data = parse_json(data) or {}
	doc = frappe.get_doc(ap.POLICY, name) if name else frappe.new_doc(ap.POLICY)
	for k in FIELDS:
		if k in data:
			doc.set(k, data[k] if data[k] not in ("",) else None)
	if "levels" in data:
		doc.set("levels", [])
		for r in data.get("levels") or []:
			doc.append("levels", {k: r.get(k) for k in LEVEL_FIELDS if r.get(k) not in (None, "")})
	if doc.applies_to not in ("Requests", "Leave"):
		doc.multi_level = 0
	doc.save() if name else doc.insert()
	if name and data.get("policy_name") and data["policy_name"] != name:
		frappe.rename_doc(ap.POLICY, name, data["policy_name"], force=True)
	ap.clear_cache()
	return overview()


@frappe.whitelist(methods=["POST"])
def delete(name: str):
	require_hr_manager()
	if frappe.db.exists(ap.STATE, {"policy": name, "status": "Pending"}):
		doc = frappe.get_doc(ap.POLICY, name)
		doc.enabled = 0
		doc.save()
		ap.clear_cache()
		return {"disabled": True, **overview()}
	frappe.delete_doc(ap.POLICY, name)
	ap.clear_cache()
	return overview()


@frappe.whitelist()
def preview(employee: str, kind: str = "Requests", request_type: str | None = None, leave_type: str | None = None,
			amount: float | str | None = 0, days: float | str | None = 0):
	"""Which policy would apply to this employee and who would approve, level by level."""
	require_hr()
	doctype = {"Requests": "AlphaX Request", "Leave": "Leave Application", "Expense claims": "Expense Claim",
			   "Attendance corrections": "Attendance Request", "Shift changes": "Shift Request",
			   "Compensatory leave": "Compensatory Leave Request", "Vacation plans": "AlphaX Leave Plan"}.get(kind, "AlphaX Request")
	doc = frappe._dict(doctype=doctype, employee=employee, request_type=request_type, leave_type=leave_type, details="{}",
					   total_leave_days=flt(days))
	f = ap.facts(doc)
	f.amount, f.days = flt(amount), flt(days)
	policy = ap.find(doc, f)
	if not policy:
		return {"policy": None, "levels": [], "message": _("No policy applies: the usual approval steps and the reminder hours in Settings are used.")}
	chain = ap.resolve_levels(policy, f) if cint(policy.multi_level) else []
	return {"policy": policy.name, "levels": [dict(x, approver_name=ap._group_name(x["approver"])) for x in chain],
			"escalate_after_days": policy.escalate_after_days, "remind_after_days": policy.remind_after_days,
			"auto_reject": cint(policy.auto_reject) and doctype in ap.AUTO_REJECT, "reject_after_days": policy.reject_after_days}


@frappe.whitelist()
def chain(doctype: str, name: str):
	"""The approval levels of one document, for anyone who may read it."""
	if doctype not in ap.KINDS:
		frappe.throw(_("Unsupported document."), frappe.PermissionError)
	out = ap.summary(doctype, name)
	if not out:
		return None
	user = frappe.session.user
	doc = frappe.get_doc(doctype, name)
	from alphax_hr.api._common import is_hr

	involved = {lv["approver"] for lv in out["levels"]} | {doc.get("approver"), doc.get("leave_approver"), doc.get("raised_by"),
														   frappe.db.get_value("Employee", doc.get("employee"), "user_id")}
	if not (user in involved or is_hr(user) or frappe.has_permission(doctype, "read", doc)):
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	return out
