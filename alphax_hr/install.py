"""Idempotent install / migrate steps. Only AlphaX's own records are seeded."""
import frappe

from alphax_hr.saudi.gosi import DEFAULT_RATES


def after_install():
	seed_gosi_rates()
	seed_settings()


def after_migrate():
	seed_gosi_rates()
	seed_settings()


def seed_gosi_rates():
	"""Insert statutory default rows that are not present yet. Edited rows are kept."""
	if not frappe.db.exists("DocType", "GOSI Contribution Rate"):
		return
	for row in DEFAULT_RATES:
		exists = frappe.db.exists(
			"GOSI Contribution Rate",
			{"system": row.system, "effective_from": row.effective_from},
		)
		if exists:
			continue
		frappe.get_doc(
			{
				"doctype": "GOSI Contribution Rate",
				"system": row.system,
				"effective_from": row.effective_from,
				"employee_pension": float(row.employee_pension),
				"employer_pension": float(row.employer_pension),
				"employee_saned": float(row.employee_saned),
				"employer_saned": float(row.employer_saned),
				"employer_hazard": float(row.employer_hazard),
				"notes": "Seeded statutory default (Royal Decree M/273 schedule for New system).",
			}
		).insert(ignore_permissions=True)


def seed_settings():
	if not frappe.db.exists("DocType", "AlphaX HR Settings"):
		return
	settings = frappe.get_single("AlphaX HR Settings")
	changed = False
	defaults = {
		"portal_title": "AlphaX HR",
		"default_language": "en",
		"gosi_enabled": 1,
		"gosi_wage_cap": 45000,
		"nitaqat_full_count_wage": 4000,
		"nitaqat_partial_weight": 0.5,
		"document_alert_days": 60,
	}
	for key, value in defaults.items():
		if settings.get(key) in (None, "", 0) and key not in ("gosi_enabled",):
			settings.set(key, value)
			changed = True
	if not settings.default_company:
		company = frappe.db.get_single_value("Global Defaults", "default_company")
		if company:
			settings.default_company = company
			changed = True
	if not settings.component_map:
		for component, purpose in (("Basic", "GOSI Basic"), ("Basic", "EOSB Wage"),
								   ("House Rent Allowance", "GOSI Housing"),
								   ("Housing Allowance", "GOSI Housing")):
			if frappe.db.exists("Salary Component", component):
				settings.append("component_map", {"salary_component": component, "purpose": purpose})
				changed = True
	if changed:
		settings.flags.ignore_permissions = True
		settings.save()
