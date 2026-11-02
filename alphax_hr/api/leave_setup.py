"""Leave setup for HR, inside /alphax: statutory leave types and rules, annual allocation."""
from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import cint, flt

from alphax_hr import leave_engine
from alphax_hr.api._common import parse_json, require_hr, require_hr_manager
from alphax_hr.install import rule_row
from alphax_hr.saudi import leave as annual_law
from alphax_hr.saudi import leave_rules as lr

# Leave Types AlphaX can create for a new customer. Calendar-day leaves
# (maternity, Iddah, sick, Hajj) include holidays; the rest count working days.
STATUTORY_TYPES = {
	lr.MATERNITY: ("Maternity Leave", 1),
	lr.PATERNITY: ("Paternity Leave", 0),
	lr.MARRIAGE: ("Marriage Leave", 0),
	lr.BEREAVEMENT: ("Bereavement Leave", 0),
	lr.SIBLING: ("Bereavement Leave (Sibling)", 0),
	lr.IDDAH_MUSLIM: ("Iddah Leave (Muslim)", 1),
	lr.IDDAH_OTHER: ("Iddah Leave (Non-Muslim)", 1),
	lr.EXAM: ("Examination Leave", 0),
	lr.HAJJ: ("Hajj Leave", 1),
	lr.SICK: ("Sick Leave", 1),
}
EDITABLE_RULE_FIELDS = {"enabled", "max_days", "gender", "min_service_days", "lifetime_limit", "requires_event_date",
						"event_label", "days_before_event", "days_after_event", "relations", "requires_attachment"}


@frappe.whitelist()
def overview():
	require_hr()
	conf = frappe.get_single("AlphaX HR Settings")
	rows = []
	for r in conf.leave_rules:
		lt = frappe.db.get_value("Leave Type", r.leave_type, ["is_lwp", "allow_negative"], as_dict=True)
		rows.append({"name": r.name, **{k: r.get(k) for k in ("leave_type", "rule", *EDITABLE_RULE_FIELDS)},
					 "max_days": flt(r.max_days) or None,  # 0 = no fixed limit
					 "exists": bool(lt),
					 # Without allocations HRMS refuses the request unless the type allows it.
					 "needs_allocation": bool(lt and not lt.is_lwp and not lt.allow_negative)})
	mapped_kinds = {r["rule"] for r in rows}
	return {
		"rules": rows,
		"missing_kinds": [k for k in lr.KINDS if k not in mapped_kinds],
		# Show the values the engine actually uses (blank settings fall back to the law's defaults).
		"annual": {
			"annual_leave_type": conf.annual_leave_type,
			"annual_auto_allocate": cint(conf.annual_auto_allocate),
			"annual_base_days": cint(conf.annual_base_days) or annual_law.ANNUAL_BASE_DAYS,
			"annual_senior_days": cint(conf.annual_senior_days) or annual_law.ANNUAL_SENIOR_DAYS,
			"annual_senior_after_years": cint(conf.annual_senior_after_years) or annual_law.SENIOR_AFTER_YEARS,
			"leave_escalation_hours": cint(conf.leave_escalation_hours),
		},
		"can_edit": bool(set(frappe.get_roles()) & {"HR Manager", "System Manager"}),
	}


@frappe.whitelist()
def create_statutory_leave_types():
	"""Create any missing statutory Leave Types and map them to their rules."""
	require_hr_manager()
	conf = frappe.get_single("AlphaX HR Settings")
	mapped_kinds = {r.rule for r in conf.leave_rules}
	created = []
	for kind, (name, calendar_days) in STATUTORY_TYPES.items():
		if kind in mapped_kinds:
			continue
		if not frappe.db.exists("Leave Type", name):
			rule = lr.default_rule(kind)
			frappe.get_doc({
				"doctype": "Leave Type", "leave_type_name": name, "is_lwp": 0,
				"allow_negative": 1,  # statutory leave is not allocated; the rule caps it
				"include_holiday": calendar_days,
				"max_continuous_days_allowed": int(rule.max_days or 0),
			}).insert()
			created.append(name)
		conf.append("leave_rules", rule_row(name, kind))
	conf.save()
	return {"created": created, **overview()}


@frappe.whitelist()
def allow_without_allocation(leave_type):
	"""Statutory leaves are capped by their rule, not by an allocation."""
	require_hr_manager()
	if leave_type not in {r.leave_type for r in frappe.get_single("AlphaX HR Settings").leave_rules}:
		frappe.throw(_("Only leave types mapped to a statutory rule can be changed here."), frappe.PermissionError)
	doc = frappe.get_doc("Leave Type", leave_type)
	doc.allow_negative = 1
	doc.save()
	return overview()


@frappe.whitelist()
def update_rule(name, data):
	require_hr_manager()
	payload = parse_json(data, {})
	conf = frappe.get_single("AlphaX HR Settings")
	row = next((r for r in conf.leave_rules if r.name == name), None)
	if not row:
		frappe.throw(_("Rule not found."), frappe.DoesNotExistError)
	for key, value in payload.items():
		if key in EDITABLE_RULE_FIELDS:
			row.set(key, value)
	conf.save()
	return overview()


@frappe.whitelist()
def update_annual_settings(data):
	require_hr_manager()
	payload = parse_json(data, {})
	conf = frappe.get_single("AlphaX HR Settings")
	for key in ("annual_leave_type", "annual_auto_allocate", "annual_base_days", "annual_senior_days",
				"annual_senior_after_years", "leave_escalation_hours"):
		if key in payload:
			conf.set(key, payload[key])
	conf.save()
	return overview()


@frappe.whitelist()
def annual_allocation(apply=0):
	"""Preview (default) or create this service year's annual leave allocations."""
	if cint(apply):
		require_hr_manager()
		return leave_engine.apply_annual_allocations()
	require_hr()
	return leave_engine.plan_annual_allocations()
