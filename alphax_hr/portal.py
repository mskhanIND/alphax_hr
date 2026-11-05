"""HR portal enforcement and page access.

- Users without a desk role are kept in /alphax (opening /app redirects them there) when HR turns it on.
- Guests opening /login get the AlphaX sign-in page (optional).
- HR can hide AlphaX pages or limit them to roles; the frontend reads the result from the session boot.
"""
from __future__ import annotations

import frappe
from frappe import _

ALWAYS_DESK = {"Administrator"}
DESK_PATHS = ("/app", "/desk")


def _conf():
	try:
		return frappe.get_cached_doc("AlphaX HR Settings")
	except Exception:  # noqa: BLE001 - before install / during migrate
		return None


def desk_roles(conf=None):
	conf = conf or _conf()
	text = (conf.get("desk_roles") if conf else None) or "System Manager"
	return {r.strip() for r in text.splitlines() if r.strip()}


def may_use_desk(user=None, conf=None):
	user = user or frappe.session.user
	if user in ALWAYS_DESK:
		return True
	conf = conf or _conf()
	if not conf or not conf.get("enforce_portal"):
		return True
	return bool(set(frappe.get_roles(user)) & desk_roles(conf))


def after_request(response=None, request=None):
	"""Redirect portal users away from the desk, and guests from /login to the AlphaX sign-in page."""
	if response is None or request is None or request.method != "GET":
		return
	path = request.path or ""
	try:
		user = frappe.session.user
	except Exception:  # noqa: BLE001
		return
	conf = None
	if path == "/login" and user == "Guest" and not request.args.get("standard"):
		conf = _conf()
		if conf and conf.get("use_alphax_login") and response.status_code == 200:
			target = "/alphax-login"
			if request.args.get("redirect-to"):
				target += "?redirect-to=" + frappe.utils.quote(request.args.get("redirect-to"), safe="")
			_redirect(response, target)
		return
	if user != "Guest" and any(path == p or path.startswith(p + "/") for p in DESK_PATHS):
		if not may_use_desk(user):
			_redirect(response, "/alphax")


def _redirect(response, location):
	response.status_code = 302
	response.headers["Location"] = location
	response.set_data(b"")


def landing_path(user=None):
	"""Where a user goes after signing in: the desk only for desk roles, everyone else /alphax."""
	user = user or frappe.session.user
	if user in ALWAYS_DESK or set(frappe.get_roles(user)) & desk_roles():
		return "/app"
	return "/alphax"


# ------------------------------------------------------------------ pages
def page_rules():
	conf = _conf()
	return [{"page": r.page, "hidden": int(r.hidden or 0),
			 "roles": [x.strip() for x in (r.roles or "").splitlines() if x.strip()]} for r in (conf.get("page_access") or [])] if conf else []


def hidden_pages(user=None):
	"""Paths this user must not see (hidden for everyone, or limited to roles the user lacks)."""
	user = user or frappe.session.user
	if user == "Administrator":
		return []
	roles = set(frappe.get_roles(user))
	out = []
	for r in page_rules():
		if r["hidden"] or (r["roles"] and not roles & set(r["roles"])):
			out.append(r["page"])
	return out


def sync_default_app(conf):
	"""Portal on: users land on /alphax after sign-in (System Settings default app)."""
	if conf.get("enforce_portal") and frappe.get_meta("System Settings").has_field("default_app"):
		if frappe.db.get_single_value("System Settings", "default_app") != "alphax_hr":
			frappe.db.set_single_value("System Settings", "default_app", "alphax_hr")


# Pages HR can hide or limit (path, label, area). Paths match the AlphaX menu.
PAGES = [
	("/me/services", "Services", "Self service"), ("/me/requests", "My Requests", "Self service"), ("/me/help", "Help centre", "Self service"),
	("/me/leave", "My Leave", "Self service"), ("/me/vacation-plan", "Vacation plan", "Self service"),
	("/me/attendance", "My Attendance", "Self service"), ("/me/payslips", "My Payslips", "My pay"), ("/me/loans", "My loans", "My pay"),
	("/me/expenses", "My expenses", "My pay"), ("/me/profile", "My Profile", "My file"), ("/me/documents", "My documents", "My file"),
	("/me/performance", "My performance", "My file"), ("/me/warnings", "My warnings", "My file"),
	("/approvals", "Approvals", "Manager"), ("/approval-delays", "Approval delays", "Manager"), ("/my-team", "My team", "Manager"),
	("/team-appraisals", "Team appraisals", "Manager"), ("/vacation-planner", "Vacation planner", "Manager"), ("/team", "Team Calendar", "Manager"),
	("/people", "Employees", "People"), ("/people/bulk-update", "Bulk update", "People"), ("/announcements", "Announcements", "People"),
	("/knowledge", "Help centre articles", "People"), ("/requests", "Requests", "People"), ("/penalties", "Warnings & penalties", "People"),
	("/appraisals", "Appraisals", "People"), ("/compliance", "Compliance", "People"),
	("/roster", "Roster", "Time & attendance"), ("/attendance", "Attendance", "Time & attendance"),
	("/checkins", "Check-ins & movements", "Time & attendance"), ("/work-locations", "Work locations", "Time & attendance"),
	("/attendance-devices", "Attendance devices", "Time & attendance"), ("/holiday-lists", "Holiday lists", "Time & attendance"), ("/approval-policies", "Approval policies", "Administration"),
	("/attendance-policies", "Attendance exceptions", "Time & attendance"), ("/leave-balances", "Leave balances", "Leave"),
	("/payroll", "Payroll control centre", "Payroll"), ("/payroll/loans", "Loans & advances", "Payroll"),
	("/payroll/adjustments", "Bonuses & deductions", "Payroll"), ("/payroll/accruals", "Accruals (leave & end of service)", "Payroll"),
	("/payroll/settlements", "Final settlements", "Payroll"), ("/payroll/gosi", "GOSI Register", "Payroll"),
	("/payroll/eosb", "End of Service", "Payroll"), ("/leave-setup", "Leave setup", "Administration"),
	("/notifications-setup", "Notifications", "Administration"), ("/cutover", "Cut-over readiness", "Administration"),
	("/activity", "Activity log", "Administration"),
]


@frappe.whitelist()
def pages():
	from alphax_hr.api._common import require_hr

	require_hr()
	rules = {r["page"]: r for r in page_rules()}
	roles = sorted(r for r in frappe.get_all("Role", filters={"disabled": 0}, pluck="name")
				   if r not in ("Guest", "All", "Administrator", "Desk User"))
	return {"pages": [{"page": p, "label": label, "area": area, "hidden": rules.get(p, {}).get("hidden", 0),
					   "roles": rules.get(p, {}).get("roles", [])} for p, label, area in PAGES],
			"roles": roles, "can_edit": bool(set(frappe.get_roles()) & {"HR Manager", "System Manager"})}


@frappe.whitelist(methods=["POST"])
def save_pages(rows: str | dict | list):
	from alphax_hr.api._common import parse_json, require_hr_manager

	require_hr_manager()
	known = {p: label for p, label, _a in PAGES}
	conf = frappe.get_single("AlphaX HR Settings")
	conf.set("page_access", [])
	for r in parse_json(rows) or []:
		if r.get("page") in known and (r.get("hidden") or r.get("roles")):
			conf.append("page_access", {"page": r["page"], "label": known[r["page"]], "hidden": 1 if r.get("hidden") else 0,
										"roles": "\n".join(x for x in (r.get("roles") or []) if x)})
	if any(r.page == "/setup" for r in conf.page_access):
		frappe.throw(_("HR status & setup cannot be hidden."))
	conf.flags.ignore_permissions = True
	conf.save()
	frappe.clear_document_cache("AlphaX HR Settings", "AlphaX HR Settings")
	return pages()


@frappe.whitelist()
def landing():
	"""Where to go after signing in on the AlphaX page."""
	return landing_path()
