"""Annual vacation planning: employees plan their vacation for the year ahead, managers approve it
with the department's coverage in view, and approved periods become leave requests in one tap."""
from __future__ import annotations

from collections import defaultdict
from datetime import date

import frappe
from frappe import _
from frappe.utils import add_days, cint, flt, getdate, now_datetime, nowdate

from alphax_hr.api._common import current_employee, is_hr, login_required, parse_json, settings

LIVE = ("Submitted", "Approved")
EDITABLE = ("Draft", "Changes requested")


def default_year():
	today = getdate(nowdate())
	return today.year + 1 if today.month >= 10 else today.year


def _holidays(employee, start, end):
	from hrms.hr.utils import get_holiday_list_for_employee

	hl = get_holiday_list_for_employee(employee, raise_exception=False)
	if not hl:
		return set()
	return set(frappe.get_all("Holiday", filters={"parent": hl, "holiday_date": ["between", [start, end]]}, pluck="holiday_date"))


def working_days(employee, start, end, holidays=None):
	start, end = getdate(start), getdate(end)
	hol = holidays if holidays is not None else _holidays(employee, start, end)
	return sum(1 for i in range((end - start).days + 1) if getdate(add_days(start, i)) not in hol)


def entitlement(employee, year):
	"""Annual days for the year: the allocation if HR has made it, otherwise the Labor Law days (21 / 30 after 5 years)."""
	conf = settings()
	lt = conf.get("annual_leave_type")
	if lt:
		alloc = frappe.get_all("Leave Allocation", filters={"employee": employee, "leave_type": lt, "docstatus": 1,
															"from_date": ["<=", f"{year}-12-31"], "to_date": [">=", f"{year}-01-01"]},
							   fields=["new_leaves_allocated"], order_by="from_date desc", limit=1)
		if alloc:
			return flt(alloc[0].new_leaves_allocated)
	from alphax_hr.saudi import leave as law

	joining = frappe.db.get_value("Employee", employee, "date_of_joining")
	return float(law.annual_entitlement(getdate(joining), date(int(year), 7, 1))) if joining else float(law.ANNUAL_BASE_DAYS)


def _approver(employee):
	from alphax_hr.api.ess import _leave_approver_for

	return _leave_approver_for(employee)


def _coverage(department, year, exclude_employee=None, include_drafts_of=None):
	"""{date: set(employees off)} from submitted/approved plans in the department, plus headcount."""
	off = defaultdict(set)
	if not department:
		return off, 0
	plans = frappe.get_all("AlphaX Leave Plan", filters={"department": department, "year": cint(year), "status": ["in", list(LIVE)]},
						   fields=["name", "employee"])
	for p in plans:
		if p.employee == exclude_employee:
			continue
		for r in frappe.get_all("AlphaX Leave Plan Period", filters={"parent": p.name}, fields=["from_date", "to_date"]):
			for i in range((getdate(r.to_date) - getdate(r.from_date)).days + 1):
				off[getdate(add_days(r.from_date, i))].add(p.employee)
	head = frappe.db.count("Employee", {"department": department, "status": "Active"})
	return off, head


def _conflicts(doc):
	"""Per period: the busiest day and how many colleagues are already off then."""
	max_pct = cint(settings().get("plan_max_off_percent"))
	off, head = _coverage(doc.department, doc.year, exclude_employee=doc.employee)
	out = []
	for p in doc.periods:
		worst, worst_day, names = 0, None, set()
		for i in range((getdate(p.to_date) - getdate(p.from_date)).days + 1):
			d = getdate(add_days(p.from_date, i))
			n = len(off.get(d, ())) + 1
			if n > worst:
				worst, worst_day, names = n, d, off.get(d, set())
		pct = round(100 * worst / head) if head else 0
		out.append({"idx": p.idx, "max_off": worst, "headcount": head, "percent": pct, "day": str(worst_day) if worst_day else None,
					"over_limit": bool(max_pct and head > 1 and pct > max_pct),
					"colleagues": sorted(frappe.db.get_value("Employee", e, "employee_name") or e for e in names)})
	return out


def _out(doc):
	conf = settings()
	return {"name": doc.name if not doc.is_new() else None, "employee": doc.employee, "employee_name": doc.employee_name, "year": doc.year,
			"status": doc.status, "department": doc.department, "entitlement": flt(doc.entitlement), "total_days": flt(doc.total_days),
			"approver": doc.approver, "manager_note": doc.manager_note, "decided_by": doc.decided_by,
			"periods": [{"idx": p.idx, "from_date": str(p.from_date), "to_date": str(p.to_date), "days": flt(p.days), "note": p.note,
						 "leave_application": p.leave_application,
						 "leave_status": frappe.db.get_value("Leave Application", p.leave_application, "status") if p.leave_application else None}
						for p in doc.periods],
			"conflicts": _conflicts(doc) if doc.periods else [],
			"rules": {"max_off_percent": cint(conf.get("plan_max_off_percent")), "min_block_days": cint(conf.get("plan_min_block_days")),
					  "deadline": str(conf.get("plan_deadline")) if conf.get("plan_deadline") else None}}


def _get(employee, year, create=False):
	name = frappe.db.get_value("AlphaX Leave Plan", {"employee": employee, "year": cint(year)})
	if name:
		return frappe.get_doc("AlphaX Leave Plan", name)
	doc = frappe.new_doc("AlphaX Leave Plan")
	doc.update({"employee": employee, "year": cint(year), "status": "Draft", "entitlement": entitlement(employee, year)})
	emp = frappe.db.get_value("Employee", employee, ["employee_name", "department", "company"], as_dict=True)
	doc.update({"employee_name": emp.employee_name, "department": emp.department, "company": emp.company})
	if create:
		doc.insert(ignore_permissions=True)
	return doc


@frappe.whitelist()
def my_plan(year=None):
	employee = current_employee()
	return _out(_get(employee, cint(year) or default_year()))


@frappe.whitelist(methods=["POST"])
def save_my_plan(year, periods):
	employee = current_employee()
	year = cint(year)
	doc = _get(employee, year)
	if doc.status not in EDITABLE:
		frappe.throw(_("This plan is {0} and can no longer be changed. Ask your manager to request changes.").format(_(doc.status)))
	rows = parse_json(periods, []) or []
	hol = _holidays(employee, f"{year}-01-01", f"{year + 1}-01-31")
	clean = []
	for r in rows:
		f_, t_ = getdate(r.get("from_date")), getdate(r.get("to_date"))
		if t_ < f_:
			frappe.throw(_("A period ends before it starts."))
		if f_.year != year:
			frappe.throw(_("Every period must start in {0}.").format(year))
		clean.append((f_, t_, str(r.get("note") or "")[:140]))
	clean.sort()
	for a, b in zip(clean, clean[1:]):
		if b[0] <= a[1]:
			frappe.throw(_("Two periods overlap ({0}).").format(frappe.utils.formatdate(b[0])))
	doc.set("periods", [])
	for f_, t_, note in clean:
		doc.append("periods", {"from_date": f_, "to_date": t_, "note": note, "days": working_days(employee, f_, t_, hol)})
	doc.total_days = sum(flt(p.days) for p in doc.periods)
	doc.entitlement = entitlement(employee, year)
	doc.flags.ignore_permissions = True
	doc.save()
	return _out(doc)


@frappe.whitelist(methods=["POST"])
def submit_my_plan(year):
	employee = current_employee()
	doc = _get(employee, cint(year))
	if doc.is_new() or not doc.periods:
		frappe.throw(_("Add at least one vacation period first."))
	if doc.status not in EDITABLE:
		frappe.throw(_("This plan has already been sent."))
	min_block = cint(settings().get("plan_min_block_days"))
	if min_block and not any((getdate(p.to_date) - getdate(p.from_date)).days + 1 >= min_block for p in doc.periods):
		frappe.throw(_("Please plan at least one continuous vacation of {0} days.").format(min_block))
	warnings = []
	if flt(doc.total_days) > flt(doc.entitlement):
		warnings.append(_("You planned {0} days; your entitlement for the year is {1}.").format(flt(doc.total_days), flt(doc.entitlement)))
	doc.status = "Submitted"
	doc.approver = _approver(employee)
	doc.flags.ignore_permissions = True
	doc.save()
	return {**_out(doc), "warnings": warnings}


def actions_for(doc, user):
	if doc.status != "Submitted":
		return []
	if doc.approver == user or is_hr(user):
		return ["Approve", "Request changes", "Reject"]
	return []


def pending_with(doc):
	if doc.status != "Submitted":
		return []
	return [{"user": doc.approver, "name": frappe.utils.get_fullname(doc.approver)}] if doc.approver else [{"role": "HR Manager"}]


def decide(name, action, comment=None):
	user = login_required()
	doc = frappe.get_doc("AlphaX Leave Plan", name)
	if action not in actions_for(doc, user):
		frappe.throw(_("You cannot perform '{0}' on this plan.").format(action), frappe.PermissionError)
	if action in ("Request changes", "Reject") and not (comment or "").strip():
		frappe.throw(_("Please tell the employee why."))
	doc.status = {"Approve": "Approved", "Request changes": "Changes requested", "Reject": "Rejected"}[action]
	doc.decided_by, doc.decided_on = user, now_datetime()
	if comment:
		doc.manager_note = str(comment)[:2000]
		doc.add_comment("Comment", frappe.utils.escape_html(str(comment)[:2000]))
	doc.flags.ignore_permissions = True
	doc.save()
	return {"name": doc.name, "status": doc.status}


@frappe.whitelist(methods=["POST"])
def decide_plan(name, action, comment=None):
	return decide(name, action, comment)


@frappe.whitelist(methods=["POST"])
def apply_period(year, idx):
	"""Turn an approved planned period into a leave request (annual leave type)."""
	employee = current_employee()
	doc = _get(employee, cint(year))
	if doc.status != "Approved":
		frappe.throw(_("The plan must be approved first."))
	row = next((p for p in doc.periods if p.idx == cint(idx)), None)
	if not row:
		frappe.throw(_("Unknown period."))
	if row.leave_application and frappe.db.get_value("Leave Application", row.leave_application, "status") not in ("Cancelled", "Rejected", None):
		frappe.throw(_("A leave request already exists for this period."))
	lt = settings().get("annual_leave_type")
	if not lt:
		frappe.throw(_("HR has not set the annual leave type yet."))
	from alphax_hr.api.ess import apply_leave

	r = apply_leave(lt, str(row.from_date), str(row.to_date), reason=_("Planned vacation ({0})").format(doc.name))
	frappe.db.set_value("AlphaX Leave Plan Period", row.name, "leave_application", r["name"])
	return r


@frappe.whitelist()
def planner(year=None, department=None):
	"""Department coverage for the year: plans, who is off each week, and days above the limit."""
	user = login_required()
	year = cint(year) or default_year()
	filters = {"year": year}
	if department:
		filters["department"] = department
	if not is_hr(user):
		filters["approver"] = user
	plans = frappe.get_all("AlphaX Leave Plan", filters=filters, fields=["name", "employee", "employee_name", "department", "status",
																		 "total_days", "entitlement", "approver"], order_by="employee_name asc")
	if not is_hr(user) and not frappe.db.exists("Employee", {"leave_approver": user}):
		frappe.throw(_("Only approvers and HR can open the vacation planner."), frappe.PermissionError)
	max_pct = cint(settings().get("plan_max_off_percent"))
	periods = defaultdict(list)
	for r in frappe.get_all("AlphaX Leave Plan Period", filters={"parent": ["in", [p.name for p in plans] or [""]]},
							fields=["parent", "idx", "from_date", "to_date", "days", "note"], order_by="from_date asc"):
		periods[r.parent].append({"from_date": str(r.from_date), "to_date": str(r.to_date), "days": flt(r.days), "note": r.note})
	# weekly coverage per department (submitted + approved)
	weeks = []
	start = getdate(f"{year}-01-01")
	start = getdate(add_days(start, -((start.weekday() + 1) % 7)))  # Sunday
	depts = sorted({p.department for p in plans if p.department})
	heads = {d: frappe.db.count("Employee", {"department": d, "status": "Active"}) for d in depts}
	live = [p for p in plans if p.status in LIVE]
	while start.year <= year:
		end = getdate(add_days(start, 6))
		row = {"week": str(start), "by_department": {}}
		for d in depts:
			names = [p.employee_name for p in live if p.department == d and any(
				getdate(x["from_date"]) <= end and getdate(x["to_date"]) >= start for x in periods[p.name])]
			pct = round(100 * len(names) / heads[d]) if heads[d] else 0
			row["by_department"][d] = {"off": len(names), "percent": pct, "names": names,
									   "over_limit": bool(max_pct and heads[d] > 1 and pct > max_pct)}
		weeks.append(row)
		start = getdate(add_days(start, 7))
	for p in plans:
		p["periods"] = periods[p.name]
		p["actions"] = actions_for(frappe._dict(p), user)
	submitted = frappe.db.count("AlphaX Leave Plan", {"year": year, "status": ["in", list(LIVE)]})
	return {"year": year, "plans": plans, "departments": depts, "headcount": heads, "weeks": weeks, "max_off_percent": max_pct,
			"not_planned": max(frappe.db.count("Employee", {"status": "Active", **({"department": department} if department else {})}) - submitted, 0)
			if is_hr(user) else None}


def query_conditions(user=None):
	user = user or frappe.session.user
	if user == "Administrator" or is_hr(user):
		return ""
	emp = frappe.db.get_value("Employee", {"user_id": user}, "name") or ""
	return "(`tabAlphaX Leave Plan`.employee = {0} or `tabAlphaX Leave Plan`.approver = {1})".format(frappe.db.escape(emp), frappe.db.escape(user))


def has_permission(doc, ptype=None, user=None):
	user = user or frappe.session.user
	if user == "Administrator" or is_hr(user):
		return True
	emp = frappe.db.get_value("Employee", {"user_id": user}, "name")
	return bool((emp and doc.employee == emp and ptype in (None, "read", "print")) or doc.approver == user)
