"""Payroll control centre: tracked payroll runs per month — the whole company, or one department, branch,
business line, cost center, or chosen employees (one employee = single salary processing).

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


SCOPES = ("Company", "Department", "Branch", "Business line", "Cost center", "Employees")


def business_line_field():
	"""Employee field holding the business line (set in settings, else the first field that looks like one)."""
	from alphax_hr.api._common import settings as _settings

	meta = frappe.get_meta("Employee")
	chosen = (_settings().get("business_line_field") or "").strip()
	if chosen and meta.has_field(chosen):
		return chosen
	for df in meta.fields:
		label = (df.label or "").lower()
		if df.fieldtype in ("Link", "Select", "Data") and (df.fieldname in ("business_line", "alphax_business_line", "division", "business_unit")
																   or any(w in label for w in ("business line", "business unit", "division"))):
			return df.fieldname
	return None


def _scope_ids(value):
	return [x.strip() for x in str(value or "").replace(",", "\n").splitlines() if x.strip()]


def _scope_filters(scope_type, scope_value):
	scope_type = scope_type or "Company"
	if scope_type == "Company":
		return {}
	if scope_type == "Employees":
		return {"name": ["in", _scope_ids(scope_value) or [""]]}
	field = {"Department": "department", "Branch": "branch", "Cost center": "payroll_cost_center",
			 "Business line": business_line_field()}.get(scope_type)
	if not field:
		frappe.throw(_("No business line field on Employee. Set it in HR status & setup → Settings → Salary."))
	return {field: scope_value}


def _active(company, start, end, scope=None):
	"""Employees on the payroll for the month: active, or left during it (within the run's scope)."""
	meta = frappe.get_meta("Employee")
	fields = ["name", "employee_name", "date_of_joining", "relieving_date", "status", "salary_mode", "bank_ac_no"] + [
		f for f in ("iban", "alphax_is_saudi") if meta.has_field(f)]
	filters = {"company": company, "date_of_joining": ["<=", end]}
	if scope is not None:
		filters.update(_scope_filters(scope.get("scope_type"), scope.get("scope_value")))
	return frappe.get_all("Employee", filters=filters, or_filters={"status": "Active", "relieving_date": [">=", start]}, fields=fields)


def _overlap(start, end, a="from_date", b="to_date"):
	return {a: ["<=", end], b: [">=", start]}


def checklist(company, month, scope=None):
	"""Everything payroll depends on for the month (and run scope), with the records behind each number."""
	start, end = _bounds(month)
	emps = _active(company, start, end, scope)
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
			if r.get("employee", r.get("name")) not in by_id:
				continue
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

	# loans and the Saudi deduction limits (Art. 91/92/93)
	if frappe.db.exists("DocType", "AlphaX Loan"):
		from alphax_hr.api import loans

		due = frappe.db.sql("""select l.name, l.employee, l.employee_name, l.loan_type, i.amount, i.status from `tabAlphaX Loan Installment` i
			join `tabAlphaX Loan` l on l.name = i.parent where i.due_month=%s and l.status in ('Disbursed','Repaying')
			and i.status in ('Scheduled','In payroll')""", (start,), as_dict=True)
		due = [d for d in due if d.employee in by_id]
		checks.append(_check("loan_installments", _("Loan and advance installments this month"),
							 [_emp_item(d, f"{_(d.loan_type)} {d.amount} · {_(d.status)}", "AlphaX Loan", d.name) for d in due], "info",
							 _("Scheduled ones are added to payroll automatically when it is processed."), "/payroll/loans"))
		waiting = frappe.get_all("AlphaX Loan", filters={"employee": ["in", ids], "status": "Approved"},
								 fields=["name", "employee", "employee_name", "amount", "loan_type"])
		checks.append(_check("loans_to_pay", _("Approved loans / advances not paid out yet"),
							 [_emp_item(r, f"{_(r.loan_type)} {r.amount}", "AlphaX Loan", r.name) for r in waiting], "warning", None, "/payroll/loans"))
		over = []
		for e in emps:
			try:
				res = loans.check(e.name, start, [])
			except Exception:  # noqa: BLE001 - one broken salary must not hide the checklist
				continue
			if res.problems:
				over.append(_emp_item(e, " ".join(loans.describe(res.problems))))
		checks.append(_check("deduction_limits", _("Deductions above the Saudi Labor Law limits"), over, "blocker",
							 _("Postpone an installment or move a deduction to a later month (Art. 91, 92, 93)."), "/payroll/adjustments"))

	# joiners / leavers
	joiners = [e for e in emps if e.date_of_joining and start <= getdate(e.date_of_joining) <= end]
	leavers = [e for e in emps if e.relieving_date and start <= getdate(e.relieving_date) <= end]
	checks.append(_check("joiners", _("Joined this month (pro-rata pay)"), [_emp_item(e, str(e.date_of_joining)) for e in joiners], "info"))
	settled = set(frappe.get_all("AlphaX Final Settlement", filters={"employee": ["in", [e.name for e in leavers] or [""]],
																	 "status": ["in", ["Approved", "Paid"]]}, pluck="employee")) \
		if frappe.db.exists("DocType", "AlphaX Final Settlement") else set()
	checks.append(_check("leavers", _("Leaving this month without a final settlement"), [_emp_item(e, str(e.relieving_date)) for e in leavers if e.name not in settled],
						 "warning", _("Prepare the end-of-service settlement so it is paid with this payroll or separately."), "/payroll/settlements"))

	# accounting set-up payroll needs
	setup_items = []
	try:
		from erpnext.accounts.utils import get_fiscal_year

		get_fiscal_year(end, company=company)
	except Exception:  # noqa: BLE001 - FiscalYearError and friends
		setup_items.append({"note": _("No active fiscal year covers {0} for this company.").format(frappe.utils.formatdate(end))})
	if not frappe.db.get_value("Company", company, "default_payroll_payable_account"):
		setup_items.append({"note": _("Company has no Default Payroll Payable Account.")})
	checks.append(_check("accounting_setup", _("Accounting set-up for payroll"), setup_items, "blocker",
						 _("Payroll cannot create salary slips until this is fixed in ERPNext.")))

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
	chosen = frappe.get_cached_doc("AlphaX HR Settings").get("overtime_component")
	comps = [c for c in (chosen, *OVERTIME_COMPONENTS) if c and frappe.db.exists("Salary Component", c)]
	if not comps:
		return set()
	return set(frappe.get_all("Additional Salary", filters={"employee": ["in", ids], "salary_component": ["in", comps],
															"payroll_date": ["between", [start, end]], "docstatus": 1}, pluck="employee"))


def _scope(doc):
	return {"scope_type": doc.get("scope_type") or "Company", "scope_value": doc.get("scope_value")}


def _title(scope_type, scope_value):
	if (scope_type or "Company") == "Company":
		return _("Whole company")
	if scope_type == "Employees":
		ids = _scope_ids(scope_value)
		names = [frappe.db.get_value("Employee", i, "employee_name") or i for i in ids[:3]]
		return _("Employees: {0}").format(", ".join(names) + (f" +{len(ids) - 3}" if len(ids) > 3 else ""))
	return f"{_(scope_type)}: {scope_value}"


def _get_period(company, month, create=True, run=None):
	if run:
		doc = frappe.get_doc("AlphaX Payroll Period", run)
		if doc.company != company or getdate(doc.month) != _bounds(month)[0]:
			frappe.throw(_("This payroll run belongs to another company or month."))
		return doc
	start, _end = _bounds(month)
	name = frappe.db.get_value("AlphaX Payroll Period", {"company": company, "month": start, "scope_type": ["in", ["Company", "", None]]})
	if name:
		return frappe.get_doc("AlphaX Payroll Period", name)
	if not create:
		return None
	if frappe.db.exists("AlphaX Payroll Period", {"company": company, "month": start}):
		return None  # the month runs by group; open one of the runs
	doc = frappe.get_doc({"doctype": "AlphaX Payroll Period", "company": company, "month": start, "status": "Open",
						  "scope_type": "Company", "title": _title("Company", None)})
	doc.insert()
	return doc


def _run_ids(doc):
	start, end = _bounds(doc.month)
	return {e.name for e in _active(doc.company, start, end, _scope(doc))}


@frappe.whitelist()
def scope_options(company: str):
	"""Values HR can run payroll for: departments, branches, business lines, cost centers."""
	require_hr()
	field = business_line_field()
	lines = []
	if field:
		lines = sorted({v for v in frappe.get_all("Employee", filters={"company": company, "status": "Active", field: ["is", "set"]},
													   pluck=field) if v})
	return {"Department": frappe.get_all("Department", filters={"company": ["in", [company, "", None]], "is_group": 0}, pluck="name", order_by="name"),
			"Branch": frappe.get_all("Branch", pluck="name", order_by="name"),
			"Business line": lines, "business_line_field": field,
			"Cost center": frappe.get_all("Cost Center", filters={"company": company, "is_group": 0, "disabled": 0}, pluck="name", order_by="name")}


@frappe.whitelist()
def runs(company: str, month: str):
	"""Payroll runs of the month for the company."""
	require_hr()
	start, end = _bounds(month)
	out = []
	for r in frappe.get_all("AlphaX Payroll Period", filters={"company": company, "month": start},
							fields=["name", "title", "scope_type", "scope_value", "status", "employees", "gross", "net", "payroll_entry"],
							order_by="creation asc"):
		r.scope_type = r.scope_type or "Company"
		r.title = r.title or _title(r.scope_type, r.scope_value)
		out.append(r)
	return {"runs": out, "whole_company": any(r.scope_type == "Company" for r in out)}


@frappe.whitelist(methods=["POST"])
def create_run(company: str, month: str, scope_type: str, scope_value: str | None = None):
	"""Open a payroll run for part of the company. An employee can be in only one run per month."""
	require_hr()
	if scope_type not in SCOPES:
		frappe.throw(_("Unknown payroll scope."))
	if scope_type == "Employees":
		scope_value = "\n".join(dict.fromkeys(_scope_ids(scope_value)))
	if scope_type != "Company" and not (scope_value or "").strip():
		frappe.throw(_("Choose what to run payroll for."))
	start, end = _bounds(month)
	scope = {"scope_type": scope_type, "scope_value": scope_value}
	ids = {e.name for e in _active(company, start, end, scope)}
	if not ids:
		frappe.throw(_("No employees on the payroll for this choice."))
	clashes = []
	for other in frappe.get_all("AlphaX Payroll Period", filters={"company": company, "month": start},
								fields=["name", "title", "scope_type", "scope_value"]):
		taken = ids & {e.name for e in _active(company, start, end, _scope(other))}
		if taken:
			clashes.append(_("{0} employee(s) already in run '{1}'").format(len(taken), other.title or _title(other.scope_type, other.scope_value)))
	if clashes:
		frappe.throw("<br>".join(clashes), title=_("Already in another payroll run"))
	doc = frappe.get_doc({"doctype": "AlphaX Payroll Period", "company": company, "month": start, "status": "Open",
						  "scope_type": scope_type, "scope_value": scope_value, "title": _title(scope_type, scope_value),
						  "employees": len(ids)})
	doc.insert()
	return _out(doc)


@frappe.whitelist(methods=["POST"])
def delete_run(name: str):
	"""Remove a run that has not been processed yet."""
	require_hr_manager()
	doc = frappe.get_doc("AlphaX Payroll Period", name)
	if doc.status in ("Processed", "Closed") or doc.payroll_entry:
		frappe.throw(_("A processed run cannot be removed. Cancel its Payroll Entry in ERPNext first."))
	frappe.delete_doc("AlphaX Payroll Period", name, ignore_permissions=True)  # HR Manager checked above
	return {"ok": True}


def _gosi_components():
	from alphax_hr.api._common import settings as _settings

	comps = {c for c in [_settings().get("salary_gosi_component")] if c}
	comps |= set(frappe.get_all("Salary Component", filters={"salary_component": ["like", "%GOSI%"], "type": "Deduction"}, pluck="name"))
	return comps


def _slip_fields(*names):
	meta = frappe.get_meta("Salary Slip")
	return [n for n in names if n in ("name", "docstatus", "modified") or meta.has_field(n)]


def _slip_filters(company, month, ids=None):
	start, end = _bounds(month)
	out = {"company": company, "start_date": [">=", start], "end_date": ["<=", end], "docstatus": ["<", 2]}
	if ids is not None:
		out["employee"] = ["in", list(ids) or [""]]
	return out


def _doc_ids(doc):
	return None if (doc.get("scope_type") or "Company") == "Company" else _run_ids(doc)


def _totals(doc):
	rows = frappe.get_all("Salary Slip", filters=_slip_filters(doc.company, doc.month, _doc_ids(doc)),
						  fields=_slip_fields("name", "docstatus", "gross_pay", "total_deduction", "net_pay", "total_loan_repayment"))
	names = [r.name for r in rows]
	gosi = penalties = 0.0
	if names:
		comps = _gosi_components()
		for d in frappe.get_all("Salary Detail", filters={"parent": ["in", names], "parenttype": "Salary Slip", "parentfield": "deductions"},
								fields=["salary_component", "amount"]):
			if d.salary_component in comps:
				gosi += flt(d.amount)
			elif any(w in d.salary_component.lower() for w in ("penalt", "disciplin", "violation")):
				penalties += flt(d.amount)
	draft = sum(1 for r in rows if r.docstatus == 0)
	return {"slips": len(rows), "draft": draft, "submitted_count": len(rows) - draft,
			"gross": flt(sum(flt(r.gross_pay) for r in rows), 2), "deductions": flt(sum(flt(r.total_deduction) for r in rows), 2),
			"gosi": flt(gosi, 2), "loans": flt(sum(flt(r.get("total_loan_repayment")) for r in rows), 2), "penalties": flt(penalties, 2),
			"net": flt(sum(flt(r.net_pay) for r in rows), 2), "submitted": bool(rows) and draft == 0}


def _out(doc, with_checklist=True):
	from alphax_hr.api.activity import trail

	out = {k: (str(doc.get(k)) if doc.get(k) is not None and k.endswith(("_on", "month")) else doc.get(k)) for k in
		   ("name", "company", "month", "status", "payroll_entry", "employees", "gross", "deductions", "net", "prepared_by", "prepared_on",
			"scope_type", "scope_value", "title",
			"reviewed_by", "reviewed_on", "approved_by", "approved_on", "processed_by", "processed_on", "notes")}
	for k in ("prepared_by", "reviewed_by", "approved_by", "processed_by"):
		out[k + "_name"] = frappe.utils.get_fullname(doc.get(k)) if doc.get(k) else None
	out["slips"] = _totals(doc)
	if doc.payroll_entry:
		out["payroll_entry_status"] = frappe.db.get_value("Payroll Entry", doc.payroll_entry, "status")
	if with_checklist:
		out["checklist"] = checklist(doc.company, doc.month, _scope(doc))
	out["scope_type"] = doc.get("scope_type") or "Company"
	out["title"] = doc.get("title") or _title(out["scope_type"], doc.get("scope_value"))
	out["trail"] = trail("AlphaX Payroll Period", doc.name)["events"] if not doc.is_new() else []
	out["can_approve"] = is_hr_manager()
	return out


@frappe.whitelist()
def companies():
	require_hr()
	return frappe.get_list("Company", pluck="name", order_by="name asc")


@frappe.whitelist()
def period(company: str, month: str, run: str | None = None):
	require_hr()
	frappe.has_permission("Company", "read", company, throw=True)
	doc = _get_period(company, month, run=run)
	if not doc:
		return None  # the month is run by group: pick a run
	return _out(doc)


def _need(company, month, run, create=True):
	doc = _get_period(company, month, create=create, run=run)
	if not doc:
		frappe.throw(_("Choose the payroll run first."))
	return doc


@frappe.whitelist(methods=["POST"])
def advance(company: str, month: str, step: str, note: str | None = None, override: int | str = 0, run: str | None = None):
	"""Move the run one step forward (prepare, review, approve, process, close) or back (reopen)."""
	require_hr()
	doc = _need(company, month, run)
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
	cl = checklist(company, month, _scope(doc))
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
	doc.employees = len(_active(doc.company, start, end, _scope(doc)))
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
	scope_type = doc.get("scope_type") or "Company"
	if frappe.db.exists("DocType", "AlphaX Loan"):
		from alphax_hr.api import loans

		loans.post_due(start, doc.company)  # this month's installments go into the slips
	# Reuse this run's draft left by an earlier failed attempt, otherwise create the entry.
	draft = doc.payroll_entry if doc.payroll_entry and frappe.db.get_value("Payroll Entry", doc.payroll_entry, "docstatus") == 0 else None
	if not draft and scope_type == "Company":
		draft = frappe.db.get_value("Payroll Entry", {"company": doc.company, "start_date": start, "end_date": end, "docstatus": 0})
	if draft:
		pe = frappe.get_doc("Payroll Entry", draft)
	else:
		values = {"doctype": "Payroll Entry", "company": doc.company, "posting_date": end, "start_date": start, "end_date": end,
				  "payroll_frequency": "Monthly", "currency": company.default_currency, "exchange_rate": 1,
				  "payroll_payable_account": payable, "cost_center": company.cost_center,
				  "payment_account": company.get("default_bank_account")}
		if scope_type == "Department":
			values["department"] = doc.scope_value
		elif scope_type == "Branch":
			values["branch"] = doc.scope_value
		elif scope_type == "Cost center":
			values["cost_center"] = doc.scope_value  # salary expense is booked to this cost center
		pe = frappe.get_doc(values)
		pe.insert()
	pe.fill_employee_details()
	if scope_type != "Company":
		ids = _run_ids(doc)
		keep = [r for r in pe.employees if r.employee in ids]
		pe.set("employees", [])
		for r in keep:
			pe.append("employees", {k: r.get(k) for k in ("employee", "employee_name", "department", "designation", "is_salary_withheld")
									if r.get(k) is not None})
		pe.number_of_employees = len(pe.employees)
	if not pe.employees:
		frappe.throw(_("No employees with a salary structure in this run for this month."))
	pe.save()
	doc.payroll_entry = pe.name
	doc.db_set("payroll_entry", pe.name, update_modified=False)
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
def submit_slips(company: str, month: str, run: str | None = None):
	"""Submit the draft salary slips of the processed run (HR Manager)."""
	require_hr_manager()
	doc = _get_period(company, month, create=False, run=run)
	if not doc or doc.status != "Processed" or not doc.payroll_entry:
		frappe.throw(_("Process the payroll first."))
	pe = frappe.get_doc("Payroll Entry", doc.payroll_entry)
	pe.submit_salary_slips()
	_save(doc, "submit slips", None)
	return _out(doc)


@frappe.whitelist(methods=["POST"])
def add_overtime(company: str, month: str, run: str | None = None):
	"""Add the month's Art. 107 overtime pay to payroll as Additional Salary (once per employee, within the run)."""
	require_hr()
	doc = _get_period(company, month, create=False, run=run) if run else None
	only = _doc_ids(doc) if doc else None
	from alphax_hr.api.attendance import overtime

	start, end = _bounds(month)
	from alphax_hr.api import components

	comp = components.get("overtime")
	data = overtime(str(start), None, company)
	done = _overtime_added([r["employee"] for r in data["rows"]], start, end)
	created, skipped = [], []
	for r in data["rows"]:
		if only is not None and r["employee"] not in only:
			continue
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



# ------------------------------------------------------------------ per-employee corrections
def _period_for_slip(slip):
	if slip.get("payroll_entry"):
		hit = frappe.db.get_value("AlphaX Payroll Period", {"payroll_entry": slip.payroll_entry}, ["name", "status"], as_dict=True)
		if hit:
			return hit
	start, _end = _bounds(slip.start_date)
	return frappe.db.get_value("AlphaX Payroll Period", {"company": slip.company, "month": start, "scope_type": ["in", ["Company", "", None]]},
							   ["name", "status"], as_dict=True)


def _guard_open(slip):
	per = _period_for_slip(slip)
	if per and per.status == "Closed":
		frappe.throw(_("This month is closed. Correct it in next month's payroll."))


@frappe.whitelist()
def slips(company: str, month: str, run: str | None = None):
	"""Every salary slip of the run with the figures HR checks before submitting."""
	require_hr()
	doc = _get_period(company, month, create=False, run=run)
	ids = _doc_ids(doc) if doc else None
	rows = frappe.get_all("Salary Slip", filters=_slip_filters(company, month, ids),
						  fields=_slip_fields("name", "employee", "employee_name", "department", "docstatus", "status", "gross_pay",
											  "total_deduction", "net_pay", "payment_days", "total_working_days", "absent_days", "leave_without_pay",
											  "total_loan_repayment", "journal_entry", "payroll_entry", "modified"), order_by="employee_name asc")
	comps = _gosi_components()
	gosi = {}
	if rows:
		for d in frappe.get_all("Salary Detail", filters={"parent": ["in", [r.name for r in rows]], "parenttype": "Salary Slip",
														   "parentfield": "deductions", "salary_component": ["in", list(comps) or [""]]},
								fields=["parent", "amount"]):
			gosi[d.parent] = gosi.get(d.parent, 0) + flt(d.amount)
	start, end = _bounds(month)
	with_slip = {r.employee for r in rows}
	missing = [e for e in _active(company, start, end, _scope(doc) if doc else None) if e.name not in with_slip and frappe.db.exists(
		"Salary Structure Assignment", {"employee": e.name, "docstatus": 1, "from_date": ["<=", end]})]
	return {"rows": [{**r, "gosi": flt(gosi.get(r.name), 2), "modified": str(r.modified),
					  "total_loan_repayment": flt(r.get("total_loan_repayment")),
					  "can_redo": r.docstatus == 1 and not r.get("journal_entry")} for r in rows],
			"missing": [{"employee": e.name, "employee_name": e.employee_name} for e in missing]}


@frappe.whitelist(methods=["POST"])
def recalculate_slip(name: str):
	"""Re-read attendance, leave, additional salary and the salary structure for one draft slip."""
	require_hr()
	slip = frappe.get_doc("Salary Slip", name)
	if slip.docstatus != 0:
		frappe.throw(_("Only draft slips can be recalculated. Use 'Redo' for a submitted slip."))
	_guard_open(slip)
	slip.set("earnings", [])
	slip.set("deductions", [])
	slip.flags.ignore_permissions = True
	slip.save()
	slip.add_comment("Comment", _("Recalculated by {0}").format(frappe.session.user))
	return {"name": slip.name, "net_pay": slip.net_pay}


@frappe.whitelist(methods=["POST"])
def remove_slip(name: str, reason: str):
	"""Take one employee out of this run (e.g. on hold); they can be added back later."""
	require_hr_manager()
	if not (reason or "").strip():
		frappe.throw(_("Please give a reason."))
	slip = frappe.get_doc("Salary Slip", name)
	if slip.docstatus != 0:
		frappe.throw(_("Only draft slips can be removed."))
	_guard_open(slip)
	per = _period_for_slip(slip)
	if per:
		frappe.get_doc("AlphaX Payroll Period", per.name).add_comment(
			"Comment", frappe.utils.escape_html(_("Removed {0} ({1}): {2}").format(slip.employee_name, slip.name, reason[:500])))
	frappe.delete_doc("Salary Slip", name, ignore_permissions=True)
	return {"ok": True}


@frappe.whitelist(methods=["POST"])
def add_employee(company: str, month: str, employee: str, run: str | None = None):
	"""Create the slip for an employee missing from the run (e.g. salary assigned after processing)."""
	require_hr()
	doc = _get_period(company, month, create=False, run=run)
	if not doc or not doc.payroll_entry:
		frappe.throw(_("Process the payroll first."))
	if doc.status == "Closed":
		frappe.throw(_("This month is closed."))
	start, end = _bounds(month)
	if frappe.db.exists("Salary Slip", {"employee": employee, "start_date": start, "end_date": end, "docstatus": ["<", 2]}):
		frappe.throw(_("This employee already has a slip for the month."))
	pe = frappe.get_doc("Payroll Entry", doc.payroll_entry)
	slip = frappe.get_doc({"doctype": "Salary Slip", "employee": employee, "company": company, "start_date": start, "end_date": end,
						   "posting_date": pe.posting_date, "payroll_frequency": "Monthly", "payroll_entry": pe.name,
						   "currency": pe.currency, "exchange_rate": pe.exchange_rate})
	slip.flags.ignore_permissions = True
	slip.insert()
	return {"name": slip.name}


@frappe.whitelist(methods=["POST"])
def adjust(company: str, month: str, employee: str, salary_component: str, amount: float | str, when: str = "this", note: str | None = None):
	"""One-off earning or deduction for one employee: in this month's draft slip (recalculated), or in next month's payroll."""
	require_hr()
	amount = flt(amount, 2)
	if amount <= 0:
		frappe.throw(_("The amount must be more than zero."))
	if not frappe.db.exists("Salary Component", salary_component):
		frappe.throw(_("Unknown salary component."))
	if frappe.db.get_value("Salary Component", salary_component, "statistical_component"):
		frappe.throw(_("{0} is an accrual (statistical) component and is never paid. Choose another component.").format(salary_component))
	start, end = _bounds(month)
	payroll_date = end if when == "this" else getdate(frappe.utils.get_last_day(add_days(end, 1)))
	slip = frappe.db.get_value("Salary Slip", {"employee": employee, "start_date": start, "end_date": end, "docstatus": ["<", 2]},
							   ["name", "docstatus"], as_dict=True)
	if when == "this" and slip and slip.docstatus == 1:
		frappe.throw(_("This month's slip is already submitted. Choose 'next month' or redo the slip."))
	add = frappe.get_doc({"doctype": "Additional Salary", "employee": employee, "company": company, "salary_component": salary_component,
						  "amount": amount, "payroll_date": payroll_date, "overwrite_salary_structure_amount": 0})
	add.flags.ignore_permissions = True
	add.insert()
	add.submit()
	if note:
		add.add_comment("Comment", frappe.utils.escape_html(str(note)[:1000]))
	if when == "this" and slip:
		recalculate_slip(slip.name)
	return {"additional_salary": add.name, "payroll_date": str(payroll_date)}


@frappe.whitelist(methods=["POST"])
def redo_slip(name: str, reason: str):
	"""Cancel one submitted slip and make a corrected draft, as long as its accounting entry is not posted yet."""
	require_hr_manager()
	if not (reason or "").strip():
		frappe.throw(_("Please give a reason."))
	slip = frappe.get_doc("Salary Slip", name)
	if slip.docstatus != 1:
		frappe.throw(_("Only submitted slips can be redone."))
	_guard_open(slip)
	if slip.get("journal_entry") and frappe.db.get_value("Journal Entry", slip.journal_entry, "docstatus") == 1:
		frappe.throw(_("The payroll accounting entry {0} is already posted. Correct this employee in next month's payroll instead.").format(
			slip.journal_entry))
	slip.flags.ignore_permissions = True
	slip.cancel()
	new = frappe.copy_doc(slip)
	new.amended_from = slip.name
	new.set("earnings", [])
	new.set("deductions", [])
	new.flags.ignore_permissions = True
	new.insert()
	new.add_comment("Comment", frappe.utils.escape_html(_("Redone from {0}: {1}").format(slip.name, reason[:500])))
	return {"name": new.name}


@frappe.whitelist()
def components():
	require_hr()
	filters = {"statistical_component": 0}
	if frappe.get_meta("Salary Component").has_field("disabled"):
		filters["disabled"] = 0
	return frappe.get_all("Salary Component", filters=filters, fields=["name", "type"], order_by="type asc, name asc")


# ------------------------------------------------------------------ bank / WPS salary file
@frappe.whitelist()
def salary_file(company: str, month: str, run: str | None = None, submitted_only: int | str = 1):
	"""Excel salary transfer file for the bank / Mudad (Wage Protection System) from the run's salary slips.

	Columns follow the common WPS layout (ID number, name, bank, IBAN, basic, housing, other earnings, deductions, net).
	Check the column order against your bank's or Mudad's current template before uploading."""
	require_hr()
	from frappe.utils.xlsxutils import make_xlsx

	from alphax_hr.api import components
	from alphax_hr.api.banks import name_for_iban

	doc = _get_period(company, month, create=False, run=run)
	ids = _doc_ids(doc) if doc else None
	filters = _slip_filters(company, month, ids)
	if cint(submitted_only):
		filters["docstatus"] = 1
	slips = frappe.get_all("Salary Slip", filters=filters, fields=["name", "employee", "employee_name", "gross_pay", "total_deduction", "net_pay"],
						   order_by="employee_name asc")
	if not slips:
		frappe.throw(_("No submitted salary slips for this run yet."))
	basic, housing = components.get("basic"), components.get("housing")
	details = frappe.get_all("Salary Detail", filters={"parent": ["in", [s.name for s in slips]], "parenttype": "Salary Slip",
													   "parentfield": "earnings"}, fields=["parent", "salary_component", "amount"])
	parts = {}
	for d in details:
		p = parts.setdefault(d.parent, {"basic": 0.0, "housing": 0.0})
		if d.salary_component == basic:
			p["basic"] += flt(d.amount)
		elif d.salary_component == housing:
			p["housing"] += flt(d.amount)
	meta = frappe.get_meta("Employee")
	fields = ["name", "iban", "bank_name", "bank_ac_no", "alphax_iqama_number"]
	emps = {e.name: e for e in frappe.get_all("Employee", filters={"name": ["in", [s.employee for s in slips]]},
											  fields=[f for f in fields if f == "name" or meta.has_field(f)])}
	bank_meta = frappe.get_meta("Bank")
	rows = [["Employee ID", "ID / Iqama number", "Employee name", "Bank", "SWIFT", "IBAN", "Basic salary", "Housing allowance",
			 "Other earnings", "Deductions", "Net salary", "Reference"]]
	missing = 0
	for s in slips:
		e = emps.get(s.employee) or frappe._dict()
		iban = (e.get("iban") or e.get("bank_ac_no") or "").replace(" ", "")
		bank = e.get("bank_name") or name_for_iban(iban) or ""
		swift = frappe.db.get_value("Bank", bank, "swift_number") if bank and bank_meta.has_field("swift_number") and frappe.db.exists("Bank", bank) else ""
		p = parts.get(s.name, {"basic": 0.0, "housing": 0.0})
		other = flt(s.gross_pay) - p["basic"] - p["housing"]
		if not iban:
			missing += 1
		rows.append([s.employee, e.get("alphax_iqama_number") or "", s.employee_name, bank, swift or "", iban, flt(p["basic"], 2),
					 flt(p["housing"], 2), flt(other, 2), flt(s.total_deduction, 2), flt(s.net_pay, 2), s.name])
	start, _end = _bounds(month)
	rows.append([])
	rows.append(["Total", "", f"{len(slips)} employees", "", "", f"{missing} without IBAN" if missing else "",
				 flt(sum(r[6] for r in rows[1:-1]), 2), flt(sum(r[7] for r in rows[1:-1]), 2), flt(sum(r[8] for r in rows[1:-1]), 2),
				 flt(sum(r[9] for r in rows[1:-1]), 2), flt(sum(r[10] for r in rows[1:-1]), 2), ""])
	frappe.response["filecontent"] = make_xlsx(rows, "Salary file").getvalue()
	frappe.response["filename"] = f"salary-file-{company}-{start.strftime('%Y-%m')}.xlsx".replace(" ", "-")
	frappe.response["type"] = "binary"
