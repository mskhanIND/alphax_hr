"""Employee self-service: everything here is scoped to the signed-in employee."""
from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import add_days, cint, flt, get_first_day, get_last_day, getdate, now_datetime, nowdate

from alphax_hr.api._common import current_employee, has_field
from alphax_hr.saudi import leave as saudi_leave

PROFILE_FIELDS = [
	"name", "employee_name", "first_name", "last_name", "image", "gender", "date_of_birth",
	"date_of_joining", "company", "department", "designation", "branch", "employment_type",
	"reports_to", "cell_number", "personal_email", "company_email", "holiday_list", "default_shift",
	"leave_approver", "expense_approver", "status",
]
SAUDI_FIELDS = ["alphax_is_saudi", "alphax_iqama_number", "alphax_iqama_expiry", "alphax_work_permit_expiry"]
SELF_EDITABLE = {"cell_number", "personal_email", "person_to_be_contacted", "emergency_phone_number",
				 "relation", "current_address", "permanent_address"}


def _employee_doc():
	doc = frappe.get_doc("Employee", current_employee())
	doc.check_permission("read")
	return doc


@frappe.whitelist()
def my_profile():
	doc = _employee_doc()
	data = {f: doc.get(f) for f in PROFILE_FIELDS + SAUDI_FIELDS + sorted(SELF_EDITABLE) if doc.meta.has_field(f) or f == "name"}
	if doc.reports_to:
		data["reports_to_name"] = frappe.db.get_value("Employee", doc.reports_to, "employee_name")
	data["annual_entitlement_days"] = (
		saudi_leave.annual_entitlement(getdate(doc.date_of_joining), getdate(nowdate())) if doc.date_of_joining else None
	)
	data["self_editable"] = sorted(f for f in SELF_EDITABLE if doc.meta.has_field(f))
	return data


@frappe.whitelist()
def update_my_contact(data):
	"""Employees may update their own contact details only."""
	payload = frappe.parse_json(data) if isinstance(data, str) else data
	doc = _employee_doc()
	changes = {k: v for k, v in (payload or {}).items() if k in SELF_EDITABLE and doc.meta.has_field(k)}
	if not changes:
		frappe.throw(_("Nothing to update."))
	doc.update(changes)
	doc.save()  # Employee write permission + HRMS validations still apply
	return my_profile()


# ------------------------------------------------------------------ leave
@frappe.whitelist()
def my_leave_balances(date=None):
	employee = current_employee()
	on = date or nowdate()
	from hrms.hr.doctype.leave_application.leave_application import get_leave_details

	details = get_leave_details(employee, on)
	rows = []
	for leave_type, row in (details.get("leave_allocation") or {}).items():
		rows.append({
			"leave_type": leave_type,
			"allocated": flt(row.get("total_leaves")),
			"taken": flt(row.get("leaves_taken")),
			"pending": flt(row.get("leaves_pending_approval")),
			"expired": flt(row.get("expired_leaves")),
			"balance": flt(row.get("remaining_leaves")),
		})
	return {
		"balances": sorted(rows, key=lambda r: r["leave_type"]),
		"lwps": details.get("lwps") or [],
		"leave_approver": details.get("leave_approver"),
	}


@frappe.whitelist()
def my_leave_applications(limit=30):
	employee = current_employee()
	fields = ["name", "leave_type", "from_date", "to_date", "total_leave_days", "status", "docstatus",
			  "description", "posting_date", "leave_approver_name", "half_day"]
	if has_field("Leave Application", "workflow_state"):
		fields.append("workflow_state")
	return frappe.get_list(
		"Leave Application",
		filters={"employee": employee},
		fields=fields,
		order_by="from_date desc",
		page_length=min(cint(limit) or 30, 100),
	)


@frappe.whitelist()
def leave_types():
	"""Leave types the employee can apply for, with any statutory rule attached.

	Allocated types, leave-without-pay types, and statutory leaves mapped in
	AlphaX HR Settings (those need no allocation; the rule caps them).
	"""
	from alphax_hr.leave_engine import rule_to_dict, rules_by_leave_type

	balances = my_leave_balances()
	rules = rules_by_leave_type()
	gender = frappe.db.get_value("Employee", current_employee(), "gender")
	names = {b["leave_type"] for b in balances["balances"]} | set(balances["lwps"])
	for leave_type, rule in rules.items():
		if (not rule.gender or not gender or rule.gender == gender) and frappe.db.exists("Leave Type", leave_type):
			names.add(leave_type)
	return [{"leave_type": n, "rule": rule_to_dict(rules.get(n))} for n in sorted(names)]


@frappe.whitelist()
def apply_leave(leave_type, from_date, to_date, reason=None, half_day=0, half_day_date=None, event_date=None, relation=None):
	employee = current_employee()
	emp = frappe.db.get_value("Employee", employee, ["company", "holiday_list"], as_dict=True)
	from hrms.hr.doctype.leave_application.leave_application import get_leave_approver

	doc = frappe.new_doc("Leave Application")
	doc.update({
		"employee": employee,
		"company": emp.company,
		"leave_type": leave_type,
		"from_date": from_date,
		"to_date": to_date,
		"half_day": cint(half_day),
		"half_day_date": half_day_date if cint(half_day) else None,
		"description": (reason or "")[:1000],
		"posting_date": nowdate(),
		"leave_approver": get_leave_approver(employee),
		"follow_via_email": 1,
		"alphax_event_date": event_date or None,
		"alphax_relation": relation or None,
	})
	doc.insert()  # permissions + HRMS validation (balance, overlap, holidays ...)
	warnings = []
	if not doc.leave_approver:
		warnings.append(_("No leave approver is set for you. HR has been asked to review this request."))
	if flt(doc.total_leave_days) == 0:
		warnings.append(_("This request counts as 0 working days. Your holiday list may not cover these dates — please check with HR."))
	if doc.get("alphax_sick_breakdown"):
		warnings.append(doc.alphax_sick_breakdown)
	return {"name": doc.name, "total_leave_days": doc.total_leave_days, "status": doc.status, "warnings": warnings}


@frappe.whitelist()
def withdraw_leave(name):
	"""Delete one of my own leave requests that is still a draft and not yet acted on."""
	employee = current_employee()
	doc = frappe.get_doc("Leave Application", name)
	if doc.employee != employee:
		frappe.throw(_("You can only withdraw your own requests."), frappe.PermissionError)
	if doc.docstatus != 0 or doc.status != "Open":
		frappe.throw(_("Only open requests that have not been approved can be withdrawn."))
	if doc.meta.has_field("workflow_state") and doc.get("workflow_state") not in (None, "", "Draft", "Open"):
		frappe.throw(_("This request is already in the approval workflow."))
	frappe.delete_doc("Leave Application", name)  # checks delete permission
	return True


# ------------------------------------------------------------- attendance
@frappe.whitelist()
def my_attendance(month=None):
	employee = current_employee()
	ref = getdate(month or nowdate())
	start, end = get_first_day(ref), get_last_day(ref)
	rows = frappe.get_list(
		"Attendance",
		filters={"employee": employee, "attendance_date": ["between", [start, end]], "docstatus": 1},
		fields=["name", "attendance_date", "status", "shift", "working_hours", "late_entry", "early_exit", "leave_type"],
		order_by="attendance_date asc",
		page_length=62,
	)
	summary = {"Present": 0, "Absent": 0, "On Leave": 0, "Half Day": 0, "Work From Home": 0, "late": 0}
	for r in rows:
		summary[r.status] = summary.get(r.status, 0) + 1
		summary["late"] += 1 if r.late_entry else 0
	return {"month": str(start), "rows": rows, "summary": summary, "today": today_status()}


@frappe.whitelist()
def today_status():
	employee = current_employee()
	today = nowdate()
	logs = frappe.get_list(
		"Employee Checkin",
		filters={"employee": employee, "time": ["between", [today + " 00:00:00", today + " 23:59:59"]]},
		fields=["name", "time", "log_type"],
		order_by="time asc",
		page_length=50,
	)
	last = logs[-1] if logs else None
	return {
		"date": today,
		"logs": logs,
		"next_action": "OUT" if last and last.log_type == "IN" else "IN",
		"shift": frappe.db.get_value("Employee", employee, "default_shift"),
	}


@frappe.whitelist()
def check_in(log_type, latitude=None, longitude=None):
	if log_type not in ("IN", "OUT"):
		frappe.throw(_("Invalid check-in type."))
	employee = current_employee()
	last = frappe.get_list("Employee Checkin", filters={"employee": employee}, fields=["time", "log_type"],
						   order_by="time desc", page_length=1)
	if last and last[0].log_type == log_type and (now_datetime() - last[0].time).total_seconds() < 60:
		frappe.throw(_("You already checked {0} a moment ago.").format(log_type.lower()))
	doc = frappe.new_doc("Employee Checkin")
	doc.employee = employee
	doc.log_type = log_type
	doc.time = now_datetime()
	if latitude and longitude and doc.meta.has_field("latitude"):
		doc.latitude = flt(latitude)
		doc.longitude = flt(longitude)
	doc.insert()  # HRMS geofence/shift validation applies
	return today_status()


# --------------------------------------------------------------- payslips
@frappe.whitelist()
def my_payslips(limit=24):
	employee = current_employee()
	slips = frappe.get_list(
		"Salary Slip",
		filters={"employee": employee, "docstatus": 1},
		fields=["name", "start_date", "end_date", "posting_date", "gross_pay", "total_deduction", "net_pay", "currency"],
		order_by="start_date desc",
		page_length=min(cint(limit) or 24, 60),
	)
	return slips


@frappe.whitelist()
def payslip(name):
	employee = current_employee()
	doc = frappe.get_doc("Salary Slip", name)
	if doc.employee != employee or doc.docstatus != 1:
		frappe.throw(_("Payslip not found."), frappe.DoesNotExistError)
	doc.check_permission("read")
	line = lambda r: {"component": r.salary_component, "abbr": r.abbr, "amount": flt(r.amount)}
	return {
		"name": doc.name, "start_date": doc.start_date, "end_date": doc.end_date, "currency": doc.currency,
		"payment_days": doc.payment_days, "total_working_days": doc.total_working_days,
		"earnings": [line(r) for r in doc.earnings], "deductions": [line(r) for r in doc.deductions],
		"gross_pay": flt(doc.gross_pay), "total_deduction": flt(doc.total_deduction), "net_pay": flt(doc.net_pay),
		"pdf_url": "/api/method/frappe.utils.print_format.download_pdf?doctype=Salary%20Slip&name="
		+ frappe.utils.quote(doc.name),
	}


# --------------------------------------------------------------- expenses
@frappe.whitelist()
def my_expense_claims(limit=20):
	employee = current_employee()
	if not frappe.db.exists("DocType", "Expense Claim"):
		return []
	return frappe.get_list(
		"Expense Claim",
		filters={"employee": employee},
		fields=["name", "posting_date", "total_claimed_amount", "total_sanctioned_amount", "approval_status", "status", "docstatus"],
		order_by="posting_date desc",
		page_length=min(cint(limit) or 20, 100),
	)


@frappe.whitelist()
def upcoming_holidays(days=60):
	employee = current_employee()
	from hrms.hr.utils import get_holiday_list_for_employee

	holiday_list = get_holiday_list_for_employee(employee, raise_exception=False)
	if not holiday_list:
		return {"holiday_list": None, "holidays": []}
	today = nowdate()
	rows = frappe.get_all(  # Holiday rows are not personal data; the list is the employee's own.
		"Holiday",
		filters={"parent": holiday_list, "holiday_date": ["between", [today, add_days(today, cint(days) or 60)]],
				 "weekly_off": 0},
		fields=["holiday_date", "description"],
		order_by="holiday_date asc",
	)
	return {"holiday_list": holiday_list, "holidays": rows}
