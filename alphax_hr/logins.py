"""Employee logins: create them in bulk, or automatically when an employee is saved with an e-mail.

A login gets the Employee (and Employee Self Service) role, is linked to the employee (Employee.user_id) and receives
Frappe's welcome e-mail to set a password. An existing user with that e-mail and no employee is linked instead of
duplicated. Nothing else (HR, manager rights) is granted here: managers get their menu from "reports to".
"""
from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import cint, validate_email_address

ROLES = ("Employee", "Employee Self Service")


def _conf():
	return frappe.get_cached_doc("AlphaX HR Settings")


def email_for(e, source=None):
	source = source or _conf().get("login_email_source") or "Company e-mail first"
	company, personal = (e.get("company_email") or "").strip(), (e.get("personal_email") or "").strip()
	order = {"Company e-mail first": (company, personal), "Personal e-mail first": (personal, company),
			 "Company e-mail only": (company,)}.get(source, (company, personal))
	for value in order:
		ok = validate_email_address(value.lower(), throw=False) if value else None
		if ok:
			return ok
	return None


def ensure(employee, email=None, welcome=True):
	"""Create or link the login of ``employee``. Returns (status, detail): created / linked / exists / skipped."""
	e = frappe.db.get_value("Employee", employee, ["name", "employee_name", "first_name", "last_name", "gender", "date_of_birth",
													"cell_number", "company_email", "personal_email", "user_id", "status"], as_dict=True)
	if not e:
		return "skipped", _("Employee not found")
	if e.user_id:
		return "exists", e.user_id
	email = validate_email_address((email or "").strip().lower(), throw=False) if email else email_for(e)
	if not email:
		return "skipped", _("No valid e-mail on the profile")
	other = frappe.db.get_value("Employee", {"user_id": email, "name": ["!=", employee]}, "employee_name")
	if other:
		return "skipped", _("{0} is already the login of {1}").format(email, other)
	if frappe.db.exists("User", email):
		user = frappe.get_doc("User", email)
		status = "linked"
	else:
		parts = (e.employee_name or "").split()
		user = frappe.get_doc({"doctype": "User", "email": email, "first_name": e.first_name or (parts[0] if parts else email),
							   "last_name": e.last_name or (" ".join(parts[1:]) if len(parts) > 1 else None), "gender": e.gender,
							   "birth_date": e.date_of_birth, "mobile_no": e.cell_number, "enabled": 1,
							   "send_welcome_email": 1 if welcome else 0})
		user.flags.ignore_permissions = True
		user.insert()
		status = "created"
	user.flags.ignore_permissions = True
	user.add_roles(*[r for r in ROLES if frappe.db.exists("Role", r)])
	doc = frappe.get_doc("Employee", employee)  # saved normally so HRMS links the user (permissions, user details)
	doc.user_id = user.name
	if not e.company_email and not e.personal_email:
		doc.personal_email = email
	doc.flags.ignore_mandatory = True
	doc.flags.ignore_permissions = True
	doc.save()
	return status, user.name


def on_employee_saved(doc, method=None):
	"""Settings → Employee logins: create the login once the employee has an e-mail."""
	if doc.user_id or doc.status != "Active" or not cint(_conf().get("auto_create_user")) or frappe.flags.in_import:
		return
	if not email_for(doc):
		return
	try:
		status, detail = ensure(doc.name)
		if status in ("created", "linked"):
			doc.user_id = detail  # keep the in-memory document in step
			frappe.msgprint(_("Login {0} for {1}: a welcome e-mail was sent.").format(detail, doc.employee_name), alert=True)
	except Exception:  # noqa: BLE001  a login problem must never block saving the employee
		frappe.log_error(title=f"AlphaX login for {doc.name}")


# ------------------------------------------------------------------ API
@frappe.whitelist()
def overview():
	from alphax_hr.api._common import require_hr

	require_hr()
	rows = frappe.get_all("Employee", filters={"status": "Active"}, order_by="employee_name asc", fields=[
		"name", "employee_name", "department", "designation", "company_email", "personal_email", "user_id"])
	without = []
	for r in rows:
		if r.user_id:
			continue
		email = email_for(r)
		taken = frappe.db.get_value("Employee", {"user_id": email}, "employee_name") if email else None
		without.append({"employee": r.name, "employee_name": r.employee_name, "department": r.department,
						"designation": r.designation, "email": email, "problem": None if email and not taken else (
							_("Already the login of {0}").format(taken) if taken else _("No e-mail"))})
	conf = _conf()
	return {"total": len(rows), "with_login": sum(1 for r in rows if r.user_id), "without": without,
			"auto": cint(conf.get("auto_create_user")), "source": conf.get("login_email_source") or "Company e-mail first"}


@frappe.whitelist(methods=["POST"])
def create(employees: str | list, emails: str | dict | None = None, background: int | str = 0):
	"""Create logins for these employees (``emails`` overrides the e-mail per employee)."""
	from alphax_hr.api._common import parse_json, require_hr_manager

	require_hr_manager()
	names = parse_json(employees) or []
	overrides = parse_json(emails) or {}
	if cint(background) and len(names) > 20:
		from alphax_hr import progress

		return progress.launch("create-logins", _("Create {0} employee logins").format(len(names)), "alphax_hr.logins.create_many",
							   total=len(names), employees=names, emails=overrides)
	return create_many(names, overrides)


def create_many(employees, emails=None, progress=None):
	out = {"created": 0, "linked": 0, "exists": 0, "skipped": []}
	for i, emp in enumerate(employees):
		if progress and i % 10 == 0:
			progress(_("Creating logins"), i, len(employees))
		try:
			status, detail = ensure(emp, (emails or {}).get(emp))
		except Exception as exc:  # noqa: BLE001
			status, detail = "skipped", frappe.utils.strip_html(str(exc))[:200]
		if status == "skipped":
			out["skipped"].append({"employee": emp, "employee_name": frappe.db.get_value("Employee", emp, "employee_name"),
								   "reason": detail})
		else:
			out[status] += 1
		frappe.db.commit() if not frappe.flags.in_test else None
	return out


@frappe.whitelist(methods=["POST"])
def save_settings(auto: int | str, source: str | None = None):
	from alphax_hr.api._common import require_hr_manager

	require_hr_manager()
	frappe.db.set_single_value("AlphaX HR Settings", "auto_create_user", cint(auto))
	if source in ("Company e-mail first", "Personal e-mail first", "Company e-mail only"):
		frappe.db.set_single_value("AlphaX HR Settings", "login_email_source", source)
	frappe.clear_document_cache("AlphaX HR Settings", "AlphaX HR Settings")
	return overview()
