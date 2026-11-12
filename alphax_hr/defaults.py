"""Ready defaults: what a new site needs before HR can work, created once and never duplicated.

Site-wide (on install, and from Setup → Prepare defaults): Saudi statutory leave types with their rules, Annual Leave,
salary components, banks, a default shift, request types, notifications and labour-law catalogues.
Per company (when a company is created, and from Setup): a holiday list for this year and next with Friday and Saturday
off and the Saudi public holidays, set as the company default; the payroll payable account; AlphaX's default company.

Existing records are reused: a leave type or holiday list that already exists is linked, not recreated.
"""
from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import getdate, nowdate

DEFAULT_SHIFT = ("General Shift", "08:00:00", "17:00:00")
WEEKLY_OFF = ("Friday", "Saturday")


def _safe(fn, results, key):
	try:
		results[key] = fn()
	except Exception as exc:  # noqa: BLE001  one missing piece must not stop the others
		frappe.log_error(title=f"AlphaX defaults: {key}")
		results[key] = {"error": frappe.utils.strip_html(str(exc))[:200]}


# ------------------------------------------------------------------ site-wide
def leave_types():
	"""Statutory leave types (mapped to their rules) and Annual Leave."""
	from alphax_hr.api.leave_setup import STATUTORY_TYPES
	from alphax_hr.install import rule_row, seed_leave_rules
	from alphax_hr.saudi import leave_rules as lr

	seed_leave_rules()  # first map leave types that already exist under common names
	conf = frappe.get_single("AlphaX HR Settings")
	mapped = {r.rule for r in conf.leave_rules}
	created = []
	for kind, (name, calendar_days) in STATUTORY_TYPES.items():
		if kind in mapped:
			continue
		if not frappe.db.exists("Leave Type", name):
			rule = lr.default_rule(kind)
			frappe.get_doc({"doctype": "Leave Type", "leave_type_name": name, "is_lwp": 0, "allow_negative": 1,
							"include_holiday": calendar_days, "max_continuous_days_allowed": int(rule.max_days or 0)}
						   ).insert(ignore_permissions=True)
			created.append(name)
		conf.append("leave_rules", rule_row(name, kind))
	if not conf.annual_leave_type:
		if not frappe.db.exists("Leave Type", "Annual Leave"):
			frappe.get_doc({"doctype": "Leave Type", "leave_type_name": "Annual Leave", "is_lwp": 0, "allow_negative": 0,
							"include_holiday": 0, "is_carry_forward": 1}).insert(ignore_permissions=True)
			created.append("Annual Leave")
		conf.annual_leave_type = "Annual Leave"
	conf.flags.ignore_permissions = True
	conf.save()
	return {"created": created}


def shift():
	"""One default shift if the site has none."""
	if frappe.get_all("Shift Type", limit=1):
		return {"created": []}
	name, start, end = DEFAULT_SHIFT
	frappe.get_doc({"doctype": "Shift Type", "name": name, "__newname": name, "start_time": start, "end_time": end,
					"enable_auto_attendance": 0}).insert(ignore_permissions=True)
	return {"created": [name]}


def catalogues():
	from alphax_hr.api.banks import seed as seed_banks
	from alphax_hr.install import seed_catalogues, seed_gosi_rates, seed_settings

	seed_gosi_rates()
	seed_settings()
	seed_catalogues()
	seed_banks()
	return {"done": True}


def site():
	out = {}
	for key, fn in (("catalogues", catalogues), ("leave_types", leave_types), ("shift", shift)):
		_safe(fn, out, key)
	return out


# ------------------------------------------------------------------ per company
def holiday_list(company):
	"""This year and next with Friday and Saturday off and the Saudi public holidays; the company default."""
	if frappe.db.get_value("Company", company, "default_holiday_list"):
		return {"created": [], "kept": frappe.db.get_value("Company", company, "default_holiday_list")}
	from alphax_hr.api.holidays import WEEKDAYS, _rows_for, public_holidays

	year = getdate(nowdate()).year
	start, end = getdate(f"{year}-01-01"), getdate(f"{year + 1}-12-31")
	abbr = frappe.db.get_value("Company", company, "abbr") or company
	name = f"{abbr} Holidays {year}-{year + 1}"
	if not frappe.db.exists("Holiday List", name):
		public, _available = public_holidays(start, end)
		doc = frappe.get_doc({"doctype": "Holiday List", "holiday_list_name": name, "from_date": start, "to_date": end,
							  "holidays": _rows_for(start, end, [WEEKDAYS.index(w) for w in WEEKLY_OFF], public)})
		if doc.meta.has_field("country"):
			doc.country = "Saudi Arabia"
		doc.insert(ignore_permissions=True)
	frappe.db.set_value("Company", company, "default_holiday_list", name)
	return {"created": [name]}


def payroll_account(company):
	meta = frappe.get_meta("Company")
	if not meta.has_field("default_payroll_payable_account") or frappe.db.get_value("Company", company, "default_payroll_payable_account"):
		return {"created": []}
	acc = frappe.db.get_value("Account", {"company": company, "account_name": ["in", ["Payroll Payable", "Salaries Payable"]],
										   "is_group": 0}, "name")
	if acc:
		frappe.db.set_value("Company", company, "default_payroll_payable_account", acc)
		return {"linked": acc}
	return {"missing": True}


def company(name):
	out = {}
	for key, fn in (("holiday_list", lambda: holiday_list(name)), ("payroll_account", lambda: payroll_account(name))):
		_safe(fn, out, key)
	if not frappe.db.get_single_value("AlphaX HR Settings", "default_company"):
		frappe.db.set_single_value("AlphaX HR Settings", "default_company", name)
	return out


def on_company_created(doc, method=None):
	company(doc.name)


# ------------------------------------------------------------------ status and API
def status():
	"""What a new site still lacks, for Setup & health."""
	conf = frappe.get_single("AlphaX HR Settings")
	mapped = {r.rule for r in conf.leave_rules}
	from alphax_hr.api.leave_setup import STATUTORY_TYPES

	missing_leave = [n for k, (n, _c) in STATUTORY_TYPES.items() if k not in mapped]
	companies = frappe.get_all("Company", fields=["name", "default_holiday_list"])
	items = [
		{"key": "leave_types", "label": _("Saudi leave types and their rules"), "ok": not missing_leave and bool(conf.annual_leave_type),
		 "detail": ", ".join(missing_leave + ([] if conf.annual_leave_type else ["Annual Leave"]))},
		{"key": "components", "label": _("Salary components (basic, housing, transport, GOSI…)"),
		 "ok": bool(conf.get("salary_basic_component") and conf.get("salary_housing_component")), "detail": None},
		{"key": "shift", "label": _("At least one shift"), "ok": bool(frappe.get_all("Shift Type", limit=1)), "detail": None},
		{"key": "holiday_lists", "label": _("A default holiday list for every company"),
		 "ok": bool(companies) and all(c.default_holiday_list for c in companies),
		 "detail": ", ".join(c.name for c in companies if not c.default_holiday_list) or (None if companies else _("No company yet"))},
		{"key": "banks", "label": _("Saudi banks"), "ok": frappe.db.count("Bank") >= 5, "detail": None},
	]
	return {"items": items, "ready": all(i["ok"] for i in items)}


@frappe.whitelist()
def overview():
	from alphax_hr.api._common import require_hr

	require_hr()
	return status()


@frappe.whitelist(methods=["POST"])
def prepare():
	"""Create whatever is missing (site-wide and for every company). Safe to run again."""
	from alphax_hr.api._common import require_hr_manager

	require_hr_manager()
	out = {"site": site(), "companies": {c: company(c) for c in frappe.get_all("Company", pluck="name")}}
	frappe.clear_cache()
	return {**out, **status()}
