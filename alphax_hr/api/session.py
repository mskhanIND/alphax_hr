"""Who am I, and what can I do? The frontend builds its navigation from this."""
import frappe

import alphax_hr
from alphax_hr.api._common import (
	APPROVER_ROLES,
	current_employee,
	is_hr,
	is_hr_manager,
	login_required,
	roles,
	settings,
)


def has_app_permission():
	return frappe.session.user != "Guest"


@frappe.whitelist()
def boot():
	user = login_required()
	user_roles = roles()
	employee = current_employee(required=False)
	emp = None
	if employee:
		emp = frappe.db.get_value(
			"Employee",
			employee,
			["name", "employee_name", "image", "designation", "department", "company", "date_of_joining"],
			as_dict=True,
		)
	conf = settings()
	approver = bool(user_roles & APPROVER_ROLES) or _is_named_approver(user)
	return {
		"user": user,
		"full_name": frappe.utils.get_fullname(user),
		"user_image": frappe.db.get_value("User", user, "user_image"),
		"roles": sorted(user_roles),
		"persona": {
			"employee": bool(employee),
			"approver": approver,
			"hr": is_hr(),
			"hr_manager": is_hr_manager(),
			"system_manager": "System Manager" in user_roles,
		},
		"employee": emp,
		"company": conf.default_company,
		"title": conf.portal_title or "AlphaX HR",
		"version": alphax_hr.__version__,
		"gosi_enabled": bool(conf.gosi_enabled),
	}


def _is_named_approver(user):
	"""Users set as leave/expense approver on any employee."""
	return bool(
		frappe.db.exists("Employee", {"leave_approver": user, "status": "Active"})
		or frappe.db.exists("Employee", {"expense_approver": user, "status": "Active"})
	)


@frappe.whitelist()
def set_language(lang):
	user = login_required()
	if lang not in ("en", "ar"):
		frappe.throw("Unsupported language")
	frappe.db.set_value("User", user, "language", lang)
	return lang
