"""Saudi compliance & HR data-readiness dashboard (HR only)."""
from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import add_days, cint, flt, get_first_day, get_last_day, getdate, nowdate

from alphax_hr.api._common import require_hr, require_hr_manager, settings
from alphax_hr.api._wages import wages
from alphax_hr.saudi import documents, nitaqat

EMP_FIELDS = ["name", "employee_name", "department", "alphax_is_saudi", "alphax_gosi_registration_date",
			  "alphax_iqama_number", "alphax_iqama_expiry", "alphax_work_permit_expiry", "valid_upto",
			  "contract_end_date", "holiday_list", "leave_approver", "user_id", "date_of_joining"]


def _active(company=None):
	meta = frappe.get_meta("Employee")
	filters = {"status": "Active"}
	if company:
		filters["company"] = company
	return frappe.get_list("Employee", filters=filters, fields=[f for f in EMP_FIELDS if meta.has_field(f) or f == "name"],
						   order_by="employee_name asc", page_length=10000)


def _sample(rows, limit=25):
	return [{"employee": r.name, "employee_name": r.employee_name, "department": r.department} for r in rows[:limit]]


@frappe.whitelist()
def overview(company=None):
	require_hr()
	conf = settings()
	company = company or conf.default_company
	today = getdate(nowdate())
	emps = _active(company)
	foreign = [e for e in emps if not e.get("alphax_is_saudi")]

	# Nitaqat estimate
	wage_map = wages([e.name for e in emps], get_first_day(today), get_last_day(today))
	policy = nitaqat.NitaqatPolicy(
		full_count_wage=flt(conf.nitaqat_full_count_wage) or 4000,
		partial_weight=flt(conf.nitaqat_partial_weight) if conf.nitaqat_partial_weight is not None else 0.5,
		target_percent=flt(conf.nitaqat_target_percent) or None,
	)
	nit = nitaqat.ratio(
		[{"is_saudi": bool(e.get("alphax_is_saudi")), "wage": wage_map[e.name]["basic"] + wage_map[e.name]["housing"]}
		 for e in emps], policy)

	def expiry(rows, field):
		return documents.summarize(
			[{"expiry": getdate(r.get(field)) if r.get(field) else None} for r in rows], today)

	docs = {
		"iqama": expiry(foreign, "alphax_iqama_expiry"),
		"work_permit": expiry(foreign, "alphax_work_permit_expiry"),
		"passport": expiry(foreign, "valid_upto"),
		"contract": expiry(emps, "contract_end_date"),
	}

	# Data readiness checks: what silently breaks leave, payroll and compliance.
	year = today.year
	lists = {r.name: getdate(r.to_date) for r in frappe.get_all("Holiday List", fields=["name", "to_date"])}
	checks = []

	def check(key, rows, severity):
		checks.append({"key": key, "severity": severity, "count": len(rows), "sample": _sample(rows)})

	check("holiday_list_missing_or_outdated",
		  [e for e in emps if not e.holiday_list or (lists.get(e.holiday_list) and lists[e.holiday_list].year < year)], "high")
	check("leave_approver_missing", [e for e in emps if not e.leave_approver], "medium")
	check("user_account_missing", [e for e in emps if not e.user_id], "medium")
	check("gosi_registration_date_missing",
		  [e for e in emps if e.get("alphax_is_saudi") and not e.get("alphax_gosi_registration_date")], "high")
	check("iqama_number_missing", [e for e in foreign if not e.get("alphax_iqama_number")], "high")
	check("iqama_expiry_missing", [e for e in foreign if not e.get("alphax_iqama_expiry")], "high")
	check("no_salary_data", [e for e in emps if wage_map[e.name]["source"] == "none"], "medium")
	if frappe.get_meta("Employee").has_field("nationality"):
		saudi_names = {r.name for r in frappe.get_list(
			"Employee", filters={"status": "Active", "nationality": ["like", "%saudi%"]}, pluck="name", page_length=10000)}
		check("saudi_flag_mismatch", [e for e in emps if e.name in saudi_names and not e.get("alphax_is_saudi")], "high")

	# HR staff restricted to their own Employee record by an auto-created User Permission
	# cannot see the workforce (HRMS creates these when "Create User Permission" is ticked).
	hr_users = set(frappe.get_all("Has Role", filters={"role": ["in", ["HR Manager", "HR User"]], "parenttype": "User"}, pluck="parent"))
	restricted = sorted({u for u in frappe.get_all("User Permission", filters={"allow": "Employee", "user": ["in", list(hr_users) or [""]]},
								 pluck="user")} - {"Administrator"})
	checks.append({"key": "hr_user_restricted_to_own_record", "severity": "high", "count": len(restricted),
				   "sample": [{"employee": u, "employee_name": frappe.utils.get_fullname(u), "department": None} for u in restricted[:25]]})

	company_default_list = frappe.db.get_value("Company", company, "default_holiday_list") if company else None
	return {
		"company": company,
		"as_of": str(today),
		"headcount": len(emps),
		"nitaqat": nit,
		"documents": docs,
		"checks": sorted(checks, key=lambda c: ({"high": 0, "medium": 1}[c["severity"]], -c["count"])),
		"company_holiday_list": company_default_list,
		"company_holiday_list_outdated": bool(company_default_list and lists.get(company_default_list)
											 and lists[company_default_list].year < year),
	}


@frappe.whitelist()
def expiring_documents(days=90, company=None):
	require_hr()
	conf = settings()
	today = getdate(nowdate())
	horizon = add_days(today, cint(days) or 90)
	rows = []
	for e in _active(company or conf.default_company):
		for kind, field in (("iqama", "alphax_iqama_expiry"), ("work_permit", "alphax_work_permit_expiry"),
							("passport", "valid_upto"), ("contract", "contract_end_date")):
			value = e.get(field)
			if value and getdate(value) <= getdate(horizon):
				rows.append({"employee": e.name, "employee_name": e.employee_name, "department": e.department,
							 "document": kind, "expiry": str(value), "days_left": (getdate(value) - today).days})
	return sorted(rows, key=lambda r: r["days_left"])


# Mapping from CentralHRMS / legacy custom fields into AlphaX fields.
LEGACY_MAP = (
	("custom_identity_number", "alphax_iqama_number"),
	("iqama_national_id", "alphax_iqama_number"),
	("custom_identity_valid_upto", "alphax_iqama_expiry"),
	("iqama_expiry_date", "alphax_iqama_expiry"),
	("custom_work_permit_expiry_date", "alphax_work_permit_expiry"),
)


@frappe.whitelist()
def import_legacy_fields(dry_run=1, saudi_nationality="Saudi"):
	"""One-time onboarding for sites coming from CentralHRMS: copy legacy values into
	empty AlphaX fields. Never overwrites a value already set. HR Manager only."""
	require_hr_manager()
	meta = frappe.get_meta("Employee")
	sources = [(s, t) for s, t in LEGACY_MAP if meta.has_field(s) and meta.has_field(t)]
	fields = ["name", "alphax_is_saudi"] + sorted({s for s, _t in sources} | {t for _s, t in sources})
	has_nationality = meta.has_field("nationality")
	if has_nationality:
		fields.append("nationality")
	plan = []
	for e in frappe.get_list("Employee", fields=fields, page_length=100000):
		changes = {}
		for src, target in sources:
			if e.get(src) and not e.get(target) and target not in changes:
				changes[target] = e.get(src)
		if has_nationality and e.get("nationality") == saudi_nationality and not e.get("alphax_is_saudi"):
			changes["alphax_is_saudi"] = 1
		if changes:
			plan.append({"employee": e.name, "changes": changes})
	if not cint(dry_run):
		for item in plan:
			doc = frappe.get_doc("Employee", item["employee"])
			doc.check_permission("write")
			doc.update(item["changes"])
			doc.flags.ignore_mandatory = True  # legacy records may miss unrelated mandatory fields
			doc.save()
	return {"dry_run": bool(cint(dry_run)), "employees": len(plan), "sources": sources, "sample": plan[:20]}
