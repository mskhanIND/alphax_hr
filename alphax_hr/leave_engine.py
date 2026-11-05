"""Saudi leave engine glue: statutory leave rules, sick-leave tiers,
automatic annual allocations and escalation of untouched requests.

The rules themselves are pure functions in ``alphax_hr.saudi``; this module
reads site data, applies them and writes back through normal Frappe APIs.
"""
from __future__ import annotations

import frappe
from frappe import _

try:  # marks a message for translation without translating it (older Frappe v15 releases lack it)
	from frappe import N_
except ImportError:
	def N_(message):
		return message
from frappe.utils import add_days, cint, flt, getdate, nowdate

from alphax_hr.saudi import leave as annual
from alphax_hr.saudi import leave_counting as lc
from alphax_hr.saudi import leave_rules as lr

ERROR_TEXT = {
	"leave_gender": N_("{leave_type} is only for {gender} employees."),
	"leave_max_days": N_("{leave_type} cannot exceed {max:g} days per request."),
	"leave_min_service": N_("{leave_type} requires at least {days} days of service."),
	"leave_lifetime_limit": N_("{leave_type} can be taken {times} time(s) during employment, and it has already been used."),
	"leave_relation_required": N_("Please choose the relation for {leave_type}."),
	"leave_relation_not_allowed": N_("{leave_type} applies to: {allowed}."),
	"leave_event_date_required": N_("Please enter the {label} for {leave_type}."),
	"leave_too_early": N_("{leave_type} can start at most {days} day(s) before the {label}."),
	"leave_too_late": N_("{leave_type} must end within {days} day(s) after the {label}."),
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
	if doc.status not in ("Cancelled", "Rejected"):
		apply_counting(doc)
		from alphax_hr.request_rules import validate_leave_overlap

		validate_leave_overlap(doc)
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
		lines = [_(ERROR_TEXT[code]).format(leave_type=doc.leave_type, **params) for code, params in errors]
		frappe.throw("<br>".join(lines), title=_("Leave rules"))
	if rule.kind == lr.SICK:
		_set_sick_breakdown(doc, rules)


# ------------------------------------------------------- counting policy
COUNTING_FIELDS = ["name", "leave_type", "count_mode", "sandwich", "sandwich_holidays", "working_day_edges",
				   "min_notice_days", "max_days_per_request", "emergency", "notes"]


def counting_rule(leave_type):
	if not leave_type or not frappe.db.exists("DocType", "AlphaX Leave Counting Rule"):
		return None
	return frappe.db.get_value("AlphaX Leave Counting Rule", {"leave_type": leave_type}, COUNTING_FIELDS, as_dict=True)


def off_days(employee, start, end):
	"""(weekends, public holidays) from the employee's holiday list between two dates."""
	from hrms.hr.utils import get_holiday_list_for_employee

	holiday_list = get_holiday_list_for_employee(employee, raise_exception=False)
	if not holiday_list:
		return set(), set()
	rows = frappe.get_all("Holiday", filters={"parent": holiday_list, "holiday_date": ["between", [start, end]]},
						  fields=["holiday_date", "weekly_off"])
	weekends = {getdate(r.holiday_date) for r in rows if cint(r.weekly_off)}
	holidays = {getdate(r.holiday_date) for r in rows if not cint(r.weekly_off)}
	return weekends, holidays


def _neighbour(doc, before: bool):
	"""End (or start) of the employee's other leave right before (after) this one, created before this one."""
	filters = {"employee": doc.employee, "docstatus": ["<", 2], "status": ["not in", ["Rejected", "Cancelled"]],
			   "name": ["!=", doc.name or ""]}
	if doc.get("creation"):
		filters["creation"] = ["<", doc.creation]
	if before:
		filters["to_date"] = ["between", [add_days(doc.from_date, -7), add_days(doc.from_date, -1)]]
		rows = frappe.get_all("Leave Application", filters=filters, fields=["to_date"], order_by="to_date desc", limit=1)
		return getdate(rows[0].to_date) if rows else None
	filters["from_date"] = ["between", [add_days(doc.to_date, 1), add_days(doc.to_date, 7)]]
	rows = frappe.get_all("Leave Application", filters=filters, fields=["from_date"], order_by="from_date asc", limit=1)
	return getdate(rows[0].from_date) if rows else None


def count_days(employee, leave_type, from_date, to_date, half_day=False, doc=None):
	"""Counted days for a request under the leave type's counting rule, or None when no rule applies."""
	rule = counting_rule(leave_type)
	if not rule or not from_date or not to_date:
		return None, rule
	start, end = getdate(from_date), getdate(to_date)
	if end < start:
		return None, rule
	weekends, holidays = off_days(employee, add_days(start, -7), add_days(end, 7))
	policy = lc.Policy(rule.count_mode or lc.CALENDAR, rule.sandwich or lc.SANDWICH_OFF, bool(cint(rule.sandwich_holidays)))
	before = after = None
	if policy.sandwich == lc.SANDWICH_ACROSS:
		probe = doc or frappe._dict(employee=employee, from_date=start, to_date=end, name=None, creation=None)
		before, after = _neighbour(probe, True), _neighbour(probe, False)
	result = lc.count(start, end, weekends, holidays, policy, half_day=bool(half_day), leave_before=before, leave_after=after)
	result.notes = [d for d in (start, end) if d in weekends or d in holidays]  # off-day edges
	return result, rule


def describe_counting(result, rule):
	return _("Counted as {0}: {1}").format(rule.count_mode or lc.CALENDAR, result.describe())


def apply_counting(doc):
	half = cint(doc.get("half_day")) and doc.get("half_day_date")
	result, rule = count_days(doc.employee, doc.leave_type, doc.from_date, doc.to_date, half, doc)
	if not rule or result is None:
		return
	if cint(rule.working_day_edges) and result.notes:
		frappe.throw(_("{0} must start and end on a working day.").format(doc.leave_type), title=_("Leave counting"))
	if result.days <= 0:
		frappe.throw(_("The chosen dates are all weekends or public holidays, so no leave days are needed."),
					 title=_("Leave counting"))
	if doc.is_new() and not cint(rule.emergency) and cint(rule.min_notice_days):
		notice = (getdate(doc.from_date) - getdate(nowdate())).days
		if notice < cint(rule.min_notice_days):
			frappe.throw(_("{0} must be requested at least {1} day(s) before it starts.").format(
				doc.leave_type, cint(rule.min_notice_days)), title=_("Leave counting"))
	if flt(rule.max_days_per_request) and result.days > flt(rule.max_days_per_request):
		frappe.throw(_("{0} cannot exceed {1:g} counted day(s) per request (this request counts {2:g}).").format(
			doc.leave_type, flt(rule.max_days_per_request), result.days), title=_("Leave counting"))
	doc.total_leave_days = result.days
	if doc.meta.has_field("alphax_counting"):
		doc.alphax_counting = describe_counting(result, rule)
	lt = frappe.db.get_value("Leave Type", doc.leave_type, ["allow_negative", "is_lwp"], as_dict=True) or frappe._dict()
	if cint(lt.allow_negative) or cint(lt.is_lwp) or doc.docstatus != 0:
		return
	from hrms.hr.doctype.leave_application.leave_application import get_leave_balance_on

	balance = get_leave_balance_on(doc.employee, doc.leave_type, doc.from_date, doc.to_date,
								   consider_all_leaves_in_the_allocation_period=True, for_consumption=True,
								   leave_application=None if doc.is_new() else doc.name)
	available = flt(balance.get("leave_balance_for_consumption"))
	if available < result.days:
		frappe.throw(_("This request counts {0:g} day(s) but only {1:g} are available for {2}.").format(
			result.days, available, doc.leave_type), title=_("Insufficient leave balance"))


def sync_leave_type_holidays(rule_doc, method=None):
	"""HRMS should never count more days than AlphaX; AlphaX adds back what its policy counts."""
	if rule_doc.leave_type and frappe.db.exists("Leave Type", rule_doc.leave_type):
		include = 1 if (rule_doc.count_mode or lc.CALENDAR) == lc.CALENDAR else 0
		if cint(frappe.db.get_value("Leave Type", rule_doc.leave_type, "include_holiday")) != include:
			frappe.db.set_value("Leave Type", rule_doc.leave_type, "include_holiday", include)


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
	beyond = sum(p["days"] for p in parts if p["tier"] == "exceeds_statutory")
	if beyond:
		frappe.throw(_("Only {0:g} sick day(s) are left in the sick-leave year that started on {1} (Art. 117 allows 120). "
					   "Shorten this request by {2:g} day(s) and use unpaid leave for the rest.").format(
			max(0, 120 - used), frappe.utils.formatdate(start), beyond), title=_("Sick leave limit"))


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
			cint(conf.annual_senior_after_years) or annual.SENIOR_AFTER_YEARS,
			annual.senior_year_index(getdate(e.date_of_joining), start, getdate(conf.annual_senior_count_from) if conf.annual_senior_count_from else None))
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
	if result["failed"]:
		frappe.logger("alphax_hr").warning(f"Annual allocation failures: {result['failed']}")


# ------------------------------------------------------------ escalation
def escalate_pending_leaves():
	"""Kept for old scheduler entries; every approval type is now handled by delays.escalate_pending_approvals."""
	from alphax_hr.api.delays import escalate_pending_approvals

	escalate_pending_approvals()


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


def sick_status(employee, on=None):
	"""Sick-leave year (Art. 117) for an employee on a date: start, used and what is left per pay tier."""
	on = getdate(on or nowdate())
	sick_types = [lt for lt, r in rules_by_leave_type().items() if r.kind == lr.SICK]
	if not sick_types:
		return None
	previous = frappe.get_all("Leave Application", filters={
		"employee": employee, "leave_type": ["in", sick_types], "docstatus": ["<", 2],
		"status": ["not in", ["Rejected", "Cancelled"]], "from_date": ["<=", on]},
		fields=["from_date", "total_leave_days"])
	start, used = lr.sick_cycle_usage([(getdate(p.from_date), flt(p.total_leave_days)) for p in previous], add_days(on, 1))
	if not previous or start > on:
		start, used = None, 0.0
	tiers = []
	cursor = 0.0
	for size, factor in annual.SICK_TIERS:
		left = max(0.0, min(size, cursor + size - used))
		tiers.append({"days": size, "pay_factor": factor, "left": left})
		cursor += size
	return {"leave_types": sick_types, "cycle_start": str(start) if start else None,
			"cycle_end": str(add_days(start, 364)) if start else None, "used": used,
			"left": max(0.0, 120 - used), "tiers": tiers}
