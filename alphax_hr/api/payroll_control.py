"""Payroll control centre: one month, one company, one tracked run.

Open -> Prepared -> Reviewed -> Approved -> Processed (HRMS Payroll Entry + slips) -> Closed.
Every step records who and when, and keeps a snapshot of the checklist it was taken on.
Blocking items stop a step unless an HR Manager overrides them with a note.
"""
from __future__ import annotations

import json

import frappe
from frappe import _
from frappe.utils import add_days, cint, flt, get_first_day, get_last_day, getdate, now_datetime, nowdate

from alphax_hr.api._common import is_hr_manager, require_hr, require_hr_manager

STEPS = {"prepare": ("Open", "Prepared"), "review": ("Prepared", "Reviewed"), "approve": ("Reviewed", "Approved"),
		 "process": ("Approved", "Processed"), "close": ("Processed", "Closed")}
OVERTIME_COMPONENTS = ("Overtime", "Overtime Allowance", "Over Time")
MAX_ITEMS = 50


def _bounds(month):
	ref = getdate(month or nowdate())
	return getdate(get_first_day(ref)), getdate(get_last_day(ref))


def _check(key, label, items, severity="warning", hint=None, link=None, count=None):
	items = list(items)
	return {"key": key, "label": label, "severity": severity if (count if count is not None else len(items)) else "ok",
			"count": count if count is not None else len(items), "items": items[:MAX_ITEMS], "hint": hint, "link": link}


def _emp_item(e, note=None, doctype="Employee", name=None):
	return {"employee": e.get("employee") or e.get("name"), "employee_name": e.get("employee_name"),
			"doctype": doctype, "name": name or e.get("name"), "note": note}


def _active(company, start, end):
	"""Employees on the payroll for the month: active, or left during it."""
	meta = frappe.get_meta("Employee")
	fields = ["name", "employee_name", "date_of_joining", "relieving_date", "status", "salary_mode", "bank_ac_no"] + [
		f for f in ("iban", "alphax_is_saudi") if meta.has_field(f)]
	return frappe.get_all("Employee", filters={"company": company, "date_of_joining": ["<=", end]},
						  or_filters={"status": "Active", "relieving_date": [">=", start]}, fields=fields)


def _overlap(start, end, a="from_date", b="to_date"):
	return {a: ["<=", end], b: [">=", start]}


def checklist(company, month):
	"""Everything payroll depends on for the month, with the records behind each number."""
	start, end = _bounds(month)
	emps = _active(company, start, end)
	ids = [e.name for e in emps]
	by_id = {e.name: e for e in emps}
	checks = []
	if not ids:
		return {"start": str(start), "end": str(end), "employees": 0, "checks": [], "blockers": 0, "warnings": 0}

	def pending(dt, filters, label, note_fn, link):
		if not frappe.db.exists("DocType", dt):
			return
		rows = frappe.get_all(dt, filters={**filters, "employee": ["in", ids]}, fields=["name", "employee", "employee_name"] +
							  [f for f in ("from_date", "to_date", "leave_type", "total_leave_days") if frappe.get_meta(dt).has_field(f)])
		checks.append(_check(f"pending_{frappe.scrub(dt)}", label, [_emp_item(r, note_fn(r), dt, r.name) for r in rows],
							 "blocker", _("Decide these before payroll so pay and deductions are right."), link))

	pending("Leave Application", {"docstatus": 0, "status": "Open", **_overlap(start, end)}, _("Leave requests waiting for approval"),
			lambda r: f"{r.leave_type} {r.from_date} → {r.to_date}", "/approvals")
	pending("Attendance Request", {"docstatus": 0, **_overlap(start, end)}, _("Attendance requests waiting"),
			lambda r: f"{r.from_date} → {r.to_date}", "/approvals")
	pending("Shift Request", {"docstatus": 0, "status": "Draft", **_overlap(start, end)}, _("Shift requests waiting"),
			lambda r: f"{r.from_date} → {r.to_date}", "/approvals")
	if frappe.db.exists("DocType", "AlphaX Request"):
		fin = frappe.get_all("AlphaX Request Type", filters={"category": ["in", ["Finance", "Separation"]]}, pluck="name")
		rows = frappe.get_all("AlphaX Request", filters={"employee": ["in", ids], "status": ["in", ["Pending Manager", "Pending HR"]],
														 "request_type": ["in", fin or [""]]}, fields=["name", "employee", "employee_name", "request_type"])
		checks.append(_check("pending_requests", _("Advance / resignation requests waiting"),
							 [_emp_item(r, r.request_type, "AlphaX Request", r.name) for r in rows], "blocker", None, "/requests"))
	if frappe.db.exists("DocType", "Expense Claim"):
		rows = frappe.get_all("Expense Claim", filters={"employee": ["in", ids], "docstatus": 0, "approval_status": "Draft",
														"posting_date": ["<=", end]}, fields=["name", "employee", "employee_name", "total_claimed_amount"])
		checks.append(_check("pending_expense", _("Expense claims waiting"), [_emp_item(r, str(r.total_claimed_amount), "Expense Claim", r.name) for r in rows],
							 "warning", None, "/approvals"))

	# attendance completeness (worked days drive pay for joiners, absences and unpaid leave)
	try:
		from alphax_hr.api.attendance import month_data
		from alphax_hr.saudi.attendance import MISSING_PUNCH, NOT_MARKED, ABSENT

		data = month_data(str(start), None, company)
		att_items, absent_items, ot_hours = [], [], 0.0
		for r in data["rows"]:
			t = r["totals"]
			gaps = int(t.get(MISSING_PUNCH, 0) + t.get(NOT_MARKED, 0))
			if gaps:
				att_items.append(_emp_item(r, _("{0} day(s) with a missing punch or not marked").format(gaps)))
			if t.get(ABSENT):
				absent_items.append(_emp_item(r, _("{0} day(s) absent").format(int(t[ABSENT]))))
			ot_hours += t.get("overtime_hours", 0)
		checks.append(_check("attendance_gaps", _("Attendance gaps (missing punch / not marked)"), att_items, "warning",
							 _("Fix or mark attendance so absences are not paid by mistake."), "/attendance"))
		checks.append(_check("absences", _("Absences this month"), absent_items, "info", _("Unpaid unless covered by leave; consider penalties."),
							 "/penalties?tab=suggest"))
	except Exception:  # noqa: BLE001 - the checklist must still load if a shift setup is broken
		frappe.log_error(title="AlphaX payroll checklist: attendance")
		ot_hours = 0.0

	# unpaid and sick leave in the month
	lwp_types = frappe.get_all("Leave Type", filters={"is_lwp": 1}, pluck="name")
	lwp = frappe.get_all("Leave Application", filters={"employee": ["in", ids], "docstatus": 1, "status": "Approved",
													   "leave_type": ["in", lwp_types or [""]], **_overlap(start, end)},
						 fields=["name", "employee", "employee_name", "leave_type", "total_leave_days"])
	checks.append(_check("unpaid_leave", _("Unpaid leave (deducted by payroll)"), [_emp_item(r, f"{r.leave_type}: {r.total_leave_days}", "Leave Application", r.name) for r in lwp], "info"))
	if frappe.get_meta("Leave Application").has_field("alphax_sick_breakdown"):
		sick = frappe.get_all("Leave Application", filters={"employee": ["in", ids], "docstatus": 1, "alphax_sick_breakdown": ["is", "set"],
															**_overlap(start, end)},
							  fields=["name", "employee", "employee_name", "alphax_sick_breakdown"])
		sick = [r for r in sick if "75%" in r.alphax_sick_breakdown or "unpaid" in r.alphax_sick_breakdown.lower()]
		checks.append(_check("sick_tiers", _("Sick leave at 75% or unpaid (Art. 117)"), [_emp_item(r, r.alphax_sick_breakdown, "Leave Application", r.name) for r in sick],
							 "warning", _("Make sure the reduced pay is deducted (Additional Salary or unpaid leave type).")))

	# penalties
	if frappe.db.exists("DocType", "AlphaX Penalty"):
		drafts = frappe.get_all("AlphaX Penalty", filters={"employee": ["in", ids], "status": "Draft", "violation_date": ["<=", end]},
								fields=["name", "employee", "employee_name", "violation_type"])
		checks.append(_check("penalty_drafts", _("Draft penalties not issued"), [_emp_item(r, r.violation_type, "AlphaX Penalty", r.name) for r in drafts],
							 "warning", _("Issue or cancel them; only issued penalties reach payroll."), "/penalties"))
		live = frappe.get_all("AlphaX Penalty", filters={"employee": ["in", ids], "status": ["in", ["Issued", "Acknowledged", "Objected"]],
														 "payroll_date": ["between", [start, end]], "amount": [">", 0]},
							  fields=["name", "employee", "employee_name", "amount", "status"])
		checks.append(_check("penalty_deductions", _("Penalty deductions this month"), [_emp_item(r, f"{r.amount} · {_(r.status)}", "AlphaX Penalty", r.name) for r in live], "info"))
		obj = [r for r in live if r.status == "Objected"]
		checks.append(_check("penalty_objections", _("Objected penalties to decide"), [_emp_item(r, str(r.amount), "AlphaX Penalty", r.name) for r in obj], "warning", None, "/penalties"))

	# overtime
	ot_add = _overtime_added(ids, start, end)
	checks.append(_check("overtime", _("Overtime hours this month"), [], "info" if not ot_hours or ot_add else "warning",
						 _("{0} hours recorded; {1} employee(s) already have overtime pay added.").format(round(ot_hours, 2), len(ot_add)),
						 "/attendance?view=overtime", count=1 if ot_hours and not ot_add else 0))

	# additional salary (bonuses, deductions), advances and loans
	adds = frappe.get_all("Additional Salary", filters={"employee": ["in", ids], "payroll_date": ["between", [start, end]], "docstatus": ["<", 2]},
						  fields=["name", "employee", "employee_name", "salary_component", "amount", "type", "docstatus"])
	checks.append(_check("additional_draft", _("Bonuses / deductions not submitted"), [_emp_item(r, f"{r.salary_component} {r.amount}", "Additional Salary", r.name)
																					   for r in adds if r.docstatus == 0], "blocker",
						 _("Draft Additional Salary records are ignored by payroll.")))
	checks.append(_check("additional", _("Bonuses and other earnings / deductions"), [_emp_item(r, f"{r.salary_component} {r.amount}", "Additional Salary", r.name)
																					   for r in adds if r.docstatus == 1], "info"))
	if frappe.db.exists("DocType", "Employee Advance"):
		adv = frappe.get_all("Employee Advance", filters={"employee": ["in", ids], "docstatus": 1, "status": ["in", ["Paid", "Unpaid"]]},
							 fields=["name", "employee", "employee_name", "advance_amount", "paid_amount", "claimed_amount", "return_amount"])
		adv = [a for a in adv if flt(a.paid_amount) - flt(a.claimed_amount) - flt(a.return_amount) > 0]
		checks.append(_check("advances", _("Advances not yet recovered"), [_emp_item(a, str(flt(a.paid_amount) - flt(a.claimed_amount) - flt(a.return_amount)), "Employee Advance", a.name) for a in adv], "info"))
	if frappe.db.exists("DocType", "Loan"):
		loans = frappe.get_all("Loan", filters={"applicant_type": "Employee", "applicant": ["in", ids], "docstatus": 1,
											   "status": ["in", ["Disbursed", "Partially Disbursed"]], "repay_from_salary": 1},
							   fields=["name", "applicant as employee", "applicant_name as employee_name", "loan_amount"])
		checks.append(_check("loans", _("Loans repaid from salary"), [_emp_item(r, str(r.loan_amount), "Loan", r.name) for r in loans], "info"))

	# joiners / leavers
	joiners = [e for e in emps if e.date_of_joining and start <= getdate(e.date_of_joining) <= end]
	leavers = [e for e in emps if e.relieving_date and start <= getdate(e.relieving_date) <= end]
	checks.append(_check("joiners", _("Joined this month (pro-rata pay)"), [_emp_item(e, str(e.date_of_joining)) for e in joiners], "info"))
	settled = set(frappe.get_all("AlphaX Final Settlement", filters={"employee": ["in", [e.name for e in leavers] or [""]],
																	 "status": ["in", ["Approved", "Paid"]]}, pluck="employee")) \
		if frappe.db.exists("DocType", "AlphaX Final Settlement") else set()
	checks.append(_check("leavers", _("Leaving this month without a final settlement"), [_emp_item(e, str(e.relieving_date)) for e in leavers if e.name not in settled],
						 "warning", _("Prepare the end-of-service settlement so it is paid with this payroll or separately."), "/payroll/settlements"))

	# salary, bank, GOSI
	with_ssa = set(frappe.get_all("Salary Structure Assignment", filters={"employee": ["in", ids], "docstatus": 1, "from_date": ["<=", end]},
								  pluck="employee"))
	checks.append(_check("no_salary", _("No salary structure"), [_emp_item(e) for e in emps if e.name not in with_ssa], "blocker",
						 _("These employees will be left out of payroll."), "/people"))
	no_bank = [e for e in emps if (e.get("salary_mode") or "Bank") == "Bank" and not (e.get("iban") or e.get("bank_ac_no"))]
	checks.append(_check("no_bank", _("Paid by bank without IBAN / account"), [_emp_item(e) for e in no_bank], "warning", None, "/people"))
	if frappe.get_meta("Employee").has_field("alphax_gosi_number"):
		saudis = [e.name for e in emps if cint(e.alphax_is_saudi)]
		missing = frappe.get_all("Employee", filters={"name": ["in", saudis or [""]], "alphax_gosi_number": ["in", ["", None]]},
								 fields=["name", "employee_name"])
		checks.append(_check("gosi_numbers", _("Saudis without a GOSI number"), [_emp_item(e) for e in missing], "warning", None, "/payroll/gosi"))
	from alphax_hr.api._common import settings

	if not settings().salary_gosi_component:
		checks.append(_check("gosi_component", _("GOSI deduction component not set"), [{"note": _("Set it in HR status & setup → Settings.")}],
							 "warning", None, "/setup"))

	# appraisals finished in the month (inputs to increments / bonuses)
	if frappe.db.exists("DocType", "Appraisal"):
		ap = frappe.get_all("Appraisal", filters={"employee": ["in", ids], "docstatus": 1, "modified": ["between", [start, add_days(end, 1)]]},
							fields=["name", "employee", "employee_name", "final_score"])
		checks.append(_check("appraisals", _("Appraisals completed this month"), [_emp_item(r, str(r.final_score), "Appraisal", r.name) for r in ap], "info",
							 _("Apply any agreed increments or bonuses before payroll."), "/appraisals"))

	return {"start": str(start), "end": str(end), "employees": len(ids),
			"checks": checks, "blockers": sum(c["count"] for c in checks if c["severity"] == "blocker"),
			"warnings": sum(c["count"] for c in checks if c["severity"] == "warning")}


def _overtime_added(ids, start, end):
	comps = [c for c in OVERTIME_COMPONENTS if frappe.db.exists("Salary Component", c)]
	if not comps:
		return set()
	return set(frappe.get_all("Additional Salary", filters={"employee": ["in", ids], "salary_component": ["in", comps],
															"payroll_date": ["between", [start, end]], "docstatus": 1}, pluck="employee"))


def _get_period(company, month, create=True):
	start, _end = _bounds(month)
	name = frappe.db.get_value("AlphaX Payroll Period", {"company": company, "month": start})
	if name:
		return frappe.get_doc("AlphaX Payroll Period", name)
	if not create:
		return None
	doc = frappe.get_doc({"doctype": "AlphaX Payroll Period", "company": company, "month": start, "status": "Open"})
	doc.insert()
	return doc


def _totals(doc):
	start, end = _bounds(doc.month)
	rows = frappe.get_all("Salary Slip", filters={"company": doc.company, "start_date": [">=", start], "end_date": ["<=", end], "docstatus": ["<", 2]},
						  fields=["count(name) as n", "sum(gross_pay) as g", "sum(total_deduction) as d", "sum(net_pay) as net", "max(docstatus) as ds"])
	r = rows[0] if rows else frappe._dict()
	return {"slips": cint(r.n), "gross": flt(r.g, 2), "deductions": flt(r.d, 2), "net": flt(r.net, 2), "submitted": cint(r.ds) == 1}


def _out(doc, with_checklist=True):
	from alphax_hr.api.activity import trail

	out = {k: (str(doc.get(k)) if doc.get(k) is not None and k.endswith(("_on", "month")) else doc.get(k)) for k in
		   ("name", "company", "month", "status", "payroll_entry", "employees", "gross", "deductions", "net", "prepared_by", "prepared_on",
			"reviewed_by", "reviewed_on", "approved_by", "approved_on", "processed_by", "processed_on", "notes")}
	for k in ("prepared_by", "reviewed_by", "approved_by", "processed_by"):
		out[k + "_name"] = frappe.utils.get_fullname(doc.get(k)) if doc.get(k) else None
	out["slips"] = _totals(doc)
	if doc.payroll_entry:
		out["payroll_entry_status"] = frappe.db.get_value("Payroll Entry", doc.payroll_entry, "status")
	if with_checklist:
		out["checklist"] = checklist(doc.company, doc.month)
	out["trail"] = trail("AlphaX Payroll Period", doc.name)["events"] if not doc.is_new() else []
	out["can_approve"] = is_hr_manager()
	return out


@frappe.whitelist()
def companies():
	require_hr()
	return frappe.get_list("Company", pluck="name", order_by="name asc")


@frappe.whitelist()
def period(company, month):
	require_hr()
	frappe.has_permission("Company", "read", company, throw=True)
	return _out(_get_period(company, month))


@frappe.whitelist(methods=["POST"])
def advance(company, month, step, note=None, override=0):
	"""Move the month one step forward (prepare, review, approve, process, close) or back (reopen)."""
	require_hr()
	doc = _get_period(company, month)
	user = frappe.session.user
	if step == "reopen":
		require_hr_manager()
		if doc.status in ("Processed", "Closed"):
			frappe.throw(_("Payroll has already been processed. Cancel the Payroll Entry in ERPNext first."))
		doc.status = "Open"
		for k in ("prepared", "reviewed", "approved"):
			doc.set(k + "_by", None)
			doc.set(k + "_on", None)
		_save(doc, step, note)
		return _out(doc)
	if step not in STEPS:
		frappe.throw(_("Unknown step."))
	before, after = STEPS[step]
	if doc.status != before:
		frappe.throw(_("This month is '{0}'; it must be '{1}' to {2}.").format(_(doc.status), _(before), _(step)))
	cl = checklist(company, month)
	if step in ("prepare", "approve", "process") and cl["blockers"]:
		if not (cint(override) and is_hr_manager() and (note or "").strip()):
			frappe.throw(_("{0} blocking item(s) are still open. Resolve them, or an HR Manager can continue with a note.").format(cl["blockers"]),
						 title=_("Not ready"))
	if step == "review" and doc.prepared_by == user and not is_hr_manager():
		frappe.throw(_("Another person must review the payroll you prepared."))
	if step == "approve":
		require_hr_manager()
	if step == "process":
		_process(doc)
	if step == "close":
		t = _totals(doc)
		if not t["submitted"]:
			frappe.throw(_("Submit the salary slips before closing the month."))
	doc.status = after
	field = {"prepare": "prepared", "review": "reviewed", "approve": "approved", "process": "processed"}.get(step)
	if field:
		doc.set(field + "_by", user)
		doc.set(field + "_on", now_datetime())
	doc.checklist_json = json.dumps({"blockers": cl["blockers"], "warnings": cl["warnings"],
									 "counts": {c["key"]: c["count"] for c in cl["checks"]}})
	if cl["blockers"] and cint(override):
		note = _("Continued with {0} blocking item(s): {1}").format(cl["blockers"], note)
	_save(doc, step, note)
	return _out(doc)


def _save(doc, step, note):
	start, end = _bounds(doc.month)
	doc.employees = len(_active(doc.company, start, end))
	t = _totals(doc)
	doc.gross, doc.deductions, doc.net = t["gross"], t["deductions"], t["net"]
	doc.save()
	if note:
		doc.add_comment("Comment", frappe.utils.escape_html(f"{step}: {note}"[:2000]))


def _process(doc):
	"""Create and submit the HRMS Payroll Entry; HRMS then creates the draft salary slips."""
	start, end = _bounds(doc.month)
	if doc.payroll_entry and frappe.db.get_value("Payroll Entry", doc.payroll_entry, "docstatus") == 1:
		return
	company = frappe.get_cached_doc("Company", doc.company)
	payable = company.get("default_payroll_payable_account")
	if not payable:
		frappe.throw(_("Set a Default Payroll Payable Account on company {0} first.").format(doc.company))
	# Reuse a draft left by an earlier failed attempt, otherwise create the entry.
	draft = frappe.db.get_value("Payroll Entry", {"company": doc.company, "start_date": start, "end_date": end, "docstatus": 0})
	if draft:
		pe = frappe.get_doc("Payroll Entry", draft)
	else:
		pe = frappe.get_doc({"doctype": "Payroll Entry", "company": doc.company, "posting_date": end, "start_date": start, "end_date": end,
							 "payroll_frequency": "Monthly", "currency": company.default_currency, "exchange_rate": 1,
							 "payroll_payable_account": payable, "cost_center": company.cost_center,
							 "payment_account": company.get("default_bank_account")})
		pe.insert()
	pe.fill_employee_details()
	if not pe.employees:
		frappe.throw(_("No employees with a salary structure for this month."))
	pe.save()
	# HRMS rolls the whole transaction back when a salary slip fails; keep the entry so the error is visible.
	frappe.db.commit()  # nosemgrep
	try:
		pe.submit()
	except frappe.DoesNotExistError:
		pass
	state = frappe.db.get_value("Payroll Entry", pe.name, ["docstatus", "status", "error_message"], as_dict=True)
	if not state or state.docstatus != 1 or state.status == "Failed":
		frappe.throw(_("Salary slips could not be created ({0}): {1}").format(
			pe.name, frappe.utils.strip_html(state.error_message or "") if state else _("entry missing")), title=_("Payroll failed"))
	doc.payroll_entry = pe.name


@frappe.whitelist(methods=["POST"])
def submit_slips(company, month):
	"""Submit the draft salary slips of the processed month (HR Manager)."""
	require_hr_manager()
	doc = _get_period(company, month, create=False)
	if not doc or doc.status != "Processed" or not doc.payroll_entry:
		frappe.throw(_("Process the payroll first."))
	pe = frappe.get_doc("Payroll Entry", doc.payroll_entry)
	pe.submit_salary_slips()
	_save(doc, "submit slips", None)
	return _out(doc)


@frappe.whitelist(methods=["POST"])
def add_overtime(company, month):
	"""Add the month's Art. 107 overtime pay to payroll as Additional Salary (once per employee)."""
	require_hr()
	from alphax_hr.api.attendance import overtime

	start, end = _bounds(month)
	comp = next((c for c in OVERTIME_COMPONENTS if frappe.db.exists("Salary Component", c)), None)
	if not comp:
		comp = frappe.get_doc({"doctype": "Salary Component", "salary_component": OVERTIME_COMPONENTS[0], "salary_component_abbr": "OT",
							   "type": "Earning", "depends_on_payment_days": 0}).insert(ignore_permissions=True).name
	data = overtime(str(start), None, company)
	done = _overtime_added([r["employee"] for r in data["rows"]], start, end)
	created, skipped = [], []
	for r in data["rows"]:
		if r["employee"] in done or not r["amount"]:
			skipped.append({"employee": r["employee"], "employee_name": r["employee_name"],
							"reason": _("already added") if r["employee"] in done else r["warning"]})
			continue
		add = frappe.get_doc({"doctype": "Additional Salary", "employee": r["employee"], "company": company, "salary_component": comp,
							  "amount": r["amount"], "payroll_date": end, "overwrite_salary_structure_amount": 0})
		add.flags.ignore_permissions = True
		add.insert()
		add.submit()
		created.append({"employee": r["employee"], "employee_name": r["employee_name"], "hours": r["hours"], "amount": r["amount"],
						"additional_salary": add.name})
	return {"created": created, "skipped": skipped}
