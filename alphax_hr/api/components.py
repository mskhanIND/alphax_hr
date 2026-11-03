"""Standard Saudi payroll components (salary, allowances, overtime, leave, end of service, accruals, deductions),
created once and mapped to AlphaX settings. Components that already exist under a common name are reused, never
duplicated; HR can point any setting at another component."""
from __future__ import annotations

import frappe
from frappe import _

from alphax_hr.api._common import require_hr, require_hr_manager

# key, name, Arabic, abbr, type, setting field, depends on payment days, statistical, other names already in use, group, map purposes
CATALOGUE = [
	("basic", "Basic Salary", "الراتب الأساسي", "BS", "Earning", "salary_basic_component", 1, 0, ("Basic", "Basic Pay"), "Salary",
	 ("GOSI Basic", "EOSB Wage", "Nitaqat Wage")),
	("housing", "Housing Allowance", "بدل السكن", "HA", "Earning", "salary_housing_component", 1, 0,
	 ("House Rent Allowance", "Housing", "HRA"), "Salary", ("GOSI Housing", "EOSB Wage", "Nitaqat Wage")),
	("transport", "Transportation Allowance", "بدل النقل", "TA", "Earning", "salary_transport_component", 1, 0,
	 ("Transport Allowance", "Transport", "Conveyance Allowance"), "Salary", ("EOSB Wage", "Nitaqat Wage")),
	("other", "Other Allowance", "بدلات أخرى", "OA", "Earning", "salary_other_component", 1, 0, ("Other Allowances",), "Salary",
	 ("EOSB Wage", "Nitaqat Wage")),
	("food", "Food Allowance", "بدل الطعام", "FA", "Earning", None, 1, 0, (), "Salary", ()),
	("phone", "Phone Allowance", "بدل الاتصال", "PHA", "Earning", None, 1, 0, ("Mobile Allowance",), "Salary", ()),
	("overtime", "Overtime", "العمل الإضافي", "OT", "Earning", "overtime_component", 0, 0, ("Overtime Allowance", "Over Time"), "Payroll", ()),
	("bonus", "Bonus", "مكافأة", "BON", "Earning", "bonus_component", 0, 0, ("Performance Bonus",), "Payroll", ()),
	("commission", "Commission", "عمولة", "COM", "Earning", None, 0, 0, (), "Payroll", ()),
	("arrears", "Arrears", "فروقات رواتب", "ARR", "Earning", None, 0, 0, ("Arrear", "Salary Arrears"), "Payroll", ()),
	("leave_encashment", "Leave Encashment", "بدل رصيد الإجازات", "LENC", "Earning", "leave_encashment_component", 0, 0, (), "Leave", ()),
	("eos", "End of Service Benefit", "مكافأة نهاية الخدمة", "EOSB", "Earning", "eos_component", 0, 0, ("End of Service", "Gratuity"),
	 "End of service", ()),
	("eos_provision", "End of Service Provision", "مخصص نهاية الخدمة", "EOSP", "Earning", "eos_provision_component", 0, 1, (),
	 "Accruals", ()),
	("leave_provision", "Annual Leave Provision", "مخصص الإجازات", "ALP", "Earning", "leave_provision_component", 0, 1, (),
	 "Accruals", ()),
	("gosi_employer", "GOSI Employer Share", "حصة صاحب العمل في التأمينات", "GOSIC", "Earning", None, 0, 1, (), "Accruals", ()),
	("gosi", "GOSI Employee Share", "التأمينات الاجتماعية - حصة الموظف", "GOSI", "Deduction", "salary_gosi_component", 0, 0,
	 ("GOSI", "GOSI Employee", "GOSI Deduction"), "Deductions", ()),
	("absence", "Absence Deduction", "خصم الغياب", "ABS", "Deduction", "absence_component", 0, 0, ("Absent Deduction",), "Deductions", ()),
	("penalty", "Penalty Deduction", "خصم الجزاءات", "PEN", "Deduction", "penalty_component", 0, 0,
	 ("Penalties", "Penalty", "Disciplinary Deduction"), "Deductions", ()),
	("loan", "Loan Repayment", "سداد القروض والسلف", "LR", "Deduction", "loan_component", 0, 0, ("Loan Deduction", "Advance Deduction"),
	 "Deductions", ()),
	("hr_deduction", "HR Deduction", "خصومات أخرى", "HRD", "Deduction", "hr_deduction_component", 0, 0, ("Other Deduction",), "Deductions", ()),
]


def _existing(name, alt):
	for n in (name, *alt):
		if frappe.db.exists("Salary Component", n):
			return n
	return None


def _abbr(abbr):
	if not frappe.db.exists("Salary Component", {"salary_component_abbr": abbr}):
		return abbr
	i = 2
	while frappe.db.exists("Salary Component", {"salary_component_abbr": f"{abbr}{i}"}):
		i += 1
	return f"{abbr}{i}"


def seed(create=True):
	"""Create missing standard components, fill empty settings and the wage mapping. Returns what was created."""
	if not frappe.db.exists("DocType", "Salary Component") or not frappe.db.exists("DocType", "AlphaX HR Settings"):
		return []
	made = []
	resolved = {}
	for key, name, _ar, abbr, kind, setting, pdays, stat, alt, _group, _purposes in CATALOGUE:
		current = frappe.db.get_single_value("AlphaX HR Settings", setting) if setting else None
		comp = current if current and frappe.db.exists("Salary Component", current) else _existing(name, alt)
		if not comp and create:
			doc = frappe.get_doc({"doctype": "Salary Component", "salary_component": name, "salary_component_abbr": _abbr(abbr),
								  "type": kind, "depends_on_payment_days": pdays, "statistical_component": stat,
								  "do_not_include_in_total": stat, "description": _ar})
			doc.flags.ignore_permissions = True
			doc.insert()
			comp = doc.name
			made.append(comp)
		resolved[key] = comp
		if setting and comp and not current:
			frappe.db.set_single_value("AlphaX HR Settings", setting, comp)
	_seed_map(resolved)
	frappe.clear_document_cache("AlphaX HR Settings", "AlphaX HR Settings")
	return made


def _seed_map(resolved):
	conf = frappe.get_single("AlphaX HR Settings")
	if conf.get("component_map"):
		return  # HR's own mapping is kept
	for key, *_rest in CATALOGUE:
		purposes = _rest[-1]
		for purpose in purposes:
			if resolved.get(key):
				conf.append("component_map", {"salary_component": resolved[key], "purpose": purpose})
	if conf.get("component_map"):
		conf.flags.ignore_permissions = True
		conf.flags.ignore_mandatory = True
		conf.save()


@frappe.whitelist()
def catalogue():
	require_hr()
	conf = frappe.get_cached_doc("AlphaX HR Settings")
	rows = []
	for key, name, ar, abbr, kind, setting, pdays, stat, alt, group, purposes in CATALOGUE:
		used = conf.get(setting) if setting else _existing(name, alt)
		rows.append({"key": key, "name": name, "name_ar": ar, "type": kind, "group": group, "setting": setting,
					 "in_use": used, "exists": bool(used and frappe.db.exists("Salary Component", used)),
					 "statistical": bool(stat), "map": list(purposes)})
	mapping = [{"component": r.salary_component, "purpose": r.purpose} for r in conf.get("component_map") or []]
	return {"rows": rows, "mapping": mapping, "can_edit": bool(set(frappe.get_roles()) & {"HR Manager", "System Manager"})}


@frappe.whitelist(methods=["POST"])
def create_missing():
	require_hr_manager()
	made = seed()
	return {"created": made, **catalogue()}


def get(key):
	"""Component in use for a catalogue key (creating the standard one if the site has none)."""
	row = next(r for r in CATALOGUE if r[0] == key)
	setting, name, alt = row[5], row[1], row[8]
	if setting:
		chosen = frappe.get_cached_doc("AlphaX HR Settings").get(setting)
		if chosen and frappe.db.exists("Salary Component", chosen):
			return chosen
	existing = _existing(name, alt)
	if existing:
		return existing
	seed()
	return _existing(name, alt) or name


def label(key):
	return _(next(r for r in CATALOGUE if r[0] == key)[1])
