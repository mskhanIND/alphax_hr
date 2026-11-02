"""Idempotent install / migrate steps. Only AlphaX's own records are seeded."""
import frappe

from alphax_hr.saudi.gosi import DEFAULT_RATES


def after_install():
	seed_gosi_rates()
	seed_settings()
	seed_leave_rules()


def after_migrate():
	seed_gosi_rates()
	seed_settings()
	seed_leave_rules()


def _fill_new_setting_defaults():
	"""Settings added in a later version get their default once; values HR saved are never touched."""
	saved = set(frappe.get_all("Singles", filters={"doctype": "AlphaX HR Settings"}, pluck="field"))
	for df in frappe.get_meta("AlphaX HR Settings").fields:
		if df.default not in (None, "") and df.fieldname not in saved and not df.is_virtual:
			frappe.db.set_single_value("AlphaX HR Settings", df.fieldname, df.default)


def seed_leave_rules():
	"""Map existing statutory Leave Types (by common names) to AlphaX rules, once."""
	if not frappe.db.exists("DocType", "AlphaX Leave Rule"):
		return
	from alphax_hr.saudi import leave_rules as lr

	settings = frappe.get_single("AlphaX HR Settings")
	mapped = {r.leave_type for r in settings.leave_rules}
	changed = False
	for kind, names in lr.DEFAULT_LEAVE_TYPE_NAMES.items():
		for name in names:
			if frappe.db.exists("Leave Type", name) and name not in mapped:
				settings.append("leave_rules", rule_row(name, kind))
				mapped.add(name)
				changed = True
				break
	if not settings.annual_leave_type:
		for name in ("Annual Leave", "Annual Vacation", "Saudi Annual Leave"):
			if frappe.db.exists("Leave Type", name):
				settings.annual_leave_type = name
				changed = True
				break
	if changed:
		settings.flags.ignore_permissions = True
		settings.save()


def rule_row(leave_type, kind):
	from alphax_hr.saudi import leave_rules as lr

	r = lr.default_rule(kind)
	return {
		"leave_type": leave_type, "rule": kind, "enabled": 1, "max_days": r.max_days or 0, "gender": r.gender or "",
		"min_service_days": r.min_service_days or 0, "lifetime_limit": r.lifetime_limit or 0,
		"requires_event_date": 1 if r.requires_event_date else 0, "event_label": r.event_label,
		"days_before_event": "" if r.days_before_event is None else str(r.days_before_event),
		"days_after_event": "" if r.days_after_event is None else str(r.days_after_event),
		"relations": "\n".join(r.relations), "requires_attachment": 1 if r.requires_attachment else 0,
	}


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
	_fill_new_setting_defaults()
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
