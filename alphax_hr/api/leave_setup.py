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
					 "idx": r.idx,
					 "exists": bool(lt),
					 # Without allocations HRMS refuses the request unless the type allows it.
					 "needs_allocation": bool(lt and not lt.is_lwp and not lt.allow_negative)})
	# Sick leave first: with annual leave it is what employees use most.
	rows.sort(key=lambda r: (r["rule"] != lr.SICK, r["idx"]))
	mapped_kinds = {r["rule"] for r in rows}
	contract_count = (frappe.db.count("Employee", {"status": "Active", "alphax_annual_leave_days": [">", 0]})
					  if frappe.get_meta("Employee").has_field("alphax_annual_leave_days") else 0)
	return {
		"rules": rows,
		"missing_kinds": [k for k in lr.KINDS if k not in mapped_kinds],
		# Show the values the engine actually uses (blank settings fall back to the law's defaults).
		"annual": {
			"annual_leave_type": conf.annual_leave_type,
			"annual_policy": conf.annual_policy or annual_law.POLICY_LAW,
			"annual_fixed_days": cint(conf.annual_fixed_days) or 30,
			"contract_overrides": contract_count,
			"annual_auto_allocate": cint(conf.annual_auto_allocate),
			"annual_base_days": cint(conf.annual_base_days) or annual_law.ANNUAL_BASE_DAYS,
			"annual_senior_days": cint(conf.annual_senior_days) or annual_law.ANNUAL_SENIOR_DAYS,
			"annual_senior_after_years": cint(conf.annual_senior_after_years) or annual_law.SENIOR_AFTER_YEARS,
			"annual_senior_count_from": str(conf.annual_senior_count_from) if conf.annual_senior_count_from else None,
			"leave_escalation_hours": cint(conf.leave_escalation_hours),
			"approval_remind_hours": cint(conf.get("approval_remind_hours")),
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
	"""Annual policy and numbers. The leave type itself is fixed once set (see setup_annual_leave_type)."""
	require_hr_manager()
	payload = parse_json(data, {})
	conf = frappe.get_single("AlphaX HR Settings")
	if "annual_policy" in payload and payload["annual_policy"] not in (annual_law.POLICY_LAW, annual_law.POLICY_FIXED):
		frappe.throw(_("Unknown annual leave policy."))
	# Blank (or 0) means "use the law": 21 days, 30 after 5 years. Only typed values are checked.
	for key in ("annual_fixed_days", "annual_base_days"):
		if cint(payload.get(key)) and cint(payload[key]) < annual_law.ANNUAL_BASE_DAYS:
			frappe.throw(_("Annual leave cannot be less than {0} days (Saudi Labor Law, Art. 109).").format(annual_law.ANNUAL_BASE_DAYS))
	if cint(payload.get("annual_senior_days")) and cint(payload["annual_senior_days"]) < annual_law.ANNUAL_SENIOR_DAYS:
		frappe.throw(_("Annual leave after 5 years cannot be less than {0} days (Art. 109).").format(annual_law.ANNUAL_SENIOR_DAYS))
	for key in ("annual_fixed_days", "annual_base_days", "annual_senior_days", "annual_senior_after_years"):
		if key in payload and not cint(payload[key]):
			payload[key] = 0  # stored as 0 = law default
	for key in ("annual_policy", "annual_fixed_days", "annual_auto_allocate", "annual_base_days", "annual_senior_days",
				"annual_senior_after_years", "annual_senior_count_from", "leave_escalation_hours", "approval_remind_hours"):
		if key in payload:
			conf.set(key, payload[key] or None if key == "annual_senior_count_from" else payload[key])
	conf.save()
	return overview()


@frappe.whitelist()
def setup_annual_leave_type():
	"""Link (or create) the 'Annual Leave' type once. After that its name is fixed."""
	require_hr_manager()
	conf = frappe.get_single("AlphaX HR Settings")
	if conf.annual_leave_type:
		frappe.throw(_("The annual leave type is already set to {0} and cannot be changed here.").format(conf.annual_leave_type))
	name = "Annual Leave"
	if not frappe.db.exists("Leave Type", name):
		frappe.get_doc({"doctype": "Leave Type", "leave_type_name": name, "is_lwp": 0, "allow_negative": 0,
						"include_holiday": 0, "is_carry_forward": 1}).insert()
	conf.annual_leave_type = name
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


# ------------------------------------------------------- counting policy
COUNTING_EDITABLE = ("count_mode", "sandwich", "sandwich_holidays", "working_day_edges", "min_notice_days",
					 "max_days_per_request", "emergency", "notes")


@frappe.whitelist()
def counting_rules():
	require_hr()
	rows = frappe.get_all("AlphaX Leave Counting Rule", fields=["name", "leave_type", *COUNTING_EDITABLE],
						  order_by="leave_type asc")
	types = frappe.get_all("Leave Type", fields=["name", "include_holiday", "is_lwp"], order_by="name asc")
	return {"rules": rows, "leave_types": types,
			"options": {"count_mode": [leave_engine.lc.CALENDAR, leave_engine.lc.WORKING, leave_engine.lc.SKIP_HOLIDAYS,
									   leave_engine.lc.SKIP_WEEKENDS],
						"sandwich": [leave_engine.lc.SANDWICH_OFF, leave_engine.lc.SANDWICH_IN, leave_engine.lc.SANDWICH_ACROSS]},
			"can_edit": bool(set(frappe.get_roles()) & {"HR Manager", "System Manager"})}


@frappe.whitelist(methods=["POST"])
def save_counting_rule(data):
	require_hr_manager()
	data = parse_json(data) or {}
	leave_type = data.get("leave_type")
	if not leave_type or not frappe.db.exists("Leave Type", leave_type):
		frappe.throw(_("Please choose a leave type."))
	name = frappe.db.get_value("AlphaX Leave Counting Rule", {"leave_type": leave_type})
	doc = frappe.get_doc("AlphaX Leave Counting Rule", name) if name else frappe.new_doc("AlphaX Leave Counting Rule")
	doc.leave_type = leave_type
	for key in COUNTING_EDITABLE:
		if key in data:
			doc.set(key, data[key])
	doc.save()
	return doc.name


@frappe.whitelist(methods=["POST"])
def delete_counting_rule(name):
	require_hr_manager()
	frappe.delete_doc("AlphaX Leave Counting Rule", name)
	return True
