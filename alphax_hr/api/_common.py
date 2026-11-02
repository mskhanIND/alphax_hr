"""Shared guards and helpers for the AlphaX HR API.

Rules every endpoint follows:
* No guest access. ``login_required`` runs first.
* Roles are decided on the server from ``frappe.get_roles`` — never from a
  value the browser sends.
* Reads use permission-aware ``frappe.get_list`` / ``doc.check_permission``.
* Writes go through normal ``doc.insert/save/submit`` so HRMS validations,
  workflows and user permissions stay authoritative.
"""
from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import getdate

HR_ROLES = frozenset({"HR Manager", "HR User", "System Manager"})
HR_MANAGER_ROLES = frozenset({"HR Manager", "System Manager"})
APPROVER_ROLES = frozenset({"Leave Approver", "Expense Approver"})


def login_required() -> str:
	user = frappe.session.user
	if not user or user == "Guest":
		frappe.throw(_("Please sign in."), frappe.AuthenticationError)
	return user


def roles(user: str | None = None) -> set[str]:
	return set(frappe.get_roles(user or frappe.session.user))


def is_hr(user: str | None = None) -> bool:
	return bool(roles(user) & HR_ROLES)


def is_hr_manager(user: str | None = None) -> bool:
	return bool(roles(user) & HR_MANAGER_ROLES)


def require_hr():
	login_required()
	if not is_hr():
		frappe.throw(_("This area is for the HR team."), frappe.PermissionError)


def require_hr_manager():
	login_required()
	if not is_hr_manager():
		frappe.throw(_("Only an HR Manager can do this."), frappe.PermissionError)


def current_employee(required: bool = True) -> str | None:
	"""Active Employee linked to the signed-in user."""
	user = login_required()
	name = frappe.db.get_value("Employee", {"user_id": user, "status": "Active"}, "name")
	if not name and required:
		frappe.throw(
			_("Your user is not linked to an active employee record. Please contact HR."),
			frappe.DoesNotExistError,
		)
	return name


def settings():
	return frappe.get_cached_doc("AlphaX HR Settings")


def parse_json(value, default=None):
	if value in (None, ""):
		return default
	if isinstance(value, (dict, list)):
		return value
	try:
		return frappe.parse_json(value)
	except Exception:
		frappe.throw(_("Invalid JSON payload."))


def as_date(value):
	return getdate(value) if value else None


def clamp_page(start, page_length, maximum=100):
	start = max(0, frappe.utils.cint(start))
	page_length = min(max(1, frappe.utils.cint(page_length) or 20), maximum)
	return start, page_length


def doctype_installed(doctype: str) -> bool:
	return bool(frappe.db.exists("DocType", doctype))


def has_field(doctype: str, fieldname: str) -> bool:
	return bool(frappe.get_meta(doctype).has_field(fieldname))
