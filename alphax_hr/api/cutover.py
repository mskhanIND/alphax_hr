"""Cut-over from CentralHRMS (or any legacy HR app) to AlphaX.

readiness(): what still depends on the old app, and what AlphaX still needs, before it is uninstalled.
import_legacy(): copy legacy requests, warning letters and identity data into AlphaX (dry-run first;
idempotent: every imported record remembers where it came from).
"""
from __future__ import annotations

import json

import frappe
from frappe import _
from frappe.utils import cint, getdate

from alphax_hr.api._common import require_hr_manager, settings

LEGACY_APPS = ("centralhrms", "central_hrms", "centralhrms_app", "iqama_management")
LEGACY_MODULES = ("CentralHrms", "Iqama Management", "Attendance Logic")

# legacy request doctype -> AlphaX request type
LEGACY_REQUESTS = {
	"Letters Request": "Employment Letter",
	"Exit ReEntry Request": "Exit & Re-entry Visa",
	"Final Exit Request": "Final Exit Visa",
	"Business Travel Request": "Business Trip",
	"Assets Request": "Asset Request",
	"Housing Advance Request": "Salary Advance",
	"Contract Termination Request": "Resignation",
	"Iqama Request": "Iqama Renewal",
	"Urgent Request": "General Request",
	"Health Insurance Upgrade Request": "General Request",
	"Transfer of Iqama Request": "General Request",
	"Accommodation Request": "General Request",
	"Request for Profession Change": "General Request",
	"Generate Flight Ticket Booking Request": "General Request",
	"Family Visit Visa Request": "General Request",
	"Annual Ticket Request": "General Request",
	"Generate Visa Request": "General Request",
	"Leave Deduction Request": "General Request",
	"Employee Info Update Request": "General Request",
	"Contract Renewal Request": "General Request",
	"Overtime Request": "General Request",
	"Overtime Sheet Request": "General Request",
}
WARNING_DOCTYPES = ("Warning Letter",)
SKIP = {"naming_series", "amended_from", "employee", "employee_name", "name_in_arabic", "docstatus", "idx", "owner", "modified_by",
		"creation", "modified", "name", "doctype", "workflow_state", "series", "employee_no"}
IMPORTED_VIOLATION = "Warning (imported)"


def _exists(dt):
	return bool(frappe.db.exists("DocType", dt))


def _legacy_apps():
	return [a for a in frappe.get_installed_apps() if a in LEGACY_APPS or "central" in a.lower()]


def _item(key, label, status, detail=None, count=None, action=None, link=None):
	return {"key": key, "label": label, "status": status, "detail": detail, "count": count, "action": action, "link": link}


def _imported(prefix):
	return set(frappe.get_all("AlphaX Request", filters={"legacy_ref": ["like", f"{prefix}%"]}, pluck="legacy_ref"))


@frappe.whitelist()
def readiness():
	require_hr_manager()
	items = []
	apps = _legacy_apps()
	items.append(_item("legacy_apps", _("Legacy HR apps installed"), "info" if apps else "ok", ", ".join(apps) or _("None")))

	# 1. legacy data still to bring over
	req_total = req_left = 0
	per_type = []
	for dt, target in LEGACY_REQUESTS.items():
		if not _exists(dt):
			continue
		names = frappe.get_all(dt, pluck="name")
		done = _imported(f"{dt}:")
		left = [n for n in names if f"{dt}:{n}" not in done]
		req_total += len(names)
		req_left += len(left)
		per_type.append({"doctype": dt, "target": target, "records": len(names), "left": len(left)})
	items.append(_item("requests", _("Employee requests to import"), "todo" if req_left else "ok",
					   _("{0} of {1} legacy request(s) not yet in AlphaX").format(req_left, req_total), req_left, "requests"))
	warn_total = warn_left = 0
	for dt in WARNING_DOCTYPES:
		if _exists(dt):
			names = frappe.get_all(dt, pluck="name")
			done = set(frappe.get_all("AlphaX Penalty", filters={"source_ref": ["like", f"{dt}:%"]}, pluck="source_ref"))
			warn_total += len(names)
			warn_left += sum(1 for n in names if f"{dt}:{n}" not in done)
	items.append(_item("warnings", _("Warning letters to import"), "todo" if warn_left else "ok",
					   _("{0} of {1} not yet in AlphaX").format(warn_left, warn_total), warn_left, "warnings"))
	from alphax_hr.api.compliance import import_legacy_fields

	ident = import_legacy_fields(dry_run=1)["employees"] + len(_iqama_plan())
	items.append(_item("identity", _("Iqama / ID values still only in legacy fields"), "todo" if ident else "ok",
					   _("{0} employee(s)").format(ident), ident, "identity"))

	# 2. legacy custom fields on standard doctypes that hold data (removed with the app)
	legacy_fields = frappe.get_all("Custom Field", filters={"module": ["in", list(LEGACY_MODULES)]},
								   fields=["dt", "fieldname", "label", "fieldtype"])
	from alphax_hr.api.hr import _mirror_map

	mirrors = _mirror_map(frappe.get_meta("Employee")) if frappe.get_meta("Employee") else {}
	at_risk = []
	for cf in legacy_fields:
		if cf.fieldtype in ("Section Break", "Column Break", "Tab Break", "HTML", "Button", "Table", "Table MultiSelect"):
			continue
		if not frappe.db.has_column(cf.dt, cf.fieldname):
			continue
		n = frappe.db.count(cf.dt, {cf.fieldname: ["is", "set"]})
		if n and not (cf.dt == "Employee" and cf.fieldname in mirrors):
			at_risk.append({"doctype": cf.dt, "fieldname": cf.fieldname, "label": cf.label, "records": n})
	items.append(_item("legacy_fields", _("Legacy custom fields holding data without an AlphaX home"), "warn" if at_risk else "ok",
					   json.dumps(at_risk[:50], ensure_ascii=False) if at_risk else None, len(at_risk), None, "/setup?tab=fields"))

	# 3. workflows on HRMS doctypes (AlphaX approves through them, but check they are intended)
	wfs = frappe.get_all("Workflow", filters={"is_active": 1, "document_type": ["in", ["Leave Application", "Expense Claim", "Shift Request",
																					  "Attendance Request", "Employee Advance"]]},
						 fields=["name", "document_type"])
	items.append(_item("workflows", _("Active workflows on HR documents"), "info" if wfs else "ok",
					   ", ".join(f"{w.document_type}: {w.name}" for w in wfs) or None, len(wfs)))

	# 4. AlphaX ready to run on its own
	conf = settings()
	items.append(_item("annual_leave", _("Annual leave type set up"), "ok" if conf.annual_leave_type else "todo", None, None, None, "/leave-setup"))
	items.append(_item("salary_components", _("Salary components mapped"), "ok" if conf.salary_basic_component else "todo", None, None, None, "/setup"))
	items.append(_item("request_types", _("Request types available"), "ok" if frappe.db.count("AlphaX Request Type", {"enabled": 1}) else "todo"))
	items.append(_item("violations", _("Violations schedule available"), "ok" if frappe.db.count("AlphaX Violation Type", {"enabled": 1}) else "todo",
					   None, None, None, "/penalties"))
	no_payable = [c for c in frappe.get_all("Company", pluck="name") if not frappe.db.get_value("Company", c, "default_payroll_payable_account")]
	items.append(_item("payroll_account", _("Payroll payable account on every company"), "todo" if no_payable else "ok",
					   ", ".join(no_payable) or None, len(no_payable)))

	todo = sum(1 for i in items if i["status"] == "todo")
	return {"items": items, "request_types": per_type, "todo": todo, "ready": todo == 0,
			"legacy_apps": apps}


def _fields_of(dt):
	return [df.fieldname for df in frappe.get_meta(dt).fields
			if df.fieldtype not in ("Section Break", "Column Break", "Tab Break", "HTML", "Button", "Table", "Table MultiSelect")
			and df.fieldname not in SKIP]


def _status(row):
	if row.docstatus == 2:
		return "Cancelled"
	state = (row.get("workflow_state") or row.get("status") or "").lower()
	if "reject" in state:
		return "Rejected"
	if row.docstatus == 1 or "approv" in state or "complet" in state:
		return "Completed"
	return "Pending HR"


def _plan_requests():
	plan = []
	for dt, target in LEGACY_REQUESTS.items():
		if not _exists(dt) or not frappe.db.exists("AlphaX Request Type", target):
			continue
		meta = frappe.get_meta(dt)
		emp_field = "employee" if meta.has_field("employee") else ("employee_no" if meta.has_field("employee_no") else None)
		if not emp_field:
			continue
		fields = _fields_of(dt)
		extra = [f for f in ("workflow_state", "status") if meta.has_field(f)]
		done = _imported(f"{dt}:")
		for r in frappe.get_all(dt, fields=["name", "docstatus", "creation", emp_field] + fields + extra, order_by="creation asc"):
			ref = f"{dt}:{r.name}"
			if ref in done or not r.get(emp_field) or not frappe.db.exists("Employee", r.get(emp_field)):
				continue
			details = {k: str(r.get(k)) for k in fields if r.get(k) not in (None, "", 0) and k not in ("reason",)}
			details["legacy_type"] = dt
			plan.append({"legacy_ref": ref, "employee": r.get(emp_field), "request_type": target, "status": _status(r),
						 "reason": str(r.get("reason") or "")[:2000], "details": details, "creation": str(r.creation)})
	return plan


def _plan_warnings():
	plan = []
	for dt in WARNING_DOCTYPES:
		if not _exists(dt):
			continue
		meta = frappe.get_meta(dt)
		done = set(frappe.get_all("AlphaX Penalty", filters={"source_ref": ["like", f"{dt}:%"]}, pluck="source_ref"))
		fields = [f for f in ("employee", "warning_date", "reason", "action_to_be_taken", "number_of_warnings") if meta.has_field(f)]
		for r in frappe.get_all(dt, fields=["name", "docstatus", "creation"] + fields):
			ref = f"{dt}:{r.name}"
			if ref in done or not r.get("employee") or not frappe.db.exists("Employee", r.employee):
				continue
			plan.append({"source_ref": ref, "employee": r.employee, "violation_date": str(r.get("warning_date") or getdate(r.creation)),
						 "description": " · ".join(str(x) for x in (r.get("reason"), r.get("action_to_be_taken")) if x) or _("Imported warning"),
						 "occurrence": cint(r.get("number_of_warnings")) or 1,
						 "status": {0: "Draft", 1: "Acknowledged", 2: "Cancelled"}[r.docstatus]})
	return plan


def _iqama_plan():
	if not _exists("Employee Iqama"):
		return []
	meta = frappe.get_meta("Employee")
	if not meta.has_field("alphax_iqama_number"):
		return []
	rows = frappe.get_all("Employee Iqama", filters={"docstatus": ["<", 2]}, fields=["employee", "iqama_number", "expiry_date_gregorian", "modified"],
						  order_by="modified asc")
	latest = {r.employee: r for r in rows if r.employee}
	plan = []
	for emp, r in latest.items():
		cur = frappe.db.get_value("Employee", emp, ["alphax_iqama_number", "alphax_iqama_expiry"], as_dict=True)
		if not cur:
			continue
		changes = {}
		if r.iqama_number and not cur.alphax_iqama_number:
			changes["alphax_iqama_number"] = r.iqama_number
		if r.expiry_date_gregorian and not cur.alphax_iqama_expiry:
			changes["alphax_iqama_expiry"] = str(r.expiry_date_gregorian)
		if changes:
			plan.append({"employee": emp, "changes": changes})
	return plan


def _violation_for_import():
	if not frappe.db.exists("AlphaX Violation Type", IMPORTED_VIOLATION):
		frappe.get_doc({"doctype": "AlphaX Violation Type", "violation_name": IMPORTED_VIOLATION, "title_ar": "إنذار (مستورد)",
						"category": "Other", "enabled": 0, "steps_json": json.dumps([{"action": "Warning"}]),
						"reference": "Imported from the previous HR app"}).insert(ignore_permissions=True)
	return IMPORTED_VIOLATION


@frappe.whitelist(methods=["POST"])
def import_legacy(kind: str, dry_run: int | str = 1):
	"""kind: requests | warnings | identity. Dry run returns the plan; otherwise it is applied once."""
	require_hr_manager()
	dry = cint(dry_run)
	if kind == "requests":
		plan = _plan_requests()
		if not dry:
			for p in plan:
				doc = frappe.get_doc({"doctype": "AlphaX Request", "employee": p["employee"], "request_type": p["request_type"],
									  "status": p["status"], "reason": p["reason"], "legacy_ref": p["legacy_ref"],
									  "details": json.dumps(p["details"], ensure_ascii=False)})
				doc.flags.alphax_engine = True
				doc.insert(ignore_permissions=True)
				frappe.db.set_value("AlphaX Request", doc.name, "creation", p["creation"], update_modified=False)
	elif kind == "warnings":
		plan = _plan_warnings()
		if not dry and plan:
			vt = _violation_for_import()
			for p in plan:
				doc = frappe.get_doc({"doctype": "AlphaX Penalty", "employee": p["employee"], "violation_type": vt,
									  "violation_date": p["violation_date"], "discovered_on": p["violation_date"], "description": p["description"],
									  "status": p["status"], "occurrence": p["occurrence"], "action": "Warning", "amount": 0,
									  "source_ref": p["source_ref"]})
				doc.insert(ignore_permissions=True)
	elif kind == "identity":
		from alphax_hr.api.compliance import import_legacy_fields

		fields_plan = import_legacy_fields(dry_run=dry)
		plan = fields_plan["sample"] if dry else []
		iq = _iqama_plan()
		if not dry:
			for p in iq:
				doc = frappe.get_doc("Employee", p["employee"])
				doc.update(p["changes"])
				doc.flags.ignore_mandatory = True
				doc.save(ignore_permissions=True)
		return {"kind": kind, "dry_run": bool(dry), "count": fields_plan["employees"] + len(iq), "sample": (plan + iq)[:20]}
	else:
		frappe.throw(_("Unknown import."))
	return {"kind": kind, "dry_run": bool(dry), "count": len(plan), "sample": plan[:20]}
