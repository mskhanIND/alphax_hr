"""Saudi leave engine glue: statutory leave rules, sick-leave tiers,
automatic annual allocations and escalation of untouched requests.

The rules themselves are pure functions in ``alphax_hr.saudi``; this module
reads site data, applies them and writes back through normal Frappe APIs.
"""
from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import add_to_date, cint, flt, getdate, now_datetime, nowdate

from alphax_hr.saudi import leave as annual
from alphax_hr.saudi import leave_rules as lr

ERROR_TEXT = {
	"leave_gender": _("{leave_type} is only for {gender} employees."),
	"leave_max_days": _("{leave_type} cannot exceed {max:g} days per request."),
	"leave_min_service": _("{leave_type} requires at least {days} days of service."),
	"leave_lifetime_limit": _("{leave_type} can be taken {times} time(s) during employment, and it has already been used."),
	"leave_relation_required": _("Please choose the relation for {leave_type}."),
	"leave_relation_not_allowed": _("{leave_type} applies to: {allowed}."),
	"leave_event_date_required": _("Please enter the {label} for {leave_type}."),
	"leave_too_early": _("{leave_type} can start at most {days} day(s) before the {label}."),
	"leave_too_late": _("{leave_type} must end within {days} day(s) after the {label}."),
}


# --------------------------------------------------------------------- rules
def _settings():
	if not frappe.db.exists("DocType", "AlphaX HR Settings"):
		return None
	return frappe.get_cached_doc("AlphaX HR Settings")


def _int_or_none(value):
	value = str(value).strip() if value not in (None, "") else ""
	return int(float(value)) if value else None


def rules_by_leave_type() -> dict[str, lr.Rule]:
	conf = _settings()
	out = {}
	if not conf:
		return out
	for row in conf.get("leave_rules") or []:
		if not cint(row.enabled) or not row.leave_type or row.rule not in lr.KINDS:
			continue
		out[row.leave_type] = lr.Rule(
			kind=row.rule,
			max_days=flt(row.max_days) or None,
			gender=row.gender or None,
			min_service_days=cint(row.min_service_days) or None,
			lifetime_limit=cint(row.lifetime_limit) or None,
			requires_event_date=bool(cint(row.requires_event_date)),
			days_before_event=_int_or_none(row.days_before_event),
			days_after_event=_int_or_none(row.days_after_event),
			relations=tuple(r.strip() for r in (row.relations or "").splitlines() if r.strip()),
			requires_attachment=bool(cint(row.requires_attachment)),
			event_label=row.event_label or "",
		)
	return out


def rule_to_dict(rule: lr.Rule | None):
	if not rule:
		return None
	return {
		"kind": rule.kind, "max_days": rule.max_days, "gender": rule.gender,
		"requires_event_date": rule.requires_event_date, "event_label": rule.event_label or None,
		"relations": list(rule.relations), "requires_attachment": rule.requires_attachment,
		"min_service_days": rule.min_service_days, "lifetime_limit": rule.lifetime_limit,
	}


# ---------------------------------------------------- Leave Application hooks
def validate_leave_application(doc, method=None):
	rules = rules_by_leave_type()
	rule = rules.get(doc.leave_type)
	if not rule or doc.status in ("Cancelled", "Rejected"):
		return
	emp = frappe.db.get_value("Employee", doc.employee, ["gender", "date_of_joining"], as_dict=True) or frappe._dict()
	previous_uses = frappe.db.count("Leave Application", {
		"employee": doc.employee, "leave_type": doc.leave_type, "docstatus": 1, "status": "Approved",
		"name": ["!=", doc.name or ""]})
	request = lr.Request(
		from_date=getdate(doc.from_date), to_date=getdate(doc.to_date), total_days=flt(doc.total_leave_days),
		gender=emp.gender, date_of_joining=getdate(emp.date_of_joining) if emp.date_of_joining else None,
		event_date=getdate(doc.alphax_event_date) if doc.get("alphax_event_date") else None,
		relation=doc.get("alphax_relation") or None, previous_uses=previous_uses)
	errors = lr.check(rule, request)
	if errors:
		lines = [ERROR_TEXT[code].format(leave_type=doc.leave_type, **params) for code, params in errors]
		frappe.throw("<br>".join(lines), title=_("Leave rules"))
	if rule.kind == lr.SICK:
		_set_sick_breakdown(doc, rules)


def _set_sick_breakdown(doc, rules):
	sick_types = [lt for lt, r in rules.items() if r.kind == lr.SICK]
	previous = frappe.get_all(  # read inside a validated save; employee's own history
		"Leave Application",
		filters={"employee": doc.employee, "leave_type": ["in", sick_types], "docstatus": ["<", 2],
				 "status": ["not in", ["Rejected", "Cancelled"]], "name": ["!=", doc.name or ""],
				 "from_date": ["<", doc.from_date]},
		fields=["from_date", "total_leave_days"],
	)
	start, used = lr.sick_cycle_usage([(getdate(p.from_date), flt(p.total_leave_days)) for p in previous], getdate(doc.from_date))
	parts = annual.sick_leave_split(used, flt(doc.total_leave_days))
	text = annual.describe_sick_split(parts)
	if doc.meta.has_field("alphax_sick_breakdown"):
		doc.alphax_sick_breakdown = _("{0} (sick-leave year from {1}, {2:g} day(s) used before)").format(
			text, frappe.utils.formatdate(start), used)
	if any(p["tier"] == "exceeds_statutory" for p in parts):
		frappe.msgprint(_("This request goes beyond the 120 days of sick leave in Art. 117."), indicator="orange", alert=True)


def before_submit_leave_application(doc, method=None):
	"""Attachment rules are checked when the request is decided (files are uploaded after it is created)."""
	if doc.status != "Approved":
		return
	rule = rules_by_leave_type().get(doc.leave_type)
	if rule and rule.requires_attachment:
		has_file = frappe.db.exists("File", {"attached_to_doctype": "Leave Application", "attached_to_name": doc.name})
		if not has_file:
			frappe.throw(_("{0} needs a supporting document (medical certificate or proof) before approval.").format(doc.leave_type),
						 title=_("Attachment required"))


# ---------------------------------------------------------- annual leave
def plan_annual_allocations(on=None, employees=None):
	"""What the annual allocation job would create today. Returns rows with an action."""
	conf = _settings()
	if not conf or not conf.annual_leave_type:
		return {"configured": False, "rows": []}
	on = getdate(on or nowdate())
	leave_type = conf.annual_leave_type
	carry = cint(frappe.db.get_value("Leave Type", leave_type, "is_carry_forward"))
	filters = {"status": "Active", "date_of_joining": ["<=", on]}
	if employees:
		filters["name"] = ["in", list(employees)]
	rows = []
	fields = ["name", "employee_name", "date_of_joining"]
	if frappe.get_meta("Employee").has_field("alphax_annual_leave_days"):
		fields.append("alphax_annual_leave_days")
	for e in frappe.get_all("Employee", filters=filters, fields=fields, order_by="employee_name asc"):
		k, start, end = annual.service_period(getdate(e.date_of_joining), on)
		days, source = annual.annual_days(
			k, conf.annual_policy or annual.POLICY_LAW, cint(conf.annual_fixed_days), cint(e.get("alphax_annual_leave_days")),
			cint(conf.annual_base_days) or annual.ANNUAL_BASE_DAYS, cint(conf.annual_senior_days) or annual.ANNUAL_SENIOR_DAYS,
			cint(conf.annual_senior_after_years) or annual.SENIOR_AFTER_YEARS)
		existing = frappe.get_all("Leave Allocation", filters={
			"employee": e.name, "leave_type": leave_type, "docstatus": 1,
			"from_date": ["<=", end], "to_date": [">=", start]}, fields=["name", "from_date", "to_date"])
		if not existing:
			action = "create"
		elif any(getdate(x.from_date) == start and getdate(x.to_date) == end for x in existing):
			action = "exists"
		else:
			action = "conflict"  # e.g. a calendar-year allocation from before; never overwritten
		rows.append({"employee": e.name, "employee_name": e.employee_name, "service_year": k + 1,
					 "from_date": str(start), "to_date": str(end), "days": days, "source": source, "carry_forward": bool(carry),
					 "action": action, "existing": [x.name for x in existing]})
	return {"configured": True, "leave_type": leave_type, "on": str(on), "rows": rows,
			"counts": {a: sum(1 for r in rows if r["action"] == a) for a in ("create", "exists", "conflict")}}


def apply_annual_allocations(on=None, employees=None):
	plan = plan_annual_allocations(on, employees)
	created, failed = [], []
	for row in plan.get("rows", []):
		if row["action"] != "create":
			continue
		frappe.db.savepoint("alphax_alloc")
		try:
			alloc = frappe.get_doc({
				"doctype": "Leave Allocation", "employee": row["employee"], "leave_type": plan["leave_type"],
				"from_date": row["from_date"], "to_date": row["to_date"], "new_leaves_allocated": row["days"],
				"carry_forward": 1 if row["carry_forward"] else 0,
				"description": _("Saudi annual leave, service year {0} (AlphaX HR)").format(row["service_year"]),
			})
			alloc.insert()
			alloc.submit()
			created.append(alloc.name)
		except Exception as exc:  # one bad employee must not stop the run
			frappe.db.rollback(save_point="alphax_alloc")
			failed.append({"employee": row["employee"], "error": str(exc)[:300]})
			frappe.clear_messages()
	plan.update({"created": created, "failed": failed})
	return plan


def daily_annual_allocation():
	conf = _settings()
	if not conf or not cint(conf.annual_auto_allocate) or not conf.annual_leave_type:
		return
	result = apply_annual_allocations()
	frappe.db.commit()
	if result["failed"]:
		frappe.logger("alphax_hr").warning(f"Annual allocation failures: {result['failed']}")


# ------------------------------------------------------------ escalation
def escalate_pending_leaves():
	conf = _settings()
	hours = cint(conf.leave_escalation_hours) if conf else 0
	if not hours or not frappe.get_meta("Leave Application").has_field("alphax_escalated_on"):
		return
	cutoff = add_to_date(now_datetime(), hours=-hours)
	pending = frappe.get_all("Leave Application", filters={
		"docstatus": 0, "status": "Open", "creation": ["<", cutoff], "alphax_escalated_on": ["is", "not set"]},
		fields=["name", "employee_name", "leave_type", "from_date", "leave_approver"], limit=500)
	if not pending:
		return
	managers = {u for u in frappe.get_all("Has Role", filters={"role": "HR Manager", "parenttype": "User"}, pluck="parent")
				if u not in ("Administrator", "Guest")}
	for row in pending:
		recipients = set(managers)
		if row.leave_approver:
			recipients.add(row.leave_approver)
		for user in recipients:
			if not frappe.db.get_value("User", user, "enabled"):
				continue
			frappe.get_doc({
				"doctype": "Notification Log", "for_user": user, "type": "Alert",
				"document_type": "Leave Application", "document_name": row.name,
				"subject": _("Leave request from {0} ({1}, {2}) has waited more than {3} hours").format(
					row.employee_name, row.leave_type, frappe.utils.formatdate(row.from_date), hours),
			}).insert(ignore_permissions=True)
		frappe.db.set_value("Leave Application", row.name, "alphax_escalated_on", now_datetime(), update_modified=False)
	frappe.db.commit()


# ------------------------------------------------- fixed leave type names
def _protected_leave_types():
	conf = _settings()
	if not conf:
		return set()
	names = {r.leave_type for r in conf.leave_rules}
	if conf.annual_leave_type:
		names.add(conf.annual_leave_type)
	return names


def block_rename(doc, method=None, old=None, new=None, merge=False):
	if (old or doc.name) in _protected_leave_types():
		frappe.throw(_("{0} is used by AlphaX HR leave rules and cannot be renamed.").format(old or doc.name),
					 title=_("Fixed leave type"))


def block_delete(doc, method=None):
	if doc.name in _protected_leave_types():
		frappe.throw(_("{0} is used by AlphaX HR leave rules and cannot be deleted.").format(doc.name),
					 title=_("Fixed leave type"))
