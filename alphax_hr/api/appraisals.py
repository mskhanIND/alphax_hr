"""Appraisals: HRMS Appraisal Cycles and Appraisals, shown and opened inside AlphaX."""
from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate

from alphax_hr.api._common import current_employee, is_hr, login_required, parse_json, require_hr, require_hr_manager

FIELDS = ["name", "employee", "employee_name", "department", "designation", "appraisal_cycle", "docstatus", "total_score",
		  "self_score", "avg_feedback_score", "goal_score_percentage", "final_score", "start_date", "end_date", "modified"]


def _rows(filters, limit=500):
	if not frappe.db.exists("DocType", "Appraisal"):
		return []
	meta = frappe.get_meta("Appraisal")
	rows = frappe.get_list("Appraisal", filters=filters, fields=[f for f in FIELDS if f in ("name", "docstatus", "modified") or meta.has_field(f)],
						   order_by="modified desc", page_length=min(cint(limit) or 500, 2000))
	for r in rows:
		r["status"] = {0: "Draft", 1: "Submitted", 2: "Cancelled"}[r.docstatus]
		for k in ("start_date", "end_date", "modified"):
			if r.get(k):
				r[k] = str(r[k])
	return rows


@frappe.whitelist()
def cycles():
	require_hr()
	if not frappe.db.exists("DocType", "Appraisal Cycle"):
		return {"installed": False, "cycles": []}
	out = frappe.get_list("Appraisal Cycle", fields=["name", "cycle_name", "start_date", "end_date", "status", "company"],
						  order_by="start_date desc", page_length=200)
	for c in out:
		rows = frappe.get_all("Appraisal", filters={"appraisal_cycle": c.name, "docstatus": ["<", 2]}, fields=["docstatus", "final_score"])
		done = [r for r in rows if r.docstatus == 1]
		c.update({"appraisals": len(rows), "submitted": len(done),
				  "average": flt(sum(flt(r.final_score) for r in done) / len(done), 2) if done else 0,
				  "start_date": str(c.start_date), "end_date": str(c.end_date)})
	return {"installed": True, "cycles": out}


@frappe.whitelist()
def appraisals(cycle: str | None = None, department: str | None = None):
	require_hr()
	filters = {"docstatus": ["<", 2]}
	if cycle:
		filters["appraisal_cycle"] = cycle
	if department:
		filters["department"] = department
	return _rows(filters)


@frappe.whitelist()
def mine():
	"""The employee's own appraisals. Many sites give employees no role access to Appraisal, so the list is
	read for their own employee only (scores, not the form); the record opens only where they may read it."""
	employee = current_employee()
	if not frappe.db.exists("DocType", "Appraisal"):
		return []
	meta = frappe.get_meta("Appraisal")
	rows = frappe.get_all("Appraisal", filters={"employee": employee, "docstatus": ["<", 2]},
						  fields=[f for f in FIELDS if f in ("name", "docstatus", "modified") or meta.has_field(f)],
						  order_by="modified desc", limit_page_length=50)
	can_open = frappe.has_permission("Appraisal", "read")
	for r in rows:
		r["status"] = {0: "Draft", 1: "Submitted", 2: "Cancelled"}[r.docstatus]
		r["can_open"] = can_open
		r["stage"] = _stage(r)
		for k in ("start_date", "end_date", "modified"):
			if r.get(k):
				r[k] = str(r[k])
	return rows


# ====================================================================== performance appraisal in AlphaX
# HR builds templates (goals + rating criteria with weights) and starts a cycle; the employee rates themselves;
# the reporting manager scores the goals and gives feedback; HR finalises. HRMS computes the scores.

STARS = 5


def _installed():
	if not frappe.db.exists("DocType", "Appraisal Cycle"):
		frappe.throw(_("Appraisals need Frappe HRMS."))


def _weights_ok(rows, label):
	total = round(sum(flt(r.get("weight")) for r in rows), 2)
	if rows and total != 100:
		frappe.throw(_("{0} weights must add up to 100% (now {1}%).").format(label, total))


def _template_dict(name):
	t = frappe.get_doc("Appraisal Template", name)
	return {"name": t.name, "title": t.template_title, "description": t.description,
			"goals": [{"kra": g.key_result_area, "weight": flt(g.per_weightage)} for g in t.goals],
			"criteria": [{"criteria": c.criteria, "weight": flt(c.per_weightage)} for c in t.rating_criteria],
			"designations": frappe.get_all("Designation", filters={"appraisal_template": t.name}, pluck="name")}


@frappe.whitelist()
def setup():
	"""Templates, designations and what HR needs to start a cycle."""
	require_hr()
	_installed()
	templates = [_template_dict(n) for n in frappe.get_all("Appraisal Template", pluck="name", order_by="name")]
	return {"templates": templates,
			"designations": frappe.get_all("Designation", fields=["name", "appraisal_template"], order_by="name"),
			"companies": frappe.get_list("Company", pluck="name", order_by="name"),
			"departments": frappe.get_all("Department", filters={"is_group": 0}, pluck="name", order_by="name"),
			"branches": frappe.get_all("Branch", pluck="name", order_by="name"),
			"can_edit": bool(set(frappe.get_roles()) & {"HR Manager", "System Manager"})}


@frappe.whitelist(methods=["POST"])
def save_template(data: str | dict | list):
	"""Create or update a template; goals (KRAs) and rating criteria are created when new."""
	require_hr_manager()
	_installed()
	data = parse_json(data) or {}
	title = (data.get("title") or "").strip()
	goals = [g for g in data.get("goals") or [] if (g.get("kra") or "").strip()]
	criteria = [c for c in data.get("criteria") or [] if (c.get("criteria") or "").strip()]
	if not title or not goals or not criteria:
		frappe.throw(_("A template needs a title, at least one goal and one rating criterion."))
	_weights_ok(goals, _("Goal"))
	_weights_ok(criteria, _("Criteria"))
	for g in goals:
		g["kra"] = g["kra"].strip()
		if not frappe.db.exists("KRA", g["kra"]):
			frappe.get_doc({"doctype": "KRA", "title": g["kra"]}).insert(ignore_permissions=True)
	for c in criteria:
		c["criteria"] = c["criteria"].strip()
		if not frappe.db.exists("Employee Feedback Criteria", c["criteria"]):
			frappe.get_doc({"doctype": "Employee Feedback Criteria", "criteria": c["criteria"]}).insert(ignore_permissions=True)
	name = data.get("name")
	t = frappe.get_doc("Appraisal Template", name) if name else frappe.new_doc("Appraisal Template")
	if not name:
		t.template_title = title
	t.description = data.get("description")
	t.set("goals", [{"key_result_area": g["kra"], "per_weightage": flt(g["weight"])} for g in goals])
	t.set("rating_criteria", [{"criteria": c["criteria"], "per_weightage": flt(c["weight"])} for c in criteria])
	t.flags.ignore_permissions = True
	t.save()
	for d in data.get("designations") or []:
		if frappe.db.exists("Designation", d):
			frappe.db.set_value("Designation", d, "appraisal_template", t.name)
	return _template_dict(t.name)


def _cycle_employees(data):
	filters = {"status": "Active", "company": data.get("company")}
	for k in ("department", "branch", "designation"):
		if data.get(k):
			filters[k] = data[k]
	if data.get("employees"):
		filters["name"] = ["in", list(data["employees"])]
	emps = frappe.get_all("Employee", filters=filters, fields=["name", "employee_name", "department", "designation", "branch"],
						  order_by="employee_name asc")
	by_designation = {d.name: d.appraisal_template for d in frappe.get_all("Designation", fields=["name", "appraisal_template"])}
	for e in emps:
		e.template = by_designation.get(e.designation) or data.get("template") or None
	return emps


@frappe.whitelist(methods=["POST"])
def preview_cycle(data: str | dict | list):
	require_hr()
	_installed()
	emps = _cycle_employees(parse_json(data) or {})
	return {"employees": emps, "missing_template": sum(1 for e in emps if not e.template)}


@frappe.whitelist(methods=["POST"])
def start_cycle(data: str | dict | list):
	"""Create the cycle (manual rating) and one appraisal per employee."""
	require_hr_manager()
	_installed()
	from hrms.hr.doctype.appraisal_cycle.appraisal_cycle import create_appraisals_for_cycle

	data = parse_json(data) or {}
	if not (data.get("cycle_name") and data.get("company") and data.get("start_date") and data.get("end_date")):
		frappe.throw(_("Name, company and period are required."))
	if getdate(data["end_date"]) < getdate(data["start_date"]):
		frappe.throw(_("The end date is before the start date."))
	emps = _cycle_employees(data)
	if not emps:
		frappe.throw(_("No active employees match this choice."))
	missing = [e.employee_name for e in emps if not e.template]
	if missing:
		frappe.throw(_("Choose a template for: {0}").format(", ".join(missing[:10])), title=_("Template missing"))
	cycle = frappe.get_doc({"doctype": "Appraisal Cycle", "cycle_name": data["cycle_name"], "company": data["company"],
							"start_date": data["start_date"], "end_date": data["end_date"], "kra_evaluation_method": "Manual Rating",
							"department": data.get("department"), "branch": data.get("branch"), "designation": data.get("designation"),
							"description": data.get("description"), "status": "In Progress",
							"appraisees": [{"employee": e.name, "employee_name": e.employee_name, "department": e.department,
											"designation": e.designation, "branch": e.branch, "appraisal_template": e.template} for e in emps]})
	cycle.flags.ignore_permissions = True
	cycle.insert()
	if len(emps) > 30:
		frappe.enqueue(create_appraisals_for_cycle, queue="long", timeout=1200, appraisal_cycle=cycle)
	else:
		frappe.flags.ignore_permissions = True
		try:
			create_appraisals_for_cycle(cycle)
		finally:
			frappe.flags.ignore_permissions = False
	from alphax_hr.api import alerts

	users = [u for u in frappe.get_all("Employee", filters={"name": ["in", [e.name for e in emps]]}, pluck="user_id") if u]
	alerts.event("Announcement", _("Appraisal started: {0}").format(cycle.cycle_name),
				 _("Rate yourself in My performance before {0}.").format(frappe.utils.formatdate(cycle.end_date)),
				 users=users, url="/alphax/me/performance", doc=("Appraisal Cycle", cycle.name), tag=f"apr-{cycle.name}")
	return {"name": cycle.name, "employees": len(emps)}


def _feedback_by(appraisal, reviewer):
	return frappe.db.get_value("Employee Performance Feedback", {"appraisal": appraisal, "reviewer": reviewer, "docstatus": 1},
							   ["name", "total_score", "feedback"], as_dict=True)


def _manager_employee(employee):
	return frappe.db.get_value("Employee", employee, "reports_to")


def _stage(a):
	if a.docstatus == 1:
		return "Final"
	reviewed = frappe.db.exists("Employee Performance Feedback", {"appraisal": a.name, "docstatus": 1})
	self_done = flt(a.self_score) > 0
	return "Reviewed" if reviewed else ("Self done" if self_done else "Waiting for self")


@frappe.whitelist()
def cycle_detail(name: str):
	require_hr()
	c = frappe.get_doc("Appraisal Cycle", name)
	rows = frappe.get_all("Appraisal", filters={"appraisal_cycle": name, "docstatus": ["<", 2]},
						  fields=["name", "employee", "employee_name", "department", "designation", "docstatus", "self_score",
								  "avg_feedback_score", "total_score", "final_score"], order_by="employee_name asc")
	for r in rows:
		r.stage = _stage(r)
		boss = _manager_employee(r.employee)
		r.manager_name = frappe.db.get_value("Employee", boss, "employee_name") if boss else None
	counts = {s: sum(1 for r in rows if r.stage == s) for s in ("Waiting for self", "Self done", "Reviewed", "Final")}
	return {"name": c.name, "cycle_name": c.cycle_name, "status": c.status, "start_date": str(c.start_date), "end_date": str(c.end_date),
			"company": c.company, "rows": rows, "counts": counts, "average": flt(sum(flt(r.final_score) for r in rows if r.docstatus == 1)
																			 / max(1, counts["Final"]), 2)}


def _role_on(a, user):
	"""employee / manager / hr (strongest first for the actions they may take)."""
	roles = set()
	own = frappe.db.get_value("Employee", {"user_id": user}, "name")
	if own and own == a.employee:
		roles.add("employee")
	boss = _manager_employee(a.employee)
	if boss and own and boss == own:
		roles.add("manager")
	if is_hr(user):
		roles.add("hr")
	return roles


@frappe.whitelist()
def appraisal(name: str):
	"""One appraisal with what this user can do on it."""
	user = login_required()
	a = frappe.get_doc("Appraisal", name)
	roles = _role_on(a, user)
	if not roles:
		raise frappe.PermissionError
	open_cycle = frappe.db.get_value("Appraisal Cycle", a.appraisal_cycle, "status") != "Completed"
	reviewer = frappe.db.get_value("Employee", {"user_id": user}, "name")
	mine = _feedback_by(a.name, reviewer) if reviewer else None
	manager_fb = None
	boss = _manager_employee(a.employee)
	if boss and ("manager" in roles or "hr" in roles or a.docstatus == 1):
		fb_name = frappe.db.get_value("Employee Performance Feedback", {"appraisal": a.name, "reviewer": boss, "docstatus": 1})
		if fb_name:
			fb = frappe.get_doc("Employee Performance Feedback", fb_name)
			manager_fb = {"feedback": fb.feedback, "total_score": fb.total_score, "reviewer_name": fb.reviewer_name,
						  "ratings": {r.criteria: round(flt(r.rating) * STARS, 1) for r in fb.feedback_ratings}}
	draft = a.docstatus == 0 and open_cycle
	return {
		"name": a.name, "employee": a.employee, "employee_name": a.employee_name, "designation": a.designation,
		"department": a.department, "cycle": a.appraisal_cycle, "start_date": str(a.start_date), "end_date": str(a.end_date),
		"docstatus": a.docstatus, "template": a.appraisal_template,
		"goals": [{"kra": g.kra, "weight": flt(g.per_weightage), "score": flt(g.score)} for g in a.goals]
		or [{"kra": g.kra, "weight": flt(g.per_weightage), "score": round(flt(g.goal_score) / 20, 1)} for g in a.appraisal_kra],
		"self_ratings": [{"criteria": r.criteria, "weight": flt(r.per_weightage), "stars": round(flt(r.rating) * STARS, 1)} for r in a.self_ratings],
		"reflections": a.reflections, "remarks": a.remarks,
		"scores": {"goals": flt(a.total_score), "self": flt(a.self_score), "feedback": flt(a.avg_feedback_score), "final": flt(a.final_score)},
		"manager_feedback": manager_fb if ("employee" not in roles or a.docstatus == 1 or "hr" in roles or "manager" in roles) else None,
		"my_feedback": bool(mine),
		"can_self": "employee" in roles and draft,
		"can_review": bool(("manager" in roles or "hr" in roles) and draft and reviewer and reviewer != a.employee),
		"can_finalise": "hr" in roles and draft,
		"roles": sorted(roles),
	}


def _stars(v):
	return max(0.0, min(float(STARS), flt(v))) / STARS


@frappe.whitelist(methods=["POST"])
def save_self(name: str, ratings: str | dict | list | None = None, reflections: str | dict | list | None = None):
	user = login_required()
	a = frappe.get_doc("Appraisal", name)
	if "employee" not in _role_on(a, user) or a.docstatus != 0:
		raise frappe.PermissionError
	ratings = parse_json(ratings) or {}
	for r in a.self_ratings:
		if r.criteria in ratings:
			r.rating = _stars(ratings[r.criteria])
	if reflections is not None:
		a.reflections = frappe.utils.escape_html(str(reflections)[:5000]).replace("\n", "<br>")
	a.flags.ignore_permissions = True
	a.save()
	return appraisal(name)


@frappe.whitelist(methods=["POST"])
def save_review(name: str, goals: str | dict | list | None = None, ratings: str | dict | list | None = None, feedback: str | dict | list | None = None):
	"""Reporting manager (or HR): score the goals 0-5 and rate the criteria; one feedback per reviewer (replaced on edit)."""
	user = login_required()
	a = frappe.get_doc("Appraisal", name)
	roles = _role_on(a, user)
	if not roles & {"manager", "hr"} or a.docstatus != 0:
		raise frappe.PermissionError
	reviewer = frappe.db.get_value("Employee", {"user_id": user}, "name")
	if not reviewer or reviewer == a.employee:
		frappe.throw(_("Reviews are given from an employee record other than the appraised employee."))
	goals = parse_json(goals) or {}
	if a.goals:
		for g in a.goals:
			if g.kra in goals:
				g.score = max(0.0, min(float(STARS), flt(goals[g.kra])))
		a.calculate_total_score()
	a.flags.ignore_permissions = True
	a.save()
	ratings = parse_json(ratings) or {}
	old = _feedback_by(a.name, reviewer)
	if old:
		prev = frappe.get_doc("Employee Performance Feedback", old.name)
		prev.flags.ignore_permissions = True
		prev.cancel()
	fb = frappe.get_doc({"doctype": "Employee Performance Feedback", "appraisal": a.name, "employee": a.employee,
						 "reviewer": reviewer, "added_on": frappe.utils.now(), "appraisal_cycle": a.appraisal_cycle,
						 "feedback": frappe.utils.escape_html(str(feedback or "")[:5000]).replace("\n", "<br>") or "-",
						 "feedback_ratings": [{"criteria": r.criteria, "per_weightage": r.per_weightage,
											   "rating": _stars(ratings.get(r.criteria, 0))} for r in a.self_ratings]})
	fb.flags.ignore_permissions = True
	fb.insert()
	fb.submit()
	user_id = frappe.db.get_value("Employee", a.employee, "user_id")
	if user_id and user_id != user:
		from alphax_hr.api import alerts

		alerts.event("Request decision", _("Your manager reviewed your appraisal"), a.appraisal_cycle or "",
					 users=[user_id], url="/alphax/me/performance", doc=("Appraisal", a.name), tag=f"apr-{a.name}")
	return appraisal(name)


@frappe.whitelist(methods=["POST"])
def finalise(name: str, remarks: str | None = None):
	require_hr()
	a = frappe.get_doc("Appraisal", name)
	if a.docstatus != 0:
		frappe.throw(_("This appraisal is already final."))
	if remarks:
		a.remarks = str(remarks)[:2000]
	a.flags.ignore_permissions = True
	if a.goals:
		a.calculate_total_score()
	a.save()
	a.submit()
	user_id = frappe.db.get_value("Employee", a.employee, "user_id")
	if user_id:
		from alphax_hr.api import alerts

		alerts.event("Request decision", _("Your appraisal is final: {0:.2f} / 5").format(flt(a.final_score)), a.appraisal_cycle or "",
					 users=[user_id], url="/alphax/me/performance", doc=("Appraisal", a.name), tag=f"apr-{a.name}")
	return appraisal(name)


@frappe.whitelist(methods=["POST"])
def finalise_reviewed(cycle: str):
	"""Finalise every appraisal of the cycle that the manager has reviewed."""
	require_hr()
	done, failed = [], []
	for r in frappe.get_all("Appraisal", filters={"appraisal_cycle": cycle, "docstatus": 0}, pluck="name"):
		if not frappe.db.exists("Employee Performance Feedback", {"appraisal": r, "docstatus": 1}):
			continue
		try:
			finalise(r)
			done.append(r)
		except Exception as exc:  # noqa: BLE001
			failed.append({"name": r, "error": str(exc)[:200]})
			frappe.clear_messages()
	return {"done": done, "failed": failed}


@frappe.whitelist(methods=["POST"])
def complete_cycle(name: str):
	require_hr_manager()
	c = frappe.get_doc("Appraisal Cycle", name)
	c.flags.ignore_permissions = True
	c.complete_cycle()
	return cycle_detail(name)


@frappe.whitelist()
def team():
	"""Open appraisals of the manager's direct reports, and the appraisal requests they raised."""
	user = login_required()
	me = frappe.db.get_value("Employee", {"user_id": user}, "name")
	if not me:
		return {"reports": [], "appraisals": [], "requests": []}
	reports = frappe.get_all("Employee", filters={"reports_to": me, "status": "Active"}, fields=["name", "employee_name", "designation"],
							 order_by="employee_name asc")
	ids = [r.name for r in reports]
	rows = frappe.get_all("Appraisal", filters={"employee": ["in", ids or [""]], "docstatus": ["<", 2]},
						  fields=["name", "employee", "employee_name", "appraisal_cycle", "docstatus", "self_score", "avg_feedback_score",
								  "total_score", "final_score", "start_date", "end_date"], order_by="modified desc", limit=200)
	for r in rows:
		r.stage = _stage(r)
		r.start_date, r.end_date = str(r.start_date), str(r.end_date)
	requests = frappe.get_all("AlphaX Request", filters={"employee": ["in", ids or [""]],
														  "request_type": ["in", frappe.get_all("AlphaX Request Type", filters={"category": "Performance"}, pluck="name") or [""]]},
							  fields=["name", "employee_name", "request_type", "status", "creation"], order_by="creation desc", limit=50) \
		if frappe.db.exists("DocType", "AlphaX Request") else []
	for r in requests:
		r.creation = str(r.creation)
	return {"reports": reports, "appraisals": rows, "requests": requests}


@frappe.whitelist()
def management():
	"""Who approves at management level (users with the AlphaX Management role)."""
	require_hr()
	from alphax_hr.api.requests import management_users

	return [{"user": u, "full_name": frappe.utils.get_fullname(u),
			 "employee": frappe.db.get_value("Employee", {"user_id": u}, "employee_name")} for u in management_users()]


@frappe.whitelist(methods=["POST"])
def set_management(user: str, enabled: int | str = 1):
	require_hr_manager()
	if not frappe.db.exists("User", user) and frappe.db.exists("Employee", user):
		user = frappe.db.get_value("Employee", user, "user_id")
	if not user or not frappe.db.exists("User", user):
		frappe.throw(_("This person has no user account."))
	u = frappe.get_doc("User", user)
	has = any(r.role == "AlphaX Management" for r in u.roles)
	if cint(enabled) and not has:
		u.append("roles", {"role": "AlphaX Management"})
	elif not cint(enabled) and has:
		u.set("roles", [r for r in u.roles if r.role != "AlphaX Management"])
	u.flags.ignore_permissions = True
	u.save()
	return management()
