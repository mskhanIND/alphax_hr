"""Idempotent install / migrate steps. Only AlphaX's own records are seeded."""
import frappe

from alphax_hr.saudi.gosi import DEFAULT_RATES


def after_install():
	seed_gosi_rates()
	seed_settings()
	seed_leave_rules()
	seed_catalogues()


def after_migrate():
	seed_gosi_rates()
	seed_settings()
	seed_leave_rules()
	apply_field_rules()
	from alphax_hr.api.salary import seed_components

	seed_components()
	seed_catalogues()


def seed_roles():
	if not frappe.db.exists("Role", "AlphaX Management"):
		frappe.get_doc({"doctype": "Role", "role_name": "AlphaX Management", "desk_access": 0}).insert(ignore_permissions=True)


def seed_catalogues():
	"""Default request types and violations schedule (only missing ones; HR edits are kept)."""
	seed_roles()
	from alphax_hr.api.penalties import seed_violations
	from alphax_hr.api.requests import seed_types

	seed_types()
	seed_violations()
	from alphax_hr.api.alerts import seed_rules

	seed_rules()


# AlphaX's own Employee columns and the width they really need. Sites with many
# custom fields hit MariaDB's 65,535-byte row limit (every varchar(140) reserves
# 560 bytes), so AlphaX keeps its footprint small.
# (64 is the narrowest varchar Frappe creates.)
EMPLOYEE_COLUMN_LENGTHS = {"alphax_iqama_number": 64, "alphax_border_number": 64, "alphax_gosi_number": 64,
						   "alphax_contract_years": 64}
ROW_LIMIT = 65535


def before_migrate():
	seed_roles()  # doctype permissions refer to it
	shrink_own_columns()


def shrink_own_columns():
	"""Narrow AlphaX's varchar columns on tabEmployee before new fields are added. Never touches other apps' columns,
	and skips a column if any stored value would not fit."""
	if not frappe.db.table_exists("Employee"):
		return
	cols = {c.Field: c.Type for c in frappe.db.sql("SHOW COLUMNS FROM `tabEmployee`", as_dict=True)}
	for col, length in EMPLOYEE_COLUMN_LENGTHS.items():
		current = cols.get(col, "")
		if not current.startswith("varchar("):
			continue
		if int(current[8:-1]) <= length:
			continue
		longest = frappe.db.sql(f"SELECT MAX(CHAR_LENGTH(`{col}`)) FROM `tabEmployee`")[0][0] or 0
		if longest > length:
			print(f"AlphaX: kept {col} as {current}; a stored value has {longest} characters")
			continue
		frappe.db.sql_ddl(f"ALTER TABLE `tabEmployee` MODIFY `{col}` varchar({length})")
		frappe.db.set_value("Custom Field", {"dt": "Employee", "fieldname": col}, "length", length, update_modified=False)
		print(f"AlphaX: {col} {current} -> varchar({length})")


def employee_row_size():
	"""bench --site SITE execute alphax_hr.install.employee_row_size  -> how full tabEmployee's row is."""
	used = 0
	widest = []
	for c in frappe.db.sql("SHOW COLUMNS FROM `tabEmployee`", as_dict=True):
		t = c.Type.lower()
		if t.startswith("varchar("):
			n = int(t[8:t.index(")")]) * 4 + 2
		elif "text" in t or "blob" in t:
			n = 12
		elif t.startswith("decimal"):
			n = 12
		elif t.startswith(("int", "bigint")):
			n = 8
		elif t.startswith(("date", "time")):
			n = 8
		else:
			n = 8
		used += n
		widest.append((n, c.Field, c.Type))
	widest.sort(reverse=True)
	print(f"tabEmployee declared row size ~ {used:,} of {ROW_LIMIT:,} bytes ({100 * used / ROW_LIMIT:.0f}%), {len(widest)} columns")
	print("Widest columns:")
	for n, f, t in widest[:15]:
		print(f"  {n:>6,}  {f}  {t}")
	return {"used": used, "limit": ROW_LIMIT}


def apply_field_rules():
	"""Site field settings AlphaX owns: passport is checked by AlphaX for non-Saudis only."""
	if not frappe.db.exists("DocType", "AlphaX HR Settings"):
		return
	if not frappe.db.get_single_value("AlphaX HR Settings", "passport_non_saudi_only"):
		return
	if frappe.get_meta("Employee").get_field("passport_number") and frappe.get_meta("Employee").get_field("passport_number").reqd:
		from frappe.custom.doctype.property_setter.property_setter import make_property_setter

		make_property_setter("Employee", "passport_number", "reqd", 0, "Check", validate_fields_for_doctype=False)
		frappe.clear_cache(doctype="Employee")


def _fill_new_setting_defaults():
	"""Settings added in a later version get their default once; values HR saved are never touched."""
	# tabSingles is a plain table, not a DocType, so it is read with SQL.
	saved = set(frappe.db.sql_list("select field from `tabSingles` where doctype=%s", "AlphaX HR Settings"))
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
