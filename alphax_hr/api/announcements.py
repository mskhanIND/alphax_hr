"""HR announcements shown on every employee's home screen."""
from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import cint, getdate, nowdate

from alphax_hr.api._common import is_hr, login_required, parse_json, require_hr

FIELDS = ["name", "title", "title_ar", "priority", "pinned", "audience", "company", "department", "publish_on", "expires_on",
		  "body", "body_ar", "attachment", "owner", "creation"]


def _out(r):
	return {**r, "publish_on": str(r.publish_on) if r.publish_on else None, "expires_on": str(r.expires_on) if r.expires_on else None,
			"creation": str(r.creation), "by": frappe.utils.get_fullname(r.owner)}


@frappe.whitelist()
def active():
	"""Announcements for the logged-in user: current, for everyone or their company / department; pinned first."""
	user = login_required()
	if not frappe.db.exists("DocType", "AlphaX Announcement"):
		return []
	emp = frappe.db.get_value("Employee", {"user_id": user}, ["company", "department"], as_dict=True) or frappe._dict()
	today = getdate(nowdate())
	rows = frappe.get_all("AlphaX Announcement", filters={"publish_on": ["<=", today]}, fields=FIELDS,
						  order_by="pinned desc, publish_on desc", limit_page_length=50)
	out = []
	for r in rows:
		if r.expires_on and getdate(r.expires_on) < today:
			continue
		if r.audience == "Company" and r.company != emp.get("company") and not is_hr(user):
			continue
		if r.audience == "Department" and r.department != emp.get("department") and not is_hr(user):
			continue
		out.append(_out(r))
	return out[:10]


@frappe.whitelist()
def all_announcements():
	require_hr()
	return [_out(r) for r in frappe.get_all("AlphaX Announcement", fields=FIELDS, order_by="publish_on desc", limit_page_length=200)]


@frappe.whitelist(methods=["POST"])
def save(data, name=None):
	require_hr()
	d = parse_json(data, {}) or {}
	doc = frappe.get_doc("AlphaX Announcement", name) if name else frappe.new_doc("AlphaX Announcement")
	for k in ("title", "title_ar", "priority", "pinned", "audience", "company", "department", "publish_on", "expires_on", "body",
			  "body_ar", "attachment"):
		if k in d:
			doc.set(k, d[k] if d[k] != "" else None)
	doc.publish_on = doc.publish_on or nowdate()
	if doc.audience == "Company" and not doc.company:
		frappe.throw(_("Choose the company."))
	if doc.audience == "Department" and not doc.department:
		frappe.throw(_("Choose the department."))
	if doc.expires_on and getdate(doc.expires_on) < getdate(doc.publish_on):
		frappe.throw(_("'Show until' is before the publish date."))
	doc.pinned = cint(doc.pinned)
	doc.save()
	return {"name": doc.name}


@frappe.whitelist(methods=["POST"])
def delete(name):
	require_hr()
	frappe.delete_doc("AlphaX Announcement", name)
	return {"ok": True}
