"""Bulk update employees, and per-employee exceptions to the attendance / check-in rules."""
from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import cint

from alphax_hr.api._common import parse_json, require_hr, require_hr_manager

EMPLOYEE_FIELDS = ["department", "designation", "branch", "grade", "employment_type", "reports_to", "leave_approver",
				   "expense_approver", "shift_request_approver", "holiday_list", "default_shift", "payroll_cost_center",
				   "salary_mode", "bank_name", "alphax_annual_leave_days"]
POLICY_FIELDS = {
	"checkin_location_rule": ("Check-in location rule", "Select", ["", "Anywhere", "Must share location", "Inside a work location"]),
	"min_punch_gap": ("Minutes between punches", "Int", None),
	"late_grace_minutes": ("Late grace (minutes)", "Int", None),
	"early_grace_minutes": ("Early-exit grace (minutes)", "Int", None),
	"exempt": ("Exempt from attendance tracking", "Check", None),
	"single_punch_ok": ("A single punch counts as present", "Check", None),
	"no_penalties": ("Never suggest penalties", "Check", None),
}


def _field_specs():
	meta = frappe.get_meta("Employee")
	out = []
	for f in EMPLOYEE_FIELDS:
		df = meta.get_field(f)
		if not df:
			continue
		spec = {"fieldname": f, "label": _(df.label), "fieldtype": df.fieldtype, "group": "employee"}
		if df.fieldtype == "Select":
			spec["options"] = (df.options or "").split("\n")
		elif df.fieldtype == "Link":
			spec["options"] = df.options
		out.append(spec)
	for f, (label, kind, options) in POLICY_FIELDS.items():
		out.append({"fieldname": f, "label": _(label), "fieldtype": kind, "options": options, "group": "attendance"})
	return out


@frappe.whitelist()
def options():
	require_hr()
	return {"fields": _field_specs(), "companies": frappe.get_list("Company", pluck="name"),
			"departments": frappe.get_all("Department", filters={"is_group": 0}, pluck="name", order_by="name"),
			"branches": frappe.get_all("Branch", pluck="name", order_by="name"),
			"designations": frappe.get_all("Designation", pluck="name", order_by="name")}


def _employees(filters=None, employees=None):
	if employees:
		return list(dict.fromkeys(e for e in employees if e))
	f = {"status": "Active"}
	for k in ("company", "department", "branch", "designation"):
		if (filters or {}).get(k):
			f[k] = filters[k]
	return frappe.get_all("Employee", filters=f, pluck="name", order_by="employee_name asc")


@frappe.whitelist(methods=["POST"])
def preview(field, filters=None, employees=None):
	require_hr()
	ids = _employees(parse_json(filters) or {}, parse_json(employees) or [])
	rows = []
	for e in frappe.get_all("Employee", filters={"name": ["in", ids or [""]]},
							fields=["name", "employee_name", "department", "designation"], order_by="employee_name asc"):
		if field in POLICY_FIELDS:
			from alphax_hr.api import attendance_policy

			pol = attendance_policy.for_employee(e.name)
			current = pol.get(field) if pol else None
		else:
			current = frappe.db.get_value("Employee", e.name, field) if frappe.get_meta("Employee").has_field(field) else None
		rows.append({**e, "current": current})
	return {"rows": rows, "count": len(rows)}


@frappe.whitelist(methods=["POST"])
def apply(field, value, filters=None, employees=None):
	"""Set one field for many employees. Each employee is saved on its own; failures are listed, the rest go through."""
	require_hr_manager()
	allowed = {s["fieldname"] for s in _field_specs()}
	if field not in allowed:
		frappe.throw(_("This field cannot be bulk updated."))
	ids = _employees(parse_json(filters) or {}, parse_json(employees) or [])
	if not ids:
		frappe.throw(_("No employees match."))
	done, failed = [], []
	for emp in ids:
		frappe.db.savepoint("alphax_bulk")
		try:
			if field in POLICY_FIELDS:
				save_exception(emp, {field: value}, _check=False)
			else:
				doc = frappe.get_doc("Employee", emp)
				doc.check_permission("write")
				doc.set(field, value or None)
				doc.flags.ignore_mandatory = True  # only this field changes; missing data elsewhere is fixed separately
				doc.save()
			done.append(emp)
		except Exception as exc:  # noqa: BLE001
			frappe.db.rollback(save_point="alphax_bulk")
			failed.append({"employee": emp, "error": frappe.utils.strip_html(str(exc))[:300]})
			frappe.clear_messages()
	if done:
		frappe.get_doc({"doctype": "Comment", "comment_type": "Info", "reference_doctype": "Employee", "reference_name": done[0],
						"content": _("Bulk update by {0}: {1} = {2} for {3} employee(s)").format(
							frappe.session.user, field, value, len(done))}).insert(ignore_permissions=True)
	return {"done": done, "failed": failed}


# ------------------------------------------------------------------ per-employee attendance / check-in exception
def _policy_name(employee):
	return frappe.db.get_value("AlphaX Attendance Policy", {"applies_to": "Employee", "employee": employee}, "name")


@frappe.whitelist()
def exception(employee):
	"""The rules that apply to this employee today, and whether they come from the employee's own exception."""
	require_hr()
	from alphax_hr.api import attendance_policy
	from alphax_hr.api._common import settings

	pol = attendance_policy.for_employee(employee)
	own = _policy_name(employee)
	conf = settings()
	rules = {k: (pol.get(k) if pol else None) for k in POLICY_FIELDS}
	return {"own": bool(own), "source": pol.policy_name if pol else None, "rules": rules,
			"defaults": {"checkin_location_rule": conf.get("checkin_location_rule") or "Anywhere",
						 "min_punch_gap": cint(conf.get("checkin_min_gap"))},
			"fields": [s for s in _field_specs() if s["group"] == "attendance"]}


@frappe.whitelist(methods=["POST"])
def save_exception(employee, data, _check=True):
	"""Create or update the employee's own policy. The first time, it starts from the rules that applied before."""
	if _check:
		require_hr_manager()
	from alphax_hr.api import attendance_policy

	data = parse_json(data) or {}
	name = _policy_name(employee)
	if name:
		doc = frappe.get_doc("AlphaX Attendance Policy", name)
	else:
		base = attendance_policy.for_employee(employee)
		emp_name = frappe.db.get_value("Employee", employee, "employee_name")
		doc = frappe.get_doc({"doctype": "AlphaX Attendance Policy", "policy_name": f"{emp_name} ({employee})"[:140], "enabled": 1,
							  "applies_to": "Employee", "employee": employee,
							  "description": _("Exception for one employee") + (f" - {_('based on')} {base.policy_name}" if base else "")})
		if base:
			for k in attendance_policy.RULES:
				doc.set(k, base.get(k))
	for k, v in data.items():
		if k in POLICY_FIELDS:
			kind = POLICY_FIELDS[k][1]
			doc.set(k, cint(v) if kind == "Check" else ("" if v in (None, "") else str(v)))
	doc.flags.ignore_permissions = True
	doc.save()
	return exception(employee) if _check else {"name": doc.name}


@frappe.whitelist(methods=["POST"])
def remove_exception(employee):
	require_hr_manager()
	name = _policy_name(employee)
	if name:
		frappe.delete_doc("AlphaX Attendance Policy", name, ignore_permissions=True)
	return exception(employee)
