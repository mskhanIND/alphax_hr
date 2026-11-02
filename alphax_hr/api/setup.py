"""Setup & health: one place for AlphaX settings and the HR system's health checks."""
from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import add_days, cint, get_datetime, getdate, now_datetime, nowdate

from alphax_hr.api._common import parse_json, require_hr, require_hr_manager, settings

SETTINGS = "AlphaX HR Settings"
# Settings edited on their own pages (or tables) are not repeated in the generic form.
SKIP = {"leave_rules", "annual_leave_type", "annual_auto_allocate", "annual_policy", "annual_fixed_days",
		"annual_base_days", "annual_senior_days", "annual_senior_after_years", "annual_senior_count_from",
		"leave_escalation_hours"}
OK, WARN, ERROR = "ok", "warn", "error"


def _check(rows, group, key, status, value=None, detail=None, link=None):
	rows.append({"group": group, "key": key, "status": status, "value": value,
				 "detail": detail if status != OK else None, "link": link})


def _system_checks(rows):
	g = "System"
	from frappe.utils.scheduler import is_scheduler_disabled, is_scheduler_inactive

	try:
		disabled = is_scheduler_disabled(verbose=False)
	except TypeError:
		disabled = is_scheduler_disabled()
	_check(rows, g, "scheduler", ERROR if disabled else (WARN if is_scheduler_inactive() else OK),
		   _("Disabled") if disabled else _("Running"),
		   _("Without the scheduler: no annual leave allocation, escalations or expiry alerts. Run: bench --site SITE enable-scheduler")
		   if disabled else None)
	try:
		from frappe.utils.background_jobs import get_workers

		workers = len(get_workers())
		_check(rows, g, "workers", OK if workers else ERROR, workers,
			   None if workers else _("No background workers: emails, exports and jobs will not run."))
	except Exception as exc:
		_check(rows, g, "workers", WARN, None, str(exc)[:200])
	jobs = frappe.get_all("Scheduled Job Type", filters={"method": ["like", "alphax_hr.%"]},
						  fields=["method", "frequency", "last_execution", "stopped"])
	stale = []
	for j in jobs:
		limit = 2 if j.frequency in ("Hourly", "Hourly Long") else 26
		if j.stopped or not j.last_execution or (now_datetime() - get_datetime(j.last_execution)).total_seconds() > limit * 3600:
			stale.append(j.method.split(".")[-1])
	_check(rows, g, "alphax_jobs", WARN if stale else OK, f"{len(jobs) - len(stale)}/{len(jobs)}",
		   (_("Not run recently") + ": " + ", ".join(stale)) if stale else None)
	failed = frappe.get_all("Scheduled Job Log", filters={"status": "Failed", "creation": [">=", add_days(now_datetime(), -1)],
														  "scheduled_job_type": ["like", "alphax_hr.%"]}, pluck="scheduled_job_type")
	if failed:
		_check(rows, g, "alphax_job_failures", ERROR, len(failed), ", ".join(sorted(set(failed))))
	errors = frappe.db.count("Error Log", {"creation": [">=", add_days(now_datetime(), -1)]})
	_check(rows, g, "error_log_24h", OK if errors < 10 else WARN, errors,
		   _("Check Error Log in the desk.") if errors >= 10 else None, "/app/error-log")
	outgoing = frappe.db.exists("Email Account", {"default_outgoing": 1, "enable_outgoing": 1})
	_check(rows, g, "outgoing_email", OK if outgoing else WARN, _("Configured") if outgoing else _("Missing"),
		   None if outgoing else _("Notifications (leave decisions, expiry alerts) cannot be emailed."), "/app/email-account")
	from alphax_hr.install import ROW_LIMIT, employee_row_size

	import contextlib
	import io

	with contextlib.redirect_stdout(io.StringIO()):
		used = employee_row_size()["used"]
	pct = round(100 * used / ROW_LIMIT)
	_check(rows, g, "employee_row_size", ERROR if pct >= 97 else WARN if pct >= 90 else OK, f"{pct}%",
		   _("The Employee table is close to MariaDB's row limit; new custom fields from any app may fail to install.") if pct >= 90 else None)


def _hr_checks(rows):
	g = "HR data"
	conf = settings()
	today = getdate(nowdate())
	_check(rows, g, "default_company", OK if conf.default_company else WARN, conf.default_company or _("Not set"), None, "/setup#settings")
	emps = frappe.get_all("Employee", filters={"status": "Active"},
						  fields=["name", "holiday_list", "company", "leave_approver", "shift_request_approver", "reports_to", "user_id"])
	total = len(emps) or 1
	lists = {h.name: h for h in frappe.get_all("Holiday List", fields=["name", "to_date"])}
	ending, outdated = set(), 0
	for e in emps:
		hl = e.holiday_list or frappe.get_cached_value("Company", e.company, "default_holiday_list")
		end = getdate(lists[hl].to_date) if hl in lists else None
		if not end or end < today:
			outdated += 1
		elif end < add_days(today, 60):
			ending.add(hl)
	_check(rows, g, "holiday_lists", ERROR if outdated else WARN if ending else OK,
		   f"{outdated} {_('employees on an outdated list')}" if outdated else (", ".join(sorted(ending)) if ending else _("Current")),
		   _("Create next year's holiday list and set it on the company (and employees)."), "/compliance?open=holiday_list_missing_or_outdated")
	for key, field, label in (("leave_approver", "leave_approver", "No leave approver"),
							  ("shift_approver", "shift_request_approver", "No shift approver"),
							  ("reports_to", "reports_to", "No reporting manager"),
							  ("user_account", "user_id", "No user account")):
		n = sum(1 for e in emps if not e.get(field))
		_check(rows, g, key, OK if not n else WARN, f"{n}/{len(emps)}", _(label) if n else None,
			   "/people?view=org" if key == "reports_to" else "/compliance")
	purposes = {r.purpose for r in conf.component_map}
	need = {"GOSI Basic", "GOSI Housing", "EOSB Wage"}
	_check(rows, g, "salary_mapping", OK if need <= purposes else ERROR, f"{len(need & purposes)}/{len(need)}",
		   (_("Map salary components for") + ": " + ", ".join(sorted(need - purposes))) if need - purposes else None, "/setup#settings")
	_check(rows, g, "annual_leave", OK if conf.annual_leave_type else WARN,
		   conf.annual_leave_type or _("Not set up"), None if conf.annual_leave_type else _("Set up Annual Leave in Leave setup."), "/leave-setup")
	rules = conf.leave_rules
	unalloc = [r.leave_type for r in rules if frappe.db.get_value("Leave Type", r.leave_type, "allow_negative") == 0
			   and not frappe.db.get_value("Leave Type", r.leave_type, "is_lwp")]
	_check(rows, g, "statutory_leave", WARN if (not rules or unalloc) else OK, f"{len(rules)} {_('rules')}",
		   (_("Need 'Allow without allocation'") + ": " + ", ".join(unalloc)) if unalloc else (None if rules else _("Create statutory leave types.")),
		   "/leave-setup")
	year = today.year
	rates = frappe.db.count("GOSI Contribution Rate", {"effective_from": ["<=", today]}) if frappe.db.exists("DocType", "GOSI Contribution Rate") else 0
	_check(rows, g, "gosi_rates", OK if rates else ERROR, rates, None if rates else _("No GOSI rates in effect for {0}.").format(year))


@frappe.whitelist()
def health():
	require_hr()
	rows = []
	for fn in (_system_checks, _hr_checks):
		try:
			fn(rows)
		except Exception as exc:  # one broken check must not hide the others
			_check(rows, fn.__name__.strip("_").replace("_checks", "").title(), "check_failed", ERROR, None, str(exc)[:300])
	from frappe.utils.change_log import get_versions

	versions = {app: v.get("version") for app, v in get_versions().items()}
	counts = {s: sum(1 for r in rows if r["status"] == s) for s in (OK, WARN, ERROR)}
	return {"checks": rows, "counts": counts, "versions": versions, "site": frappe.local.site, "as_of": str(now_datetime())}


def _spec(df):
	spec = {"fieldname": df.fieldname, "label": _(df.label or df.fieldname), "fieldtype": df.fieldtype,
			"description": _(df.description) if df.description else None, "default": df.default}
	if df.fieldtype == "Select":
		spec["options"] = (df.options or "").split("\n")
	elif df.fieldtype == "Link":
		spec["options"] = df.options
	return spec


@frappe.whitelist()
def get_settings():
	require_hr()
	doc = frappe.get_single(SETTINGS)
	sections, current = [], None
	for df in doc.meta.fields:
		if df.fieldtype == "Section Break":
			current = {"key": df.fieldname, "label": _(df.label or ""), "fields": []}
			sections.append(current)
			continue
		if df.fieldtype in ("Column Break", "Tab Break") or df.fieldname in SKIP or df.fieldtype == "Table":
			continue
		if current is None:
			current = {"key": "general", "label": _("General"), "fields": []}
			sections.append(current)
		current["fields"].append(_spec(df))
	values = {f["fieldname"]: doc.get(f["fieldname"]) for s in sections for f in s["fields"]}
	return {"sections": [s for s in sections if s["fields"]], "values": values,
			"component_map": [{"salary_component": r.salary_component, "purpose": r.purpose} for r in doc.component_map],
			"purposes": doc.meta.get_field("component_map") and frappe.get_meta("AlphaX Salary Component Map").get_field("purpose").options.split("\n"),
			"can_edit": bool(set(frappe.get_roles()) & {"HR Manager", "System Manager"})}


@frappe.whitelist()
def save_settings(data):
	require_hr_manager()
	payload = parse_json(data, {})
	doc = frappe.get_single(SETTINGS)
	editable = {df.fieldname for df in doc.meta.fields
				if df.fieldtype not in ("Section Break", "Column Break", "Tab Break", "Table") and df.fieldname not in SKIP}
	for k, v in (payload.get("values") or {}).items():
		if k in editable:
			doc.set(k, v)
	if "component_map" in payload:
		doc.set("component_map", [])
		for row in payload["component_map"] or []:
			if row.get("salary_component") and row.get("purpose"):
				doc.append("component_map", {"salary_component": row["salary_component"], "purpose": row["purpose"]})
	doc.save()
	if cint(doc.passport_non_saudi_only):
		from alphax_hr.install import apply_field_rules

		apply_field_rules()
	return get_settings()
