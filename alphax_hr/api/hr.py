"""HR core: employee directory, profile, create/update, lookups."""
from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import cint, get_datetime, getdate, nowdate

from alphax_hr.api._common import clamp_page, parse_json, require_hr
from alphax_hr.saudi import documents

LIST_FIELDS = ["name", "employee_name", "image", "department", "designation", "branch", "company",
			   "status", "date_of_joining", "user_id", "alphax_is_saudi"]

SECTIONS = {
	"personal": ["first_name", "middle_name", "last_name", "gender", "date_of_birth", "marital_status",
				 "blood_group", "salutation"],
	"job": ["company", "department", "designation", "branch", "employment_type", "grade", "reports_to",
			"date_of_joining", "final_confirmation_date", "contract_end_date", "notice_number_of_days", "status"],
	"attendance_leave": ["holiday_list", "default_shift", "attendance_device_id", "leave_approver",
						 "expense_approver", "shift_request_approver"],
	"contact": ["cell_number", "personal_email", "company_email", "prefered_contact_email", "user_id",
				"current_address", "permanent_address", "person_to_be_contacted", "emergency_phone_number", "relation"],
	"saudi": ["alphax_is_saudi", "alphax_gosi_registration_date", "alphax_gosi_number", "alphax_iqama_number",
			  "alphax_iqama_expiry", "alphax_border_number", "alphax_work_permit_expiry",
			  "alphax_medical_insurance_expiry", "passport_number", "valid_upto"],
	"exit": ["relieving_date", "reason_for_leaving", "resignation_letter_date"],
}
EDITABLE = {f for fields in SECTIONS.values() for f in fields} - {"status"}
LOOKUP_DOCTYPES = {"Company", "Department", "Designation", "Branch", "Employment Type", "Employee Grade",
				   "Holiday List", "Shift Type", "Gender", "User", "Employee", "Leave Type", "Salary Component"}


def _fields(meta, names):
	return [n for n in names if meta.has_field(n)]


@frappe.whitelist()
def employees(search=None, status="Active", department=None, company=None, saudi=None, start=0, page_length=25):
	require_hr()
	meta = frappe.get_meta("Employee")
	start, page_length = clamp_page(start, page_length)
	filters = {}
	if status in ("Active", "Inactive", "Suspended", "Left"):
		filters["status"] = status
	if department:
		filters["department"] = department
	if company:
		filters["company"] = company
	if saudi in ("0", "1", 0, 1) and meta.has_field("alphax_is_saudi"):
		filters["alphax_is_saudi"] = cint(saudi)
	or_filters = None
	if search:
		term = "%" + str(search)[:80] + "%"
		or_filters = [["employee_name", "like", term], ["name", "like", term]]
		if meta.has_field("alphax_iqama_number"):
			or_filters.append(["alphax_iqama_number", "like", term])
	rows = frappe.get_list("Employee", filters=filters, or_filters=or_filters, fields=_fields(meta, LIST_FIELDS) + ["name"],
						   order_by="employee_name asc", start=start, page_length=page_length)
	total = frappe.get_list("Employee", filters=filters, or_filters=or_filters, fields=["count(name) as n"])[0].n
	return {"rows": rows, "total": total, "start": start, "page_length": page_length}


@frappe.whitelist()
def employee(name):
	require_hr()
	doc = frappe.get_doc("Employee", name)
	doc.check_permission("read")
	doc.apply_fieldlevel_read_permissions()
	meta = doc.meta
	sections = {}
	for key, names in SECTIONS.items():
		sections[key] = {f: doc.get(f) for f in _fields(meta, names)}
	labels = {f: _(meta.get_label(f)) for names in SECTIONS.values() for f in _fields(meta, names)}
	today = getdate(nowdate())
	docs = {
		"iqama": documents.bucket(getdate(doc.get("alphax_iqama_expiry")) if doc.get("alphax_iqama_expiry") else None, today),
		"passport": documents.bucket(getdate(doc.valid_upto) if doc.get("valid_upto") else None, today),
		"work_permit": documents.bucket(getdate(doc.get("alphax_work_permit_expiry")) if doc.get("alphax_work_permit_expiry") else None, today),
		"contract": documents.bucket(getdate(doc.contract_end_date) if doc.get("contract_end_date") else None, today),
	}
	return {
		"name": doc.name, "employee_name": doc.employee_name, "image": doc.image, "modified": str(doc.modified),
		"sections": sections, "labels": labels, "documents": docs,
		"can_write": bool(frappe.has_permission("Employee", "write", doc)),
		"issues": _issues(doc),
	}


def _issues(doc):
	"""Data problems that silently break leave, attendance or compliance."""
	issues = []
	year = getdate(nowdate()).year
	if not doc.holiday_list:
		issues.append("no_holiday_list")
	else:
		to_date = frappe.db.get_value("Holiday List", doc.holiday_list, "to_date")
		if to_date and getdate(to_date).year < year:
			issues.append("holiday_list_outdated")
	if not doc.leave_approver:
		issues.append("no_leave_approver")
	if not doc.user_id:
		issues.append("no_user_account")
	if doc.get("alphax_is_saudi") and not doc.get("alphax_gosi_registration_date"):
		issues.append("gosi_registration_date_missing")
	if not doc.get("alphax_is_saudi") and not doc.get("alphax_iqama_number"):
		issues.append("iqama_missing")
	if not doc.get("alphax_is_saudi") and not doc.get("alphax_iqama_expiry"):
		issues.append("iqama_expiry_missing")
	return issues


@frappe.whitelist()
def update_employee(name, data, modified):
	require_hr()
	payload = parse_json(data, {})
	doc = frappe.get_doc("Employee", name)
	doc.check_permission("write")
	if not modified or get_datetime(modified) != get_datetime(doc.modified):
		frappe.throw(_("Someone else changed this employee. Reload and try again."), frappe.TimestampMismatchError)
	changes = {k: v for k, v in payload.items() if k in EDITABLE and doc.meta.has_field(k)}
	if not changes:
		frappe.throw(_("Nothing to update."))
	doc.update(changes)
	doc.save()
	return employee(doc.name)


@frappe.whitelist()
def create_employee(data):
	require_hr()
	payload = parse_json(data, {})
	required = ["first_name", "gender", "date_of_birth", "date_of_joining", "company"]
	missing = [f for f in required if not payload.get(f)]
	if missing:
		frappe.throw(_("Missing required fields: {0}").format(", ".join(missing)))
	doc = frappe.new_doc("Employee")
	doc.update({k: v for k, v in payload.items() if k in EDITABLE and doc.meta.has_field(k)})
	doc.status = "Active"
	doc.insert()
	return employee(doc.name)


@frappe.whitelist()
def lookup(doctype, txt="", filters=None):
	"""Typeahead for Link fields, limited to HR-relevant doctypes and permissions."""
	require_hr()
	if doctype not in LOOKUP_DOCTYPES:
		frappe.throw(_("Lookup not allowed."), frappe.PermissionError)
	from frappe.desk.search import search_link

	return search_link(doctype, txt=str(txt or "")[:80], filters=parse_json(filters), page_length=20)


@frappe.whitelist()
def org_summary():
	require_hr()
	rows = frappe.get_list("Employee", filters={"status": "Active"}, fields=["department", "count(name) as n"],
						   group_by="department", order_by="n desc", page_length=100)
	total = sum(r.n for r in rows)
	joiners = frappe.get_list("Employee", filters={"date_of_joining": [">=", frappe.utils.add_days(nowdate(), -30)]},
							  fields=["count(name) as n"])[0].n
	leavers = frappe.get_list("Employee", filters={"relieving_date": [">=", frappe.utils.add_days(nowdate(), -30)]},
							  fields=["count(name) as n"])[0].n
	return {"active": total, "by_department": rows, "joiners_30d": joiners, "leavers_30d": leavers}
