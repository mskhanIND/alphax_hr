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


def _check(rows, group, key, status, value=None, detail=None, link=None, fix=None):
	rows.append({"group": group, "key": key, "status": status, "value": value,
				 "detail": detail if status != OK else None, "link": link, "fix": fix if status != OK else None})


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
	_check(rows, g, "default_company", OK if conf.default_company else WARN, conf.default_company or _("Not set"), None, None, fix="settings")
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
		   _("Create the current year's holiday list in the desk, then set it on these employees here."), "/app/holiday-list/new",
		   fix="employees")
	for key, field, label in (("leave_approver", "leave_approver", "No leave approver"),
							  ("shift_approver", "shift_request_approver", "No shift approver"),
							  ("reports_to", "reports_to", "No reporting manager"),
							  ("user_account", "user_id", "No user account")):
		n = sum(1 for e in emps if not e.get(field))
		_check(rows, g, key, OK if not n else WARN, f"{n}/{len(emps)}", _(label) if n else None, None, fix="employees")
	purposes = {r.purpose for r in conf.component_map}
	need = {"GOSI Basic", "GOSI Housing", "EOSB Wage"}
	_check(rows, g, "salary_mapping", OK if need <= purposes else ERROR, f"{len(need & purposes)}/{len(need)}",
		   (_("Map salary components for") + ": " + ", ".join(sorted(need - purposes))) if need - purposes else None, None, fix="settings")
	_check(rows, g, "annual_leave", OK if conf.annual_leave_type else WARN,
		   conf.annual_leave_type or _("Not set up"), None if conf.annual_leave_type else _("Set up Annual Leave in Leave setup."), "/leave-setup")
	rules = conf.leave_rules
	unalloc = [r.leave_type for r in rules if frappe.db.get_value("Leave Type", r.leave_type, "allow_negative") == 0
			   and not frappe.db.get_value("Leave Type", r.leave_type, "is_lwp")]
	_check(rows, g, "statutory_leave", WARN if (not rules or unalloc) else OK, f"{len(rules)} {_('rules')}",
		   (_("Need 'Allow without allocation'") + ": " + ", ".join(unalloc)) if unalloc else (None if rules else _("Create statutory leave types.")),
		   "/leave-setup", fix="allow_leave_types" if unalloc else None)
	year = today.year
	rates = frappe.db.count("GOSI Contribution Rate", {"effective_from": ["<=", today]}) if frappe.db.exists("DocType", "GOSI Contribution Rate") else 0
	_check(rows, g, "gosi_rates", OK if rates else ERROR, rates, None if rates else _("No GOSI rates in effect for {0}.").format(year))
	broken = broken_employee_links()
	n = sum(len(b["employees"]) for b in broken)
	_check(rows, g, "broken_links", WARN if broken else OK, n,
		   "; ".join(f"{b['label']} → {b['doctype']}: {', '.join(b['values'][:6])}{' …' if len(b['values']) > 6 else ''}" for b in broken) or None,
		   None, fix="create_missing_links" if any(b["creatable"] for b in broken) else None)


def _creatable_by_name(doctype):
	"""Field to set when a record of ``doctype`` can be created from its name alone (simple master lists)."""
	meta = frappe.get_meta(doctype)
	if meta.istable or meta.issingle or meta.is_submittable or meta.is_tree:
		return None
	reqd = [df.fieldname for df in meta.fields if df.reqd and not df.default]
	autoname = (meta.autoname or "").strip()
	if autoname.startswith("field:"):
		field = autoname.split(":", 1)[1]
		return field if set(reqd) <= {field} else None
	if autoname.lower() == "prompt" and not reqd:
		return "__name"
	return None


def broken_employee_links():
	"""Employee Link fields holding values that do not exist (e.g. a nationality removed from its list).
	Such records cannot be saved until the value exists again, so every edit of the employee fails."""
	meta = frappe.get_meta("Employee")
	out = []
	for df in meta.fields:
		if df.fieldtype != "Link" or not df.options or not frappe.db.has_column("Employee", df.fieldname):
			continue
		if not frappe.db.exists("DocType", df.options):
			continue
		table = f"tab{df.options}"
		rows = frappe.db.sql(f"""select e.`{df.fieldname}` v, group_concat(e.name) emps from `tabEmployee` e
			left join `{table}` t on t.name = e.`{df.fieldname}`
			where ifnull(e.`{df.fieldname}`, '') != '' and t.name is null group by e.`{df.fieldname}`""", as_dict=True)
		if rows:
			out.append({"field": df.fieldname, "label": _(df.label or df.fieldname), "doctype": df.options,
						"values": [r.v for r in rows], "employees": sorted({x for r in rows for x in (r.emps or "").split(",") if x}),
						"creatable": bool(_creatable_by_name(df.options))})
	return out


@frappe.whitelist(methods=["POST"])
def create_missing_links():
	"""Create the missing master records (e.g. Employee Nationality "Egyptian") so those employees can be saved again."""
	require_hr_manager()
	created, skipped = [], []
	for b in broken_employee_links():
		field = _creatable_by_name(b["doctype"])
		for v in b["values"]:
			if not field:
				skipped.append(f"{b['doctype']}: {v}")
				continue
			doc = frappe.new_doc(b["doctype"])
			if field == "__name":
				doc.name = v
				doc.flags.name_set = True
			else:
				doc.set(field, v)
			doc.insert()
			created.append(f"{b['doctype']}: {v}")
	return {"created": created, "skipped": skipped}


def _require_system_manager():
	if "System Manager" not in frappe.get_roles():
		frappe.throw(_("System health is only visible to System Managers."), frappe.PermissionError)


def _run(fns):
	rows = []
	for fn in fns:
		try:
			fn(rows)
		except Exception as exc:  # one broken check must not hide the others
			_check(rows, _("Checks"), "check_failed", ERROR, None, str(exc)[:300])
	counts = {s: sum(1 for r in rows if r["status"] == s) for s in (OK, WARN, ERROR)}
	return {"checks": rows, "counts": counts, "as_of": str(now_datetime())}


def _require_hr_lead():
	if not set(frappe.get_roles()) & {"HR Manager", "System Manager"}:
		frappe.throw(_("Only HR Managers can see the HR status."), frappe.PermissionError)


# ----------------------------------------------------------------- HR operational status
EMPLOYEE_FIXES = {  # check key -> (Employee field, Link doctype) for bulk setting
	"holiday_lists": ("holiday_list", "Holiday List"),
	"leave_approver": ("leave_approver", "User"),
	"shift_approver": ("shift_request_approver", "User"),
	"reports_to": ("reports_to", "Employee"),
}


def _hr_operational_checks(rows):
	g = _("Workforce & operations")
	today = getdate(nowdate())
	from alphax_hr.api.compliance import expiring_documents

	docs = expiring_documents(30)
	expired = [d for d in docs if d["days_left"] < 0]
	_check(rows, g, "documents_expired", ERROR if expired else OK, len(expired),
		   _("Iqama, work permit, passport or contract already expired."), None, fix="employees")
	soon = [d for d in docs if d["days_left"] >= 0]
	_check(rows, g, "documents_expiring", WARN if soon else OK, len(soon), _("Expiring within 30 days."), None, fix="employees")
	missing = len(_employees_missing_mandatory())
	_check(rows, g, "mandatory_missing", WARN if missing else OK, missing,
		   _("Employees that cannot be saved until mandatory fields are filled."), None, fix="employees")
	no_salary = len(_employees_without_salary())
	_check(rows, g, "no_salary", WARN if no_salary else OK, no_salary, _("Active employees without a salary assignment."), None, fix="employees")
	from alphax_hr.api.approvals import SOURCES

	old = 0
	for dt, conf in SOURCES.items():
		if frappe.db.exists("DocType", dt):
			old += frappe.db.count(dt, {"docstatus": 0, "creation": ["<", add_days(today, -3)], **conf["open"]})
	_check(rows, g, "approvals_waiting", WARN if old else OK, old, _("Requests waiting for a decision for more than 3 days."), "/approvals")


def _active_employees(fields):
	return frappe.get_all("Employee", filters={"status": "Active"}, fields=["name", "employee_name", "department", *fields],
						  order_by="employee_name asc", limit_page_length=10000)


def _employees_missing_mandatory():
	from alphax_hr.api.hr import _mirror_map, _site_required_fields

	meta = frappe.get_meta("Employee")
	req = [df.fieldname for df in _site_required_fields(meta) if df.fieldname not in _mirror_map(meta)]
	out = []
	for e in _active_employees(req):
		gaps = [meta.get_label(f) for f in req if e.get(f) in (None, "")]
		if gaps:
			out.append({**e, "note": ", ".join(gaps[:4]) + (f" +{len(gaps) - 4}" if len(gaps) > 4 else "")})
	return out


def _employees_without_salary():
	with_salary = set(frappe.get_all("Salary Structure Assignment", filters={"docstatus": 1}, pluck="employee", distinct=True))
	return [e for e in _active_employees([]) if e.name not in with_salary]


@frappe.whitelist()
def affected(key):
	"""Employees behind one HR status check, with what is wrong for each."""
	_require_hr_lead()
	today = getdate(nowdate())
	if key in EMPLOYEE_FIXES:
		field, link = EMPLOYEE_FIXES[key]
		rows = _active_employees([field, "company"])
		if key == "holiday_lists":
			ends = {h.name: getdate(h.to_date) for h in frappe.get_all("Holiday List", fields=["name", "to_date"])}
			def bad(e):
				hl = e.holiday_list or frappe.get_cached_value("Company", e.company, "default_holiday_list")
				return not hl or hl not in ends or ends[hl] < add_days(today, 60)
			rows = [{**e, "note": e.holiday_list or _("Company default")} for e in rows if bad(e)]
			current = [h.name for h in frappe.get_all("Holiday List", filters={"from_date": ["<=", today], "to_date": [">=", today]},
														fields=["name"]) if not frappe.db.get_value("Holiday List", h.name, "alphax_employee")]
		else:
			rows = [{**e, "note": None} for e in rows if not e.get(field)]
			current = []
		return {"key": key, "rows": rows, "set_field": field, "link_doctype": link, "suggestions": current}
	if key == "user_account":
		return {"key": key, "rows": [{**e, "note": e.company_email or e.personal_email or _("No email")}
									 for e in _active_employees(["user_id", "company_email", "personal_email"]) if not e.user_id]}
	if key in ("documents_expired", "documents_expiring"):
		from alphax_hr.api.compliance import expiring_documents

		docs = [d for d in expiring_documents(30) if (d["days_left"] < 0) == (key == "documents_expired")]
		return {"key": key, "rows": [{"name": d["employee"], "employee_name": d["employee_name"], "department": d["department"],
									  "note": f"{_(d['document'])}: {d['expiry']} ({d['days_left']} {_('days')})"} for d in docs]}
	if key == "mandatory_missing":
		return {"key": key, "rows": _employees_missing_mandatory()}
	if key == "no_salary":
		return {"key": key, "rows": [{**e, "note": None} for e in _employees_without_salary()]}
	frappe.throw(_("Unknown check."))


@frappe.whitelist()
def bulk_fix(key, employees, value):
	"""Set one field (approver, manager, holiday list) on many employees. Each save is validated and audited;
	other missing mandatory data does not block this one change."""
	require_hr_manager()
	if key not in EMPLOYEE_FIXES:
		frappe.throw(_("This check cannot be fixed in bulk."))
	field, link = EMPLOYEE_FIXES[key]
	if not value or not frappe.db.exists(link, value):
		frappe.throw(_("Choose a valid {0}.").format(_(link)))
	done, failed = [], []
	for emp in parse_json(employees, [])[:1000]:
		frappe.db.savepoint("alphax_fix")
		try:
			doc = frappe.get_doc("Employee", emp)
			doc.check_permission("write")
			if field == "reports_to" and value == emp:
				raise frappe.ValidationError(_("An employee cannot report to themselves."))
			doc.set(field, value)
			doc.flags.ignore_mandatory = True
			# Only this field changes and its value was checked above; other stale links on the record
			# (e.g. a nationality missing from its list) must not block it.
			doc.flags.ignore_links = True
			doc.save()
			done.append(emp)
		except Exception as exc:
			frappe.db.rollback(save_point="alphax_fix")
			frappe.clear_messages()
			failed.append({"employee": emp, "error": str(exc)[:300]})
	return {"done": done, "failed": failed}


@frappe.whitelist()
def allow_statutory_without_allocation():
	require_hr_manager()
	from alphax_hr.api import leave_setup

	changed = []
	for r in settings().leave_rules:
		lt = frappe.db.get_value("Leave Type", r.leave_type, ["allow_negative", "is_lwp"], as_dict=True)
		if lt and not lt.allow_negative and not lt.is_lwp:
			leave_setup.allow_without_allocation(r.leave_type)
			changed.append(r.leave_type)
	return {"changed": changed}


@frappe.whitelist()
def health():
	"""Technical status of the site (System Managers only)."""
	_require_system_manager()
	return _run([_system_checks])


def _file_missing(url):
	"""True when a /files or /private/files URL has no file on this site (PDFs then fail with 'broken image links')."""
	import os
	from urllib.parse import unquote, urlparse

	path = unquote(urlparse(url).path)
	if path.startswith("/private/files/"):
		return not os.path.exists(frappe.get_site_path("private", "files", path[len("/private/files/"):]))
	if path.startswith("/files/"):
		return not os.path.exists(frappe.get_site_path("public", "files", path[len("/files/"):]))
	return False


def broken_print_images():
	"""Images used by letter heads, payslip print formats and the site logo that point to missing files."""
	import re

	found = []
	urls = re.compile(r"""(?:src|href)=["']([^"']+)["']|url\(["']?([^"')]+)""")

	def scan(where, link, *texts):
		for text in texts:
			for m in urls.finditer(text or ""):
				u = m.group(1) or m.group(2)
				if u and _file_missing(u):
					found.append({"where": where, "url": u, "link": link})
			if text and str(text).startswith(("/files/", "/private/files/")) and _file_missing(text):
				found.append({"where": where, "url": text, "link": link})

	for lh in frappe.get_all("Letter Head", filters={"disabled": 0}, fields=["name", "image", "content", "footer", "footer_image"]):
		scan(_("Letter Head {0}").format(lh.name), f"/app/letter-head/{lh.name}", lh.image, lh.content, lh.footer, lh.footer_image)
	for pf in frappe.get_all("Print Format", filters={"doc_type": "Salary Slip", "disabled": 0}, fields=["name", "html", "css"]):
		scan(_("Print Format {0}").format(pf.name), f"/app/print-format/{pf.name}", pf.html, pf.css)
	for field in ("app_logo", "banner_image", "favicon", "splash_image"):
		v = frappe.db.get_single_value("Website Settings", field) if frappe.get_meta("Website Settings").has_field(field) else None
		scan(_("Website Settings: {0}").format(field), "/app/website-settings", v)
	seen, out = set(), []
	for f in found:
		if (f["where"], f["url"]) not in seen:
			seen.add((f["where"], f["url"]))
			out.append(f)
	return out


def _print_checks(rows):
	g = _("Documents & printing")
	broken = broken_print_images()
	_check(rows, g, "print_images", WARN if broken else OK, len(broken),
		   "; ".join(f"{b['where']}: {b['url']}" for b in broken[:8]) or None,
		   broken[0]["link"] if broken and "System Manager" in frappe.get_roles() else None)


@frappe.whitelist()
def hr_status():
	"""Overall HR status for HR Managers: data gaps, documents, approvals, leave and payroll setup."""
	_require_hr_lead()
	return _run([_hr_checks, _hr_operational_checks, _print_checks])


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
