"""Warnings and penalties: violation schedule, repeat escalation, Labor-Law caps, payroll deduction.

Flow: HR drafts (or picks a suggestion from attendance) -> Issue (step, amount and cap are
fixed, deduction goes to payroll as Additional Salary) -> employee acknowledges or objects
within 15 days -> HR may cancel (the deduction is reversed).
"""
from __future__ import annotations

import json

import frappe
from frappe.model.document import Document
from frappe import _
from frappe.utils import add_days, cint, flt, get_first_day, get_last_day, getdate, now_datetime, nowdate

from alphax_hr.api._common import current_employee, is_hr, login_required, parse_json, require_hr
from alphax_hr.saudi import penalties as rules

LIVE = ("Issued", "Acknowledged", "Objected")
COMPONENT_NAMES = ("Penalty Deduction", "Penalties", "Penalty", "Disciplinary Deduction")

W = lambda *s: [{"action": "Warning"}] + list(s)  # noqa: E731
D = lambda pct=None, days=None: {"action": "Deduction", **({"percent": pct} if pct else {}), **({"days": days} if days else {})}  # noqa: E731

DEFAULT_VIOLATIONS = [
	{"violation_name": "Late arrival up to 15 minutes", "title_ar": "التأخر حتى 15 دقيقة", "category": "Working Hours",
	 "source": "Late Arrival", "min_minutes": 1, "max_minutes": 15, "steps": W(D(5), D(10), D(20))},
	{"violation_name": "Late arrival 16 to 30 minutes", "title_ar": "التأخر من 16 إلى 30 دقيقة", "category": "Working Hours",
	 "source": "Late Arrival", "min_minutes": 16, "max_minutes": 30, "steps": [D(10), D(15), D(25), D(50)]},
	{"violation_name": "Late arrival 31 to 60 minutes", "title_ar": "التأخر من 31 إلى 60 دقيقة", "category": "Working Hours",
	 "source": "Late Arrival", "min_minutes": 31, "max_minutes": 60, "steps": [D(25), D(50), D(75), D(days=1)]},
	{"violation_name": "Late arrival over 60 minutes", "title_ar": "التأخر أكثر من 60 دقيقة", "category": "Working Hours",
	 "source": "Late Arrival", "min_minutes": 61, "steps": W(D(days=1), D(days=2), D(days=3))},
	{"violation_name": "Leaving early without permission", "title_ar": "الانصراف المبكر دون إذن", "category": "Working Hours",
	 "source": "Early Exit", "min_minutes": 15, "steps": W(D(10), D(25), D(days=1))},
	{"violation_name": "Absence without excuse (1 day)", "title_ar": "الغياب دون عذر (يوم واحد)", "category": "Working Hours",
	 "source": "Absence", "steps": [D(days=1), D(days=2), D(days=3), {"action": "Suspension", "days": 4}]},
	{"violation_name": "Not following safety instructions", "title_ar": "عدم الالتزام بتعليمات السلامة", "category": "Work Organization",
	 "steps": [D(25), D(50), D(days=1), D(days=2)]},
	{"violation_name": "Smoking in prohibited areas", "title_ar": "التدخين في الأماكن المحظورة", "category": "Work Organization",
	 "steps": W(D(10), D(25), D(50))},
	{"violation_name": "Misconduct with colleagues or customers", "title_ar": "سوء السلوك مع الزملاء أو العملاء", "category": "Conduct",
	 "steps": W(D(days=1), D(days=2), {"action": "Suspension", "days": 3})},
]


def seed_violations():
	if not frappe.db.exists("DocType", "AlphaX Violation Type"):
		return
	for v in DEFAULT_VIOLATIONS:
		if frappe.db.exists("AlphaX Violation Type", v["violation_name"]):
			continue
		doc = {k: val for k, val in v.items() if k != "steps"}
		doc.update({"doctype": "AlphaX Violation Type", "steps_json": json.dumps(v["steps"]),
					"reference": "MHRSD model work regulations (review against your approved regulations)"})
		frappe.get_doc(doc).insert(ignore_permissions=True)


# ------------------------------------------------------------------ helpers
def _steps(vtype):
	steps = parse_json(frappe.db.get_value("AlphaX Violation Type", vtype, "steps_json"), []) or []
	for s in steps:
		rules.step_for([s], 1)  # validates the action name
	return steps


def monthly_wage(employee, on=None):
	"""Actual monthly wage (all fixed earnings of the current structure); falls back to payroll data."""
	ssa = frappe.get_all("Salary Structure Assignment", filters={"employee": employee, "docstatus": 1,
																  "from_date": ["<=", on or nowdate()]},
						 fields=["salary_structure", "base"], order_by="from_date desc", limit=1)
	if ssa:
		gross = sum(flt(d.amount) for d in frappe.get_all(
			"Salary Detail", filters={"parent": ssa[0].salary_structure, "parenttype": "Salary Structure", "parentfield": "earnings"},
			fields=["amount"]))
		return gross or flt(ssa[0].base)
	from alphax_hr.api._wages import wages

	return flt(wages([employee], on or nowdate(), on or nowdate())[employee]["eosb_wage"])


def _days_this_month(employee, on, exclude=None):
	start, end = get_first_day(on), get_last_day(on)
	rows = frappe.get_all("AlphaX Penalty", filters={"employee": employee, "status": ["in", list(LIVE)],
													"payroll_date": ["between", [start, end]], "name": ["!=", exclude or ""]},
						  fields=["days", "percent", "action"])
	return sum(flt(r.days) + flt(r.percent) / 100 for r in rows if r.action in ("Deduction", "Suspension"))


def _component(company):
	from alphax_hr.api import components

	chosen = frappe.get_cached_doc("AlphaX HR Settings").get("penalty_component")
	if chosen and frappe.db.exists("Salary Component", chosen):
		return chosen
	for n in COMPONENT_NAMES:
		if frappe.db.exists("Salary Component", n):
			return n
	return components.get("penalty")


def preview_doc(doc):
	"""Fill occurrence, step, wage, amount and cap on a penalty (not saved)."""
	on = getdate(doc.violation_date)
	prev = frappe.get_all("AlphaX Penalty", filters={"employee": doc.employee, "violation_type": doc.violation_type,
													  "status": ["in", list(LIVE)], "name": ["!=", doc.name or ""]},
						  pluck="violation_date")
	doc.occurrence = rules.occurrence([getdate(d) for d in prev], on)
	step = rules.step_for(_steps(doc.violation_type), doc.occurrence)
	doc.action = step["action"]
	days = rules.penalty_days(step)
	doc.payroll_date = doc.payroll_date or nowdate()
	already = _days_this_month(doc.employee, getdate(doc.payroll_date), exclude=doc.name)
	allowed, was_capped = rules.capped(days, already)
	doc.days = flt(step.get("days") or 0)
	doc.percent = flt(step.get("percent") or 0)
	if was_capped:
		# keep the whole cost within the monthly cap
		doc.days, doc.percent = float(int(allowed)), round((allowed - int(allowed)) * 100, 2)
		doc.capped_note = _("Reduced to {0} day(s): wage deductions cannot exceed {1} days' wage in a month ({2} already used).").format(
			round(allowed, 2), rules.MONTHLY_CAP_DAYS, round(already, 2))
	else:
		doc.capped_note = None
	doc.daily_wage = rules.daily_wage(monthly_wage(doc.employee, doc.violation_date))
	doc.amount = flt(doc.daily_wage * allowed, 2) if doc.action in ("Deduction", "Suspension") else 0
	return doc


def _out(doc):
	d = doc.as_dict() if isinstance(doc, Document) else dict(doc)
	keep = ("name", "employee", "employee_name", "department", "violation_type", "violation_date", "discovered_on", "status",
			"occurrence", "action", "days", "percent", "daily_wage", "amount", "capped_note", "payroll_date", "additional_salary",
			"description", "source_ref", "issued_by", "issued_on", "acknowledged_on", "employee_reply", "creation")
	return {k: (str(d.get(k)) if k in ("violation_date", "discovered_on", "payroll_date", "issued_on", "acknowledged_on", "creation")
				and d.get(k) else d.get(k)) for k in keep}


# ------------------------------------------------------------------ HR
@frappe.whitelist()
def violation_types(include_disabled=0):
	require_hr()
	filters = {} if cint(include_disabled) else {"enabled": 1}
	rows = frappe.get_all("AlphaX Violation Type", filters=filters, fields=["*"], order_by="category asc, violation_name asc")
	return [{"name": r.name, "title": r.violation_name, "title_ar": r.title_ar, "category": r.category, "enabled": cint(r.enabled),
			 "source": r.source, "min_minutes": r.min_minutes, "max_minutes": r.max_minutes,
			 "steps": parse_json(r.steps_json, []) or []} for r in rows]


@frappe.whitelist(methods=["POST"])
def save_violation_type(name, data):
	from alphax_hr.api._common import require_hr_manager

	require_hr_manager()
	payload = parse_json(data, {})
	t = frappe.get_doc("AlphaX Violation Type", name) if frappe.db.exists("AlphaX Violation Type", name) else \
		frappe.new_doc("AlphaX Violation Type")
	if t.is_new():
		t.violation_name = name
	for k in ("title_ar", "category", "enabled", "source", "min_minutes", "max_minutes"):
		if k in payload:
			t.set(k, payload[k])
	if "steps" in payload:
		for s in payload["steps"] or []:
			try:
				rules.step_for([s], 1)
			except ValueError as e:
				frappe.throw(str(e))
		t.steps_json = json.dumps(payload["steps"] or [])
	t.save()
	return {"name": t.name}


@frappe.whitelist()
def preview(employee, violation_type, violation_date, payroll_date=None):
	require_hr()
	doc = frappe.new_doc("AlphaX Penalty")
	doc.update({"employee": employee, "violation_type": violation_type, "violation_date": violation_date, "payroll_date": payroll_date})
	return _out(preview_doc(doc))


@frappe.whitelist(methods=["POST"])
def create(employee, violation_type, violation_date, description, discovered_on=None, payroll_date=None, issue=0, source_ref=None):
	require_hr()
	if getdate(violation_date) > getdate(nowdate()):
		frappe.throw(_("The violation date cannot be in the future."))
	if source_ref and frappe.db.exists("AlphaX Penalty", {"source_ref": source_ref, "status": ["!=", "Cancelled"]}):
		frappe.throw(_("A penalty for this attendance record already exists."))
	doc = frappe.new_doc("AlphaX Penalty")
	doc.update({"employee": employee, "violation_type": violation_type, "violation_date": violation_date,
				"discovered_on": discovered_on or violation_date, "description": description, "payroll_date": payroll_date,
				"source_ref": source_ref, "status": "Draft"})
	preview_doc(doc).insert()
	if cint(issue):
		return issue_penalty(doc.name)
	return _out(doc)


@frappe.whitelist(methods=["POST"])
def issue_penalty(name):
	require_hr()
	doc = frappe.get_doc("AlphaX Penalty", name)
	if doc.status != "Draft":
		frappe.throw(_("Only a draft can be issued."))
	if (getdate(nowdate()) - getdate(doc.discovered_on or doc.violation_date)).days > rules.DISCOVERY_LIMIT_DAYS:
		frappe.throw(_("This violation was discovered more than {0} days ago and can no longer be penalised.").format(
			rules.DISCOVERY_LIMIT_DAYS))
	preview_doc(doc)
	if doc.amount > 0:
		from alphax_hr.api._common import require_salary_structure

		require_salary_structure(doc.employee, doc.payroll_date, _("Assign a salary first, or record it as a warning."))
		add = frappe.get_doc({"doctype": "Additional Salary", "employee": doc.employee, "company": doc.company,
							  "salary_component": _component(doc.company), "amount": doc.amount,
							  "payroll_date": doc.payroll_date, "overwrite_salary_structure_amount": 0})
		add.insert(ignore_permissions=True)
		add.submit()
		doc.additional_salary = add.name
	doc.status, doc.issued_by, doc.issued_on = "Issued", frappe.session.user, now_datetime()
	doc.save()
	_notify(doc)
	return _out(doc)


def _notify(doc):
	user = frappe.db.get_value("Employee", doc.employee, "user_id")
	if not user:
		return
	frappe.get_doc({"doctype": "Notification Log", "for_user": user, "type": "Alert", "document_type": "AlphaX Penalty",
					"document_name": doc.name, "subject": _("A {0} was issued to you: {1}").format(_(doc.action).lower(), doc.violation_type)
					}).insert(ignore_permissions=True)


@frappe.whitelist(methods=["POST"])
def cancel_penalty(name, reason):
	require_hr()
	if not (reason or "").strip():
		frappe.throw(_("Please give a reason for cancelling."))
	doc = frappe.get_doc("AlphaX Penalty", name)
	if doc.status == "Cancelled":
		return _out(doc)
	if doc.additional_salary and frappe.db.get_value("Additional Salary", doc.additional_salary, "docstatus") == 1:
		add = frappe.get_doc("Additional Salary", doc.additional_salary)
		add.flags.ignore_permissions = True  # the endpoint is HR-only; payroll roles may not hold cancel rights
		add.cancel()
	doc.status = "Cancelled"
	doc.save()
	doc.add_comment("Comment", frappe.utils.escape_html(_("Cancelled: {0}").format(reason[:1000])))
	return _out(doc)


@frappe.whitelist()
def penalties(employee=None, status=None, month=None, violation_type=None, limit=500):
	require_hr()
	filters = {}
	if employee:
		filters["employee"] = employee
	if status:
		filters["status"] = status
	if violation_type:
		filters["violation_type"] = violation_type
	if month:
		filters["violation_date"] = ["between", [get_first_day(month), get_last_day(month)]]
	rows = frappe.get_list("AlphaX Penalty", filters=filters, fields=["*"], order_by="violation_date desc",
						   page_length=min(cint(limit) or 500, 2000))
	return [_out(r) for r in rows]


@frappe.whitelist()
def suggestions(month=None, department=None):
	"""Attendance issues of the month that match a violation type and have no penalty yet."""
	require_hr()
	from alphax_hr.api.attendance import month_data
	from alphax_hr.saudi.attendance import ABSENT

	data = month_data(month, department)
	vts = [v for v in violation_types() if v["source"]]
	taken = set(frappe.get_all("AlphaX Penalty", filters={"source_ref": ["is", "set"], "status": ["!=", "Cancelled"]}, pluck="source_ref"))
	limit_day = getdate(add_days(nowdate(), -rules.DISCOVERY_LIMIT_DAYS))
	out = []
	for row in data["rows"]:
		if row.get("no_penalties"):
			continue
		for c in row["cells"]:
			if c.get("not_employed") or getdate(c["date"]) < limit_day:
				continue
			hits = []
			if c.get("late"):
				hits += [(v, "Late Arrival", c["late"]) for v in vts if v["source"] == "Late Arrival"
						 and rules.late_matches(int(c["late"]), v["min_minutes"], v["max_minutes"])]
			if c.get("early"):
				hits += [(v, "Early Exit", c["early"]) for v in vts if v["source"] == "Early Exit"
						 and rules.late_matches(int(c["early"]), v["min_minutes"], v["max_minutes"])]
			if c["code"] == ABSENT:
				hits += [(v, "Absence", None) for v in vts if v["source"] == "Absence"]
			for v, src, minutes in hits[:1]:
				ref = f"{row['employee']}:{c['date']}:{src}"
				if ref in taken:
					continue
				out.append({"employee": row["employee"], "employee_name": row["employee_name"], "department": row["department"],
							"date": c["date"], "source": src, "minutes": minutes, "violation_type": v["name"], "source_ref": ref})
	return out


# ------------------------------------------------------------------ employee
@frappe.whitelist()
def mine():
	employee = current_employee()
	rows = frappe.get_all("AlphaX Penalty", filters={"employee": employee, "status": ["!=", "Draft"]}, fields=["*"],
						  order_by="violation_date desc")
	out = []
	for r in rows:
		o = _out(r)
		o["can_object"] = r.status == "Issued" and r.issued_on and \
			(getdate(nowdate()) - getdate(r.issued_on)).days <= rules.OBJECTION_DAYS
		out.append(o)
	return out


@frappe.whitelist(methods=["POST"])
def respond(name, action, reply=None):
	"""Employee acknowledges a penalty, or objects (with a reply) within 15 days."""
	login_required()
	doc = frappe.get_doc("AlphaX Penalty", name)
	if doc.employee != current_employee():
		frappe.throw(_("Not permitted."), frappe.PermissionError)
	if doc.status != "Issued":
		frappe.throw(_("This penalty has already been answered."))
	if action == "Object":
		if (getdate(nowdate()) - getdate(doc.issued_on)).days > rules.OBJECTION_DAYS:
			frappe.throw(_("Objections must be made within {0} days.").format(rules.OBJECTION_DAYS))
		if not (reply or "").strip():
			frappe.throw(_("Please explain your objection."))
		doc.status = "Objected"
	elif action == "Acknowledge":
		doc.status = "Acknowledged"
	else:
		frappe.throw(_("Unknown action."))
	doc.employee_reply = (reply or "")[:2000] or doc.employee_reply
	doc.acknowledged_on = now_datetime()
	doc.flags.ignore_permissions = True
	doc.save()
	return _out(doc)


def query_conditions(user=None):
	user = user or frappe.session.user
	if user == "Administrator" or is_hr(user):
		return ""
	emp = frappe.db.get_value("Employee", {"user_id": user}, "name") or ""
	return "(`tabAlphaX Penalty`.employee = {0} and `tabAlphaX Penalty`.status != 'Draft')".format(frappe.db.escape(emp))


def has_permission(doc, ptype=None, user=None):
	user = user or frappe.session.user
	if user == "Administrator" or is_hr(user):
		return True
	emp = frappe.db.get_value("Employee", {"user_id": user}, "name")
	return bool(emp and doc.employee == emp and doc.status != "Draft" and ptype in (None, "read", "print"))
