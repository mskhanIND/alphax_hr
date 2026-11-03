"""Attendance exceptions policy: who is exempt, grace periods, free late minutes, single punch, permission limits.

The most specific enabled policy applies: Employee > Designation > Department > Company > Everyone.
"""
from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import cint

from alphax_hr.api._common import parse_json, require_hr, require_hr_manager

ORDER = ("Employee", "Designation", "Department", "Company", "Everyone")
RULES = ("exempt", "late_grace_minutes", "early_grace_minutes", "monthly_late_allowance", "single_punch_ok",
		 "permissions_per_month", "no_penalties", "checkin_location_rule", "min_punch_gap")
FIELDS = ["name", "policy_name", "enabled", "applies_to", "company", "department", "designation", "employee", "description", *RULES]


def _policies():
	if not frappe.db.exists("DocType", "AlphaX Attendance Policy"):
		return []
	return frappe.get_all("AlphaX Attendance Policy", filters={"enabled": 1}, fields=FIELDS)


def resolve(employees):
	"""{employee: policy} for employee rows with name, company, department and (optionally) designation."""
	pols = _policies()
	if not pols:
		return {}
	idx = {(p.applies_to, p.get(p.applies_to.lower()) if p.applies_to != "Everyone" else None): p for p in pols}
	need = [e for e in employees if not e.get("designation") and "designation" not in e]
	if need:
		des = dict(frappe.get_all("Employee", filters={"name": ["in", [e["name"] for e in need]]}, fields=["name", "designation"], as_list=True))
		for e in need:
			e["designation"] = des.get(e["name"])
	out = {}
	for e in employees:
		keys = (("Employee", e["name"]), ("Designation", e.get("designation")), ("Department", e.get("department")),
				("Company", e.get("company")), ("Everyone", None))
		for k in keys:
			if k in idx and (k[1] or k[0] == "Everyone"):
				out[e["name"]] = idx[k]
				break
	return out


def for_employee(employee):
	e = frappe.db.get_value("Employee", employee, ["name", "company", "department", "designation"], as_dict=True)
	return resolve([e]).get(employee) if e else None


def apply_allowance(cells, allowance):
	"""Use up the monthly free late minutes in date order; returns minutes forgiven."""
	left = cint(allowance)
	used = 0
	for c in cells:
		if left <= 0:
			break
		if c.get("late"):
			take = min(c["late"], left)
			c["late"] -= take
			c["late_allowance"] = take
			left -= take
			used += take
	return used


@frappe.whitelist()
def policies():
	require_hr()
	rows = frappe.get_all("AlphaX Attendance Policy", fields=FIELDS, order_by="policy_name asc")
	for r in rows:
		r["covers"] = _covers(r)
	return rows


def _covers(p):
	filters = {"status": "Active"}
	if p.applies_to != "Everyone":
		target = p.get(p.applies_to.lower())
		if not target:
			return 0
		filters[{"Employee": "name"}.get(p.applies_to, p.applies_to.lower())] = target
	return frappe.db.count("Employee", filters)


@frappe.whitelist(methods=["POST"])
def save(data: str | dict | list, name: str | None = None):
	require_hr_manager()
	d = parse_json(data, {}) or {}
	if d.get("applies_to") not in ORDER:
		frappe.throw(_("Choose who the policy applies to."))
	if d["applies_to"] != "Everyone" and not d.get(d["applies_to"].lower()):
		frappe.throw(_("Choose the {0}.").format(_(d["applies_to"])))
	doc = frappe.get_doc("AlphaX Attendance Policy", name) if name else frappe.new_doc("AlphaX Attendance Policy")
	if not name:
		doc.policy_name = (d.get("policy_name") or "").strip()
	for k in ("enabled", "applies_to", "company", "department", "designation", "employee", "description", *RULES):
		if k in d:
			doc.set(k, d[k] if d[k] != "" else None)
	for k in ("company", "department", "designation", "employee"):  # only the target that matters is kept
		if k != doc.applies_to.lower():
			doc.set(k, None)
	for k in ("late_grace_minutes", "early_grace_minutes", "permissions_per_month", "min_punch_gap"):
		v = str(doc.get(k) if doc.get(k) is not None else "").strip()
		if v and not v.isdigit():
			frappe.throw(_("{0} must be a whole number (or blank to use the default).").format(doc.meta.get_label(k)))
		doc.set(k, v or None)
	if cint(doc.monthly_late_allowance) < 0:
		frappe.throw(_("Minutes cannot be negative."))
	clash = frappe.db.get_value("AlphaX Attendance Policy", {"applies_to": doc.applies_to, "enabled": 1, "name": ["!=", doc.name or ""],
															 **({doc.applies_to.lower(): doc.get(doc.applies_to.lower())} if doc.applies_to != "Everyone" else {})})
	if clash and cint(doc.enabled):
		frappe.throw(_("Policy {0} already covers the same people.").format(clash))
	doc.save()
	return {"name": doc.name}


@frappe.whitelist(methods=["POST"])
def delete(name: str):
	require_hr_manager()
	frappe.delete_doc("AlphaX Attendance Policy", name)
	return {"ok": True}


@frappe.whitelist()
def my_policy():
	"""The exceptions that apply to the logged-in employee (shown on My Attendance)."""
	from alphax_hr.api._common import current_employee

	p = for_employee(current_employee())
	return {k: p.get(k) for k in ("policy_name", *RULES)} if p else None
