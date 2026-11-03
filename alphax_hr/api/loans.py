"""Employee loans and salary advances, paid by cash or bank transfer and recovered through payroll.

Accounting stays in ERPNext/HRMS: the money is an HRMS Employee Advance paid with a Journal Entry; every monthly
installment is an Additional Salary deduction that references the advance, so the payroll accounting entry credits
the employee's advance account. AlphaX keeps the schedule and enforces the Saudi Labor Law limits
(Art. 92: 10% of the wage without written consent; Art. 93: at most half the wage deducted in a month).
"""
from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import add_days, cint, flt, get_first_day, get_last_day, getdate, nowdate

from alphax_hr.api._common import current_employee, login_required, parse_json, require_hr, require_hr_manager, settings
from alphax_hr.saudi import deductions as rules

DT = "AlphaX Loan"
OPEN_ROWS = ("Scheduled", "In payroll")
COMPONENTS = {"loan_component": ("Loan Repayment", "LR", "Deduction"), "bonus_component": ("Bonus", "BON", "Earning"),
			  "hr_deduction_component": ("HR Deduction", "HRD", "Deduction")}


# ------------------------------------------------------------------ helpers shared with pay adjustments
def component(key):
	"""Salary component chosen in settings, or AlphaX's default one (created once)."""
	chosen = settings().get(key)
	if chosen and frappe.db.exists("Salary Component", chosen):
		return chosen
	name, abbr, kind = COMPONENTS[key]
	if not frappe.db.exists("Salary Component", name):
		frappe.get_doc({"doctype": "Salary Component", "salary_component": name, "salary_component_abbr": abbr, "type": kind,
						"depends_on_payment_days": 0}).insert(ignore_permissions=True)
	return name


def monthly_wage(employee):
	"""Actual monthly wage (Art. 2): the latest submitted slip's gross, else the current salary structure."""
	slip = frappe.get_all("Salary Slip", filters={"employee": employee, "docstatus": 1}, fields=["gross_pay"],
						  order_by="end_date desc", limit=1)
	if slip and flt(slip[0].gross_pay):
		return flt(slip[0].gross_pay, 2)
	ssa = frappe.get_all("Salary Structure Assignment", filters={"employee": employee, "docstatus": 1, "from_date": ["<=", nowdate()]},
						 fields=["salary_structure", "base"], order_by="from_date desc", limit=1)
	if not ssa:
		return 0.0
	earn = frappe.get_all("Salary Detail", filters={"parent": ssa[0].salary_structure, "parenttype": "Salary Structure",
													"parentfield": "earnings"}, pluck="amount")
	return flt(sum(flt(a) for a in earn) or ssa[0].base, 2)


def _month(d):
	return getdate(get_first_day(getdate(d)))


def _gosi_monthly(employee):
	from alphax_hr.api.payroll_control import _gosi_components

	ssa = frappe.get_all("Salary Structure Assignment", filters={"employee": employee, "docstatus": 1}, fields=["salary_structure"],
						 order_by="from_date desc", limit=1)
	if not ssa:
		return 0.0
	comps = _gosi_components()
	rows = frappe.get_all("Salary Detail", filters={"parent": ssa[0].salary_structure, "parenttype": "Salary Structure",
													"parentfield": "deductions"}, fields=["salary_component", "amount"])
	return flt(sum(flt(r.amount) for r in rows if r.salary_component in comps), 2)


ADJ_KIND = {"Damage or loss (Art. 91)": rules.DAMAGE, "Court order (Art. 92)": rules.COURT,
			"Deduction with written consent (Art. 92)": rules.CONSENT, "Other recovery": rules.CONSENT}


def month_items(employee, month, skip_loan=None, skip_adjustment=None):
	"""Every deduction already planned for the employee in a month, as (kind, amount)."""
	month = _month(month)
	end = getdate(get_last_day(month))
	items = []
	rows = frappe.db.sql("""select l.name, l.loan_type, i.amount from `tabAlphaX Loan Installment` i
		join `tabAlphaX Loan` l on l.name = i.parent where l.employee=%s and l.status in ('Approved','Disbursed','Repaying')
		and i.due_month=%s and i.status in ('Scheduled','In payroll','Deducted')""", (employee, month), as_dict=True)
	for r in rows:
		if r.name != skip_loan:
			items.append((rules.ADVANCE if r.loan_type == "Salary advance" else rules.LOAN, flt(r.amount)))
	if frappe.db.exists("DocType", "AlphaX Pay Adjustment"):
		for a in frappe.get_all("AlphaX Pay Adjustment", filters={"employee": employee, "kind": "Deduction", "status": "Posted",
																  "name": ["!=", skip_adjustment or ""]},
								fields=["category", "additional_salaries"]):
			for line in parse_json(a.additional_salaries, []) or []:
				if _month(line["month"]) == month:
					items.append((ADJ_KIND.get(a.category, rules.CONSENT), flt(line["amount"])))
	if frappe.db.exists("DocType", "AlphaX Penalty"):
		for p in frappe.get_all("AlphaX Penalty", filters={"employee": employee, "status": ["in", ["Issued", "Acknowledged", "Objected"]],
														   "payroll_date": ["between", [month, end]], "amount": [">", 0]}, pluck="amount"):
			items.append((rules.FINE, flt(p)))
	gosi = _gosi_monthly(employee)
	if gosi:
		items.append((rules.STATUTORY, gosi))
	return items


PROBLEM_TEXT = {
	"loan_over_10": _("Loan installments of {amount:,.2f} are above 10% of the wage ({cap:,.2f}) without the employee's written consent (Art. 92)."),
	"damage_over_5_days": _("Damage deductions of {amount:,.2f} are above five days' wage ({cap:,.2f}) in one month (Art. 91)."),
	"fines_over_5_days": _("Penalties of {amount:,.2f} are above five days' wage ({cap:,.2f}) in one month."),
	"court_over_quarter": _("Court-ordered deductions of {amount:,.2f} are above a quarter of the wage ({cap:,.2f}) (Art. 92)."),
	"over_half_wage": _("Total deductions of {amount:,.2f} are above half the wage ({cap:,.2f}) (Art. 93)."),
	"no_wage": _("The employee has no salary to deduct from."),
}


def describe(problems):
	return [PROBLEM_TEXT[c].format(**p) for c, p in problems]


def check(employee, month, extra, consent=False, skip_loan=None, skip_adjustment=None, wage=None):
	wage = monthly_wage(employee) if wage is None else wage
	items = month_items(employee, month, skip_loan, skip_adjustment) + list(extra)
	gosi_counts = settings().get("cap_includes_gosi")
	return rules.check_month(wage, items, consent_for_loans=consent, include_statutory=gosi_counts is None or bool(cint(gosi_counts)))


# ------------------------------------------------------------------ schedule and validation
def _schedule(amount, months, first_month):
	return [{"due_month": r["due_month"], "amount": r["amount"], "status": "Scheduled"}
			for r in rules.plan_installments(flt(amount), cint(months), _month(first_month))]


def _validate_terms(employee, loan_type, amount, months, first_month, consent, skip_loan=None):
	amount, months = flt(amount, 2), cint(months) or 1
	if amount <= 0:
		frappe.throw(_("The amount must be more than zero."))
	conf = settings()
	wage = monthly_wage(employee)
	if not wage:
		frappe.throw(_("This employee has no salary yet, so nothing can be recovered from payroll."))
	if loan_type == "Salary advance":
		pct = flt(conf.get("advance_max_percent") or 50)
		if amount > wage * pct / 100 + 0.005:
			frappe.throw(_("A salary advance can be at most {0}% of the monthly wage ({1:,.2f}).").format(pct, wage * pct / 100))
	else:
		max_months = cint(conf.get("loan_max_months") or 24)
		if months > max_months:
			frappe.throw(_("A loan can be repaid over at most {0} months.").format(max_months))
		max_wages = flt(conf.get("loan_max_wages"))
		if max_wages and amount > wage * max_wages + 0.005:
			frappe.throw(_("A loan can be at most {0:g} months of wage ({1:,.2f}).").format(max_wages, wage * max_wages))
	schedule = _schedule(amount, months, first_month)
	kind = rules.ADVANCE if loan_type == "Salary advance" else rules.LOAN
	problems = []
	for row in schedule:
		res = check(employee, row["due_month"], [(kind, row["amount"])], consent=bool(cint(consent)), skip_loan=skip_loan, wage=wage)
		for p in describe(res.problems):
			problems.append(f"{frappe.utils.formatdate(row['due_month'], 'MMM yyyy')}: {p}")
	return {"wage": wage, "loan_cap": rules.loan_cap(wage), "half_wage": rules.total_cap(wage),
			"min_months": rules.min_months_for_cap(amount, wage) if loan_type != "Salary advance" else 1,
			"schedule": [{**r, "due_month": str(r["due_month"])} for r in schedule], "problems": problems}


@frappe.whitelist()
def preview(employee, loan_type="Loan", amount=0, installments=1, first_month=None, consent=0):
	require_hr()
	return _validate_terms(employee, loan_type, amount, installments, first_month or _next_month(), consent)


def _next_month():
	return _month(add_days(get_last_day(nowdate()), 1))


def _create(employee, loan_type, amount, installments, first_month, purpose=None, consent=0, consent_file=None, request=None, notes=None):
	terms = _validate_terms(employee, loan_type, amount, installments, first_month, consent)
	if terms["problems"]:
		frappe.throw("<br>".join(terms["problems"]), title=_("Saudi Labor Law limits"))
	doc = frappe.get_doc({"doctype": DT, "employee": employee, "loan_type": loan_type, "amount": flt(amount, 2),
						  "installments": cint(installments) or 1, "first_month": _month(first_month), "purpose": purpose,
						  "consent": cint(consent), "consent_file": consent_file, "request": request, "notes": notes,
						  "monthly_wage": terms["wage"], "status": "Approved",
						  "schedule": [{"due_month": r["due_month"], "amount": r["amount"], "status": "Scheduled"} for r in terms["schedule"]]})
	_totals(doc)
	doc.insert(ignore_permissions=True)
	return doc


@frappe.whitelist(methods=["POST"])
def create(data):
	"""HR records an approved loan or salary advance (requests from employees arrive here automatically)."""
	require_hr()
	d = parse_json(data) or {}
	doc = _create(d.get("employee"), d.get("loan_type") or "Loan", d.get("amount"), d.get("installments") or 1,
				  d.get("first_month") or _next_month(), d.get("purpose"), d.get("consent"), d.get("consent_file"), notes=d.get("notes"))
	return detail(doc.name)


def _request_terms(req):
	details = parse_json(req.details, {}) or {}
	return details, flt(details.get("amount")), cint(details.get("months")) or 1, details.get("first_month") or _next_month()


def check_request(req, loan_type):
	"""Refuse the approval when the requested loan breaks a limit (so the request stays where it was)."""
	_details, amount, months, first = _request_terms(req)
	terms = _validate_terms(req.employee, loan_type, amount, months, first, 0)
	if terms["problems"]:
		frappe.throw("<br>".join(terms["problems"] + [_("Fewest months within 10% of the wage: {0}").format(terms["min_months"])]),
					 title=_("Saudi Labor Law limits"))


def from_request(req, loan_type):
	"""Called when a loan / salary advance request is approved."""
	details, amount, months, first = _request_terms(req)
	doc = _create(req.employee, loan_type, amount, months, first, details.get("purpose") or req.reason, request=req.name)
	req.hr_note = _("{0} {1} created; HR pays it by cash or bank transfer.").format(_(loan_type), doc.name)
	return doc


# ------------------------------------------------------------------ status
def _slip_submitted(employee, month):
	return bool(frappe.db.exists("Salary Slip", {"employee": employee, "start_date": [">=", month],
												 "end_date": ["<=", get_last_day(month)], "docstatus": 1}))


def _totals(doc):
	for r in doc.schedule:
		if r.status == "In payroll" and _slip_submitted(doc.employee, r.due_month):
			r.status = "Deducted"
	repaid = sum(flt(r.amount) for r in doc.schedule if r.status in ("Deducted", "Settled") and not (r.note or "").startswith("~"))
	doc.repaid = flt(repaid, 2)
	doc.outstanding = flt(flt(doc.amount) - repaid, 2) if doc.status != "Cancelled" else 0
	live = [r for r in doc.schedule if r.status in OPEN_ROWS]
	doc.installment_amount = flt(doc.schedule[0].amount) if doc.schedule else 0
	if doc.status in ("Disbursed", "Repaying"):
		if doc.outstanding <= 0.005 and not live:
			doc.status = "Settled"
			doc.settled_on = doc.settled_on or getdate(nowdate())
		elif any(r.status in ("In payroll", "Deducted") for r in doc.schedule):
			doc.status = "Repaying"


def _out(doc):
	return {**{k: doc.get(k) for k in ("name", "employee", "employee_name", "company", "loan_type", "purpose", "status", "amount",
									   "installments", "installment_amount", "monthly_wage", "consent", "consent_file", "paid_by",
									   "payment_account", "employee_advance", "payment_entry", "repaid", "outstanding",
									   "settlement_entry", "request", "notes")},
			"first_month": str(doc.first_month), "disbursed_on": str(doc.disbursed_on) if doc.disbursed_on else None,
			"settled_on": str(doc.settled_on) if doc.settled_on else None,
			"schedule": [{"name": r.name, "due_month": str(r.due_month), "amount": flt(r.amount), "status": r.status,
						  "additional_salary": r.additional_salary, "note": (r.note or "").lstrip("~")} for r in doc.schedule]}


def _save(doc):
	_totals(doc)
	doc.flags.ignore_permissions = True
	doc.save()
	return doc


@frappe.whitelist()
def loans(status=None, employee=None, loan_type=None):
	require_hr()
	filters = {}
	if status:
		filters["status"] = status
	if employee:
		filters["employee"] = employee
	if loan_type:
		filters["loan_type"] = loan_type
	rows = frappe.get_all(DT, filters=filters, fields=["name", "employee", "employee_name", "loan_type", "status", "amount", "installments",
													  "installment_amount", "outstanding", "first_month", "paid_by", "creation"],
						  order_by="creation desc", limit=500)
	for r in rows:
		r.first_month, r.creation = str(r.first_month), str(r.creation)
	summary = {"outstanding": flt(sum(flt(r.outstanding) for r in rows if r.status in ("Disbursed", "Repaying")), 2),
			   "to_pay": sum(1 for r in rows if r.status == "Approved"),
			   "repaying": sum(1 for r in rows if r.status in ("Disbursed", "Repaying"))}
	accounts = frappe.get_all("Account", filters={"account_type": ["in", ["Cash", "Bank"]], "is_group": 0, "disabled": 0},
							  fields=["name", "account_type", "company"], order_by="name")
	return {"rows": rows, "summary": summary, "accounts": accounts}


@frappe.whitelist()
def detail(name):
	user = login_required()
	doc = frappe.get_doc(DT, name)
	from alphax_hr.api._common import is_hr

	if not is_hr(user) and doc.employee != current_employee(required=False):
		raise frappe.PermissionError
	_totals(doc)
	return _out(doc)


@frappe.whitelist()
def mine():
	employee = current_employee()
	out = []
	for name in frappe.get_all(DT, filters={"employee": employee, "status": ["!=", "Cancelled"]}, pluck="name", order_by="creation desc"):
		doc = frappe.get_doc(DT, name)
		_totals(doc)
		out.append(_out(doc))
	return {"loans": out, "wage": monthly_wage(employee), "loan_cap": rules.loan_cap(monthly_wage(employee))}


# ------------------------------------------------------------------ pay out
def _payment_account(company, paid_by, account=None):
	if account:
		if frappe.db.get_value("Account", account, "company") != company:
			frappe.throw(_("The account belongs to another company."))
		return account
	field = "default_cash_account" if paid_by == "Cash" else "default_bank_account"
	acc = frappe.get_cached_value("Company", company, field)
	if acc and paid_by != "Cash" and frappe.db.exists("Bank Account", acc):
		acc = frappe.db.get_value("Bank Account", acc, "account")
	if not acc:
		frappe.throw(_("Choose the {0} account to pay from (no default on the company).").format(_(paid_by).lower()))
	return acc


def _journal(company, posting_date, paid_by, lines, remark, ref):
	je = frappe.new_doc("Journal Entry")
	je.voucher_type = "Cash Entry" if paid_by == "Cash" else "Bank Entry"
	je.company = company
	je.posting_date = posting_date
	je.user_remark = remark
	if paid_by != "Cash":
		je.cheque_no = ref
		je.cheque_date = posting_date
	for line in lines:
		je.append("accounts", line)
	je.flags.ignore_permissions = True
	je.insert()
	je.submit()
	return je.name


@frappe.whitelist(methods=["POST"])
def disburse(name, paid_by, account=None, posting_date=None):
	"""Pay the loan / advance to the employee by cash or bank transfer (HRMS Employee Advance + Journal Entry)."""
	require_hr_manager()
	if paid_by not in ("Cash", "Bank transfer"):
		frappe.throw(_("Choose cash or bank transfer."))
	doc = frappe.get_doc(DT, name)
	if doc.status != "Approved":
		frappe.throw(_("Only an approved loan that has not been paid can be paid out."))
	posting_date = getdate(posting_date or nowdate())
	company = doc.company or frappe.db.get_value("Employee", doc.employee, "company")
	advance_account = frappe.get_cached_value("Company", company, "default_employee_advance_account")
	if not advance_account:
		frappe.throw(_("Set the Default Employee Advance Account on company {0} (ERPNext → Company → Accounts).").format(company))
	pay_account = _payment_account(company, paid_by, account)
	currency = frappe.get_cached_value("Company", company, "default_currency")
	ea = frappe.get_doc({"doctype": "Employee Advance", "employee": doc.employee, "company": company, "posting_date": posting_date,
						 "purpose": f"{_(doc.loan_type)} {doc.name}" + (f": {doc.purpose}" if doc.purpose else ""),
						 "advance_amount": doc.amount, "currency": currency, "exchange_rate": 1, "advance_account": advance_account,
						 "repay_unclaimed_amount_from_salary": 1})
	ea.flags.ignore_permissions = True
	ea.insert()
	ea.submit()
	cost_center = frappe.get_cached_value("Company", company, "cost_center")
	je = _journal(company, posting_date, paid_by, [
		{"account": advance_account, "debit_in_account_currency": doc.amount, "party_type": "Employee", "party": doc.employee,
		 "reference_type": "Employee Advance", "reference_name": ea.name, "is_advance": "Yes", "cost_center": cost_center},
		{"account": pay_account, "credit_in_account_currency": doc.amount, "cost_center": cost_center},
	], _("{0} {1} paid to {2}").format(_(doc.loan_type), doc.name, doc.employee_name), doc.name)
	doc.update({"status": "Disbursed", "paid_by": paid_by, "payment_account": pay_account, "employee_advance": ea.name,
				"payment_entry": je, "disbursed_on": posting_date})
	_save(doc)
	if doc.request and frappe.db.get_value("AlphaX Request", doc.request, "status") == "Approved":
		frappe.db.set_value("AlphaX Request", doc.request, "status", "Completed")
	from alphax_hr.api import alerts

	alerts.event("Request decision", _("{0} paid: {1:,.2f}").format(_(doc.loan_type), doc.amount),
				 _("Paid by {0}. Repayment starts {1}.").format(_(paid_by).lower(), frappe.utils.formatdate(doc.first_month, "MMM yyyy")),
				 employee=doc.employee, url="/alphax/me/loans", doc=(DT, doc.name), tag=doc.name)
	return _out(doc)


# ------------------------------------------------------------------ monthly recovery
def _post_row(doc, row):
	if row.status != "Scheduled" or not doc.employee_advance:
		return False
	month = _month(row.due_month)
	if _slip_submitted(doc.employee, month):
		return False  # that month is paid already; HR postpones it
	add = frappe.get_doc({"doctype": "Additional Salary", "employee": doc.employee, "company": doc.company,
						  "salary_component": component("loan_component"), "amount": flt(row.amount),
						  "payroll_date": getdate(get_last_day(month)), "overwrite_salary_structure_amount": 0,
						  "ref_doctype": "Employee Advance", "ref_docname": doc.employee_advance})
	add.flags.ignore_permissions = True
	add.insert()
	add.submit()
	row.additional_salary = add.name
	row.status = "In payroll"
	return True


@frappe.whitelist(methods=["POST"])
def post_due(month=None, company=None):
	"""Put this month's installments into payroll (also run daily and when payroll is processed)."""
	if frappe.session.user != "Administrator":
		require_hr()
	month = _month(month or nowdate())
	filters = {"status": ["in", ["Disbursed", "Repaying"]]}
	if company:
		filters["company"] = company
	posted = []
	for name in frappe.get_all(DT, filters=filters, pluck="name"):
		doc = frappe.get_doc(DT, name)
		changed = False
		for row in doc.schedule:
			if _month(row.due_month) <= month and row.status == "Scheduled":
				if _month(row.due_month) < month:  # overdue: a month already paid without it -> move to this month
					row.due_month = month
				changed |= _post_row(doc, row)
				if row.status == "In payroll":
					posted.append({"loan": doc.name, "employee_name": doc.employee_name, "amount": flt(row.amount)})
		if changed:
			_save(doc)
	return {"posted": posted, "month": str(month)}


def daily_post_due():
	post_due(nowdate())
	frappe.db.commit()


def _release(doc, row):
	"""Take a posted installment out of payroll (before its slip is submitted)."""
	if row.status != "In payroll":
		return
	if _slip_submitted(doc.employee, _month(row.due_month)):
		frappe.throw(_("The {0} salary is already submitted with this installment.").format(frappe.utils.formatdate(row.due_month, "MMM yyyy")))
	if row.additional_salary and frappe.db.get_value("Additional Salary", row.additional_salary, "docstatus") == 1:
		add = frappe.get_doc("Additional Salary", row.additional_salary)
		add.flags.ignore_permissions = True
		add.cancel()
	row.status = "Scheduled"
	row.additional_salary = None


@frappe.whitelist(methods=["POST"])
def postpone(name, row=None, months=1, reason=None):
	"""Move the next (or a chosen) open installment to the end of the schedule, ``months`` later."""
	require_hr()
	return _postpone(name, row, months, reason)


def _postpone(name, row=None, months=1, reason=None):
	doc = frappe.get_doc(DT, name)
	if doc.status not in ("Approved", "Disbursed", "Repaying"):
		frappe.throw(_("This loan is not being repaid."))
	open_rows = [r for r in doc.schedule if r.status in OPEN_ROWS]
	target = next((r for r in open_rows if r.name == row), None) if row else (open_rows[0] if open_rows else None)
	if not target:
		frappe.throw(_("There is no open installment to postpone."))
	_release(doc, target)
	last = max(_month(r.due_month) for r in doc.schedule if r.status in OPEN_ROWS + ("Deducted",))
	new_month = rules.add_months(last, max(1, cint(months)))
	res = check(doc.employee, new_month, [(rules.ADVANCE if doc.loan_type == "Salary advance" else rules.LOAN, flt(target.amount))],
				consent=bool(doc.consent), skip_loan=None)
	if res.problems:
		frappe.throw("<br>".join(describe(res.problems)), title=_("Saudi Labor Law limits"))
	target.status = "Postponed"
	target.note = (reason or _("Postponed"))[:140]
	doc.append("schedule", {"due_month": new_month, "amount": target.amount, "status": "Scheduled",
							"note": _("Moved from {0}").format(frappe.utils.formatdate(target.due_month, "MMM yyyy"))})
	doc.add_comment("Comment", frappe.utils.escape_html(_("Installment of {0} postponed to {1}: {2}").format(
		frappe.utils.formatdate(target.due_month, "MMM yyyy"), frappe.utils.formatdate(new_month, "MMM yyyy"), reason or "")))
	_save(doc)
	return _out(doc)


@frappe.whitelist(methods=["POST"])
def settle(name, mode, account=None, month=None, consent=0, posting_date=None):
	"""One-time settlement of everything still owed: in one payroll, or paid back by cash / bank transfer."""
	require_hr_manager()
	doc = frappe.get_doc(DT, name)
	if doc.status not in ("Disbursed", "Repaying"):
		frappe.throw(_("Only a paid-out loan can be settled."))
	for r in doc.schedule:
		if r.status == "In payroll" and not _slip_submitted(doc.employee, _month(r.due_month)):
			_release(doc, r)
	_totals(doc)
	owed = flt(doc.outstanding, 2)
	if owed <= 0:
		frappe.throw(_("Nothing is outstanding."))
	if mode == "payroll":
		month = _month(month or nowdate())
		kind = rules.ADVANCE if doc.loan_type == "Salary advance" else rules.LOAN
		res = check(doc.employee, month, [(kind, owed)], consent=bool(cint(consent) or doc.consent), skip_loan=doc.name)
		if res.problems:
			frappe.throw("<br>".join(describe(res.problems)), title=_("Saudi Labor Law limits"))
		for r in doc.schedule:
			if r.status == "Scheduled":
				r.status, r.note = "Cancelled", _("Included in the one-time settlement")
		row = doc.append("schedule", {"due_month": month, "amount": owed, "status": "Scheduled", "note": _("One-time settlement")})
		if not _post_row(doc, row):
			frappe.throw(_("The salary for {0} is already submitted. Choose a later month.").format(frappe.utils.formatdate(month, "MMM yyyy")))
	elif mode in ("Cash", "Bank transfer"):
		posting_date = getdate(posting_date or nowdate())
		advance_account = frappe.db.get_value("Employee Advance", doc.employee_advance, "advance_account")
		pay_account = _payment_account(doc.company, mode, account)
		cost_center = frappe.get_cached_value("Company", doc.company, "cost_center")
		je = _journal(doc.company, posting_date, mode, [
			{"account": pay_account, "debit_in_account_currency": owed, "cost_center": cost_center},
			{"account": advance_account, "credit_in_account_currency": owed, "party_type": "Employee", "party": doc.employee,
			 "reference_type": "Employee Advance", "reference_name": doc.employee_advance, "is_advance": "Yes", "cost_center": cost_center},
		], _("One-time settlement of {0} {1} by {2}").format(_(doc.loan_type), doc.name, doc.employee_name), f"{doc.name}-S")
		for r in doc.schedule:
			if r.status == "Scheduled":
				r.status, r.note = "Cancelled", _("Settled by {0}").format(_(mode).lower())
		doc.append("schedule", {"due_month": _month(posting_date), "amount": owed, "status": "Settled",
								"note": _("Paid back by {0}").format(_(mode).lower())})
		doc.settlement_entry = je
		doc.settled_on = posting_date
	else:
		frappe.throw(_("Choose how the loan is settled."))
	_save(doc)
	return _out(doc)


@frappe.whitelist(methods=["POST"])
def cancel(name, reason=None):
	require_hr_manager()
	doc = frappe.get_doc(DT, name)
	if doc.status != "Approved":
		frappe.throw(_("A loan that has been paid out cannot be cancelled; settle it instead."))
	doc.status = "Cancelled"
	for r in doc.schedule:
		r.status = "Cancelled"
	if reason:
		doc.add_comment("Comment", frappe.utils.escape_html(str(reason)[:500]))
	_save(doc)
	return _out(doc)


def postpone_from_request(req):
	details = parse_json(req.details, {}) or {}
	loan = details.get("loan") or frappe.db.get_value(DT, {"employee": req.employee, "status": ["in", ["Disbursed", "Repaying"]]},
													   "name", order_by="creation desc")
	if not loan or frappe.db.get_value(DT, loan, "employee") != req.employee:
		frappe.throw(_("No loan being repaid was found for this employee."))
	_postpone(loan, months=cint(details.get("months")) or 1, reason=req.reason or _("Requested by the employee"))
	req.hr_note = _("Next installment of {0} postponed.").format(loan)
