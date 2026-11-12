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
# words that identify a leave type whatever the site called it (English and Arabic); sibling before bereavement
KEYWORDS = [
	("Bereavement (Sibling)", ("sibling", "brother", "sister", "شقيق", "أخ ", "الأخ", "الأخت")),
	("Maternity", ("maternity", "أمومة", "الوضع", "ولادة")),
	("Paternity", ("paternity", "newborn", "new born", "child birth", "مولود", "أبوة")),
	("Marriage", ("marriage", "wedding", "زواج")),
	("Bereavement", ("bereavement", "death", "condolence", "وفاة", "عزاء")),
	("Iddah (Muslim)", ("iddah", "idda", "عدة", "العدة")),
	("Examination", ("exam", "examination", "امتحان", "اختبار")),
	("Hajj", ("hajj", "haj ", "حج")),
	("Sick", ("sick", "medical", "مرض", "مرضية")),
]
ANNUAL_WORDS = ("annual", "vacation", "سنوية", "اعتيادية")


def _match(kind, taken):
	"""An existing leave type that is clearly this kind (one match only, not already used)."""
	words = dict(KEYWORDS).get(kind)
	if not words:
		return None
	hits = []
	for lt in frappe.get_all("Leave Type", filters={"is_lwp": 0}, pluck="name"):
		if lt in taken:
			continue
		low = f" {lt.lower()} "
		if kind == "Bereavement" and any(w in low for w in dict(KEYWORDS)["Bereavement (Sibling)"]):
			continue
		if any(w in low for w in words):
			hits.append(lt)
	return hits[0] if len(hits) == 1 else None


def leave_plan():
	"""What Prepare defaults would do with leave types: link an existing one, or create the standard one."""
	from alphax_hr.api.leave_setup import STATUTORY_TYPES

	conf = frappe.get_single("AlphaX HR Settings")
	mapped = {r.rule for r in conf.leave_rules}
	taken = {r.leave_type for r in conf.leave_rules} | ({conf.annual_leave_type} if conf.annual_leave_type else set())
	plan = []
	for kind, (name, _days) in STATUTORY_TYPES.items():
		if kind in mapped:
			continue
		if frappe.db.exists("Leave Type", name) and name not in taken:
			plan.append({"kind": kind, "action": "link", "leave_type": name})
		elif hit := _match(kind, taken):
			plan.append({"kind": kind, "action": "link", "leave_type": hit})
		else:
			plan.append({"kind": kind, "action": "create", "leave_type": name})
		taken.add(plan[-1]["leave_type"])
	if not conf.annual_leave_type:
		hits = [lt for lt in frappe.get_all("Leave Type", filters={"is_lwp": 0}, pluck="name")
				if lt not in taken and any(w in lt.lower() for w in ANNUAL_WORDS)]
		used = frappe.db.sql("""select leave_type, count(*) n from `tabLeave Allocation` where docstatus=1 group by leave_type
			order by n desc limit 1""", as_dict=True)
		if len(hits) == 1:
			plan.append({"kind": "Annual", "action": "link", "leave_type": hits[0]})
		elif used and used[0].leave_type not in taken:  # the type the site already allocates most is its annual leave
			plan.append({"kind": "Annual", "action": "link", "leave_type": used[0].leave_type})
		else:
			plan.append({"kind": "Annual", "action": "create", "leave_type": "Annual Leave"})
	return plan


def leave_types():
	"""Statutory leave types (mapped to their rules) and Annual Leave: existing ones are linked, missing ones created."""
	from alphax_hr.api.leave_setup import STATUTORY_TYPES
	from alphax_hr.install import rule_row, seed_leave_rules
	from alphax_hr.saudi import leave_rules as lr

	seed_leave_rules()  # first map leave types that already exist under common names
	conf = frappe.get_single("AlphaX HR Settings")
	created, linked = [], []
	days_of = {k: d for k, (_n, d) in STATUTORY_TYPES.items()}
	for step in leave_plan():
		kind, name = step["kind"], step["leave_type"]
		if kind == "Annual":
			if step["action"] == "create" and not frappe.db.exists("Leave Type", name):
				frappe.get_doc({"doctype": "Leave Type", "leave_type_name": name, "is_lwp": 0, "allow_negative": 0,
								"include_holiday": 0, "is_carry_forward": 1}).insert(ignore_permissions=True)
				created.append(name)
			else:
				linked.append(name)
			conf.annual_leave_type = name
			continue
		if step["action"] == "create" and not frappe.db.exists("Leave Type", name):
			rule = lr.default_rule(kind)
			frappe.get_doc({"doctype": "Leave Type", "leave_type_name": name, "is_lwp": 0, "allow_negative": 1,
							"include_holiday": days_of[kind], "max_continuous_days_allowed": int(rule.max_days or 0)}
						   ).insert(ignore_permissions=True)
			created.append(name)
		else:
			linked.append(name)
		conf.append("leave_rules", rule_row(name, kind))
	conf.flags.ignore_permissions = True
	conf.save()
	return {"created": created, "linked": linked}


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
	return {"items": items, "ready": all(i["ok"] for i in items), "leave_plan": leave_plan(),
			"in_use": bool(frappe.db.count("Employee"))}


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
