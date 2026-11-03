"""Employee self-service: everything here is scoped to the signed-in employee."""
from __future__ import annotations

import re as _re

import frappe
from frappe import _
from frappe.utils import add_days, cint, flt, get_first_day, get_last_day, getdate, now_datetime, nowdate

from alphax_hr.api._common import current_employee, has_field, login_required
from alphax_hr.saudi import leave as saudi_leave

PROFILE_FIELDS = [
	"name", "employee_name", "first_name", "last_name", "image", "gender", "date_of_birth",
	"date_of_joining", "company", "department", "designation", "branch", "employment_type",
	"reports_to", "cell_number", "personal_email", "company_email", "holiday_list", "default_shift",
	"leave_approver", "expense_approver", "status",
]
SAUDI_FIELDS = ["alphax_is_saudi", "alphax_iqama_number", "alphax_iqama_expiry", "alphax_work_permit_expiry"]
SELF_EDITABLE = {"cell_number", "personal_email", "person_to_be_contacted", "emergency_phone_number",
				 "relation", "current_address", "permanent_address"}


def _employee_doc():
	doc = frappe.get_doc("Employee", current_employee())
	doc.check_permission("read")
	return doc


@frappe.whitelist()
def my_profile():
	doc = _employee_doc()
	data = {f: doc.get(f) for f in PROFILE_FIELDS + SAUDI_FIELDS + sorted(SELF_EDITABLE) if doc.meta.has_field(f) or f == "name"}
	if doc.reports_to:
		data["reports_to_name"] = frappe.db.get_value("Employee", doc.reports_to, "employee_name")
	data["annual_entitlement_days"] = (
		saudi_leave.annual_entitlement(getdate(doc.date_of_joining), getdate(nowdate())) if doc.date_of_joining else None
	)
	data["self_editable"] = sorted(f for f in SELF_EDITABLE if doc.meta.has_field(f))
	return data


@frappe.whitelist()
def update_my_contact(data):
	"""Employees may update their own contact details only."""
	payload = frappe.parse_json(data) if isinstance(data, str) else data
	doc = _employee_doc()
	changes = {k: v for k, v in (payload or {}).items() if k in SELF_EDITABLE and doc.meta.has_field(k)}
	if not changes:
		frappe.throw(_("Nothing to update."))
	doc.update(changes)
	# Only the contact fields above can change. Employees often lack write access to Employee, and stale values
	# elsewhere on the record (e.g. a nationality missing from its list) must not block a phone number update.
	doc.flags.ignore_permissions = True
	doc.flags.ignore_links = True
	doc.flags.ignore_mandatory = True
	doc.save()
	return my_profile()


@frappe.whitelist()
def profile_change_form():
	"""Fields an employee can ask HR to change, with their current values and any pending request."""
	from alphax_hr.api import requests as rq

	doc = _employee_doc()
	fields = [{**f, "value": str(doc.get(f["fieldname"]) or "")} for f in rq.profile_fields()]
	t_name = frappe.db.get_value("AlphaX Request Type", {"effect": "Update employee record"})
	pending = frappe.get_all("AlphaX Request", filters={"employee": doc.name, "request_type": t_name or "", "status": ["in", list(rq.OPEN)]},
							 fields=["name", "status", "details", "creation"], limit=1)
	p = None
	if pending:
		p = {"name": pending[0].name, "status": pending[0].status, "creation": str(pending[0].creation),
			 "changes": (frappe.parse_json(pending[0].details or "{}") or {}).get("changes", {})}
	return {"fields": fields, "pending": p, "enabled": bool(t_name)}


@frappe.whitelist(methods=["POST"])
def request_profile_change(changes, reason=None):
	from alphax_hr.api.requests import create_profile_update

	return create_profile_update(current_employee(), changes, reason)


@frappe.whitelist()
def my_activity(limit=15):
	"""What happened recently on my requests, leave, pay and warnings."""
	employee = current_employee()
	limit = min(cint(limit) or 15, 50)
	since = add_days(nowdate(), -60)
	items = []

	def add(rows, kind, title_fn, link_fn):
		for r in rows:
			items.append({"kind": kind, "title": title_fn(r), "status": r.get("status") or r.get("approval_status"),
						  "at": str(r.modified), "link": link_fn(r)})

	add(frappe.get_all("Leave Application", filters={"employee": employee, "modified": [">=", since]},
					   fields=["name", "leave_type", "from_date", "to_date", "status", "modified"], order_by="modified desc", limit=limit),
		"leave", lambda r: f"{r.leave_type}: {frappe.utils.formatdate(r.from_date)} → {frappe.utils.formatdate(r.to_date)}", lambda r: "/me/leave")
	if frappe.db.exists("DocType", "AlphaX Request"):
		add(frappe.get_all("AlphaX Request", filters={"employee": employee, "modified": [">=", since]},
						   fields=["name", "request_type", "status", "modified"], order_by="modified desc", limit=limit),
			"request", lambda r: _(r.request_type), lambda r: "/me/requests")
	add(frappe.get_all("Salary Slip", filters={"employee": employee, "docstatus": 1, "modified": [">=", since]},
					   fields=["name", "start_date", "modified"], order_by="modified desc", limit=6),
		"payslip", lambda r: _("Payslip for {0}").format(getdate(r.start_date).strftime("%B %Y")), lambda r: "/me/payslips")
	if frappe.db.exists("DocType", "Expense Claim"):
		add(frappe.get_all("Expense Claim", filters={"employee": employee, "modified": [">=", since]},
						   fields=["name", "total_claimed_amount", "approval_status", "modified"], order_by="modified desc", limit=limit),
			"expense", lambda r: _("Expense claim {0}").format(frappe.utils.fmt_money(r.total_claimed_amount)), lambda r: "/me/expenses")
	if frappe.db.exists("DocType", "AlphaX Penalty"):
		add(frappe.get_all("AlphaX Penalty", filters={"employee": employee, "status": ["!=", "Draft"], "modified": [">=", since]},
						   fields=["name", "violation_type", "status", "modified"], order_by="modified desc", limit=limit),
			"warning", lambda r: r.violation_type, lambda r: "/me/warnings")
	items.sort(key=lambda x: x["at"], reverse=True)
	return items[:limit]


# ------------------------------------------------------------------ leave
@frappe.whitelist()
def my_leave_balances(date=None):
	employee = current_employee()
	on = date or nowdate()
	from hrms.hr.doctype.leave_application.leave_application import get_leave_details

	details = get_leave_details(employee, on)
	rows = []
	for leave_type, row in (details.get("leave_allocation") or {}).items():
		rows.append({
			"leave_type": leave_type,
			"allocated": flt(row.get("total_leaves")),
			"taken": flt(row.get("leaves_taken")),
			"pending": flt(row.get("leaves_pending_approval")),
			"expired": flt(row.get("expired_leaves")),
			"balance": flt(row.get("remaining_leaves")),
		})
	return {
		"balances": sorted(rows, key=lambda r: r["leave_type"]),
		"lwps": details.get("lwps") or [],
		"leave_approver": details.get("leave_approver"),
	}


@frappe.whitelist()
def my_leave_applications(limit=30):
	employee = current_employee()
	fields = ["name", "leave_type", "from_date", "to_date", "total_leave_days", "status", "docstatus",
			  "description", "posting_date", "leave_approver_name", "half_day"]
	if has_field("Leave Application", "workflow_state"):
		fields.append("workflow_state")
	return frappe.get_list(
		"Leave Application",
		filters={"employee": employee},
		fields=fields,
		order_by="from_date desc",
		page_length=min(cint(limit) or 30, 100),
	)


@frappe.whitelist()
def leave_types():
	"""Leave types the employee can apply for, with any statutory rule attached.

	Allocated types, leave-without-pay types, and statutory leaves mapped in
	AlphaX HR Settings (those need no allocation; the rule caps them).
	"""
	from alphax_hr.leave_engine import rule_to_dict, rules_by_leave_type

	balances = my_leave_balances()
	rules = rules_by_leave_type()
	gender = frappe.db.get_value("Employee", current_employee(), "gender")
	names = {b["leave_type"] for b in balances["balances"]} | set(balances["lwps"])
	for leave_type, rule in rules.items():
		if (not rule.gender or not gender or rule.gender == gender) and frappe.db.exists("Leave Type", leave_type):
			names.add(leave_type)
	return [{"leave_type": n, "rule": rule_to_dict(rules.get(n))} for n in sorted(names)]


# Fields AlphaX fills itself on a Leave Application; anything else the site makes mandatory is asked for.
LEAVE_HANDLED = {"employee", "employee_name", "company", "leave_type", "from_date", "to_date", "half_day", "half_day_date",
				 "description", "posting_date", "leave_approver", "leave_approver_name", "status", "follow_via_email",
				 "alphax_event_date", "alphax_relation", "department", "total_leave_days", "leave_balance", "workflow_state",
				 "naming_series", "amended_from", "letter_head", "color"}
LEAVE_INPUT_TYPES = {"Data", "Link", "Select", "Date", "Datetime", "Int", "Float", "Currency", "Small Text", "Text", "Long Text",
					 "Phone", "Attach", "Attach Image"}
_RETURN_DATE = _re.compile(r"report(ing)?\s*(back\s*)?to\s*work|return(ing)?\s*(to\s*work|date)|resum|re-?join|back\s*to\s*work|duty\s*resumption", _re.I)


def _leave_auto_kind(df):
	if df.fieldtype == "Date" and (_RETURN_DATE.search(df.label or "") or _RETURN_DATE.search(df.fieldname.replace("_", " "))):
		return "return_date"
	return None


def _leave_required_fields():
	meta = frappe.get_meta("Leave Application")
	out = []
	for df in meta.fields:
		if not df.reqd or df.fetch_from or cint(df.permlevel) or df.fieldtype not in LEAVE_INPUT_TYPES or df.fieldname in LEAVE_HANDLED:
			continue
		out.append(df)
	return out


@frappe.whitelist()
def leave_form():
	"""Extra fields this site requires on a leave request (custom mandatory fields), and ones AlphaX fills."""
	current_employee()
	fields, auto = [], []
	for df in _leave_required_fields():
		kind = _leave_auto_kind(df)
		if kind:
			auto.append({"fieldname": df.fieldname, "label": _(df.label or df.fieldname), "kind": kind})
			continue
		spec = {"fieldname": df.fieldname, "label": _(df.label or df.fieldname), "fieldtype": df.fieldtype, "reqd": 1,
				"description": _(df.description) if df.description else None, "default": df.default}
		if df.fieldtype == "Select":
			spec["options"] = (df.options or "").split("\n")
		elif df.fieldtype == "Link":
			spec["options"] = df.options
		fields.append(spec)
	return {"fields": fields, "auto": auto}


def next_working_day(employee, after):
	"""First day after ``after`` that is not a holiday / week-off for the employee."""
	from hrms.hr.utils import get_holiday_list_for_employee

	hl = get_holiday_list_for_employee(employee, raise_exception=False)
	day = getdate(add_days(after, 1))
	if not hl:
		return day
	off = set(frappe.get_all("Holiday", filters={"parent": hl, "holiday_date": ["between", [day, add_days(day, 60)]]}, pluck="holiday_date"))
	while day in off:
		day = getdate(add_days(day, 1))
	return day


@frappe.whitelist()
def lookup(doctype, txt=""):
	"""Suggestions for Link fields on the employee's own forms (only doctypes those forms link to)."""
	current_employee()
	allowed = {f["options"] for f in leave_form()["fields"] if f["fieldtype"] == "Link"}
	if doctype not in allowed:
		frappe.throw(_("Lookup not allowed."), frappe.PermissionError)
	meta = frappe.get_meta(doctype)
	title = meta.title_field if meta.title_field and meta.title_field != "name" else None
	filters = {"disabled": 0} if meta.has_field("disabled") else {}
	or_filters = {"name": ["like", f"%{str(txt)[:80]}%"]}
	if title:
		or_filters[title] = ["like", f"%{str(txt)[:80]}%"]
	rows = frappe.get_all(doctype, filters=filters, or_filters=or_filters, fields=["name"] + ([title] if title else []),
						  limit_page_length=20, order_by="name asc")  # names of a master list the form links to
	return [{"value": r.name, "description": r.get(title) if title else None} for r in rows]


def _leave_approver_for(employee):
	from hrms.hr.doctype.leave_application.leave_application import get_leave_approver

	approver = get_leave_approver(employee)
	if approver:
		return approver
	reports_to = frappe.db.get_value("Employee", employee, "reports_to")
	return frappe.db.get_value("Employee", reports_to, "user_id") if reports_to else None


@frappe.whitelist()
def apply_leave(leave_type, from_date, to_date, reason=None, half_day=0, half_day_date=None, event_date=None, relation=None, extra=None):
	employee = current_employee()
	emp = frappe.db.get_value("Employee", employee, ["company", "holiday_list"], as_dict=True)

	doc = frappe.new_doc("Leave Application")
	doc.update({
		"employee": employee,
		"company": emp.company,
		"leave_type": leave_type,
		"from_date": from_date,
		"to_date": to_date,
		"half_day": cint(half_day),
		"half_day_date": half_day_date if cint(half_day) else None,
		"description": (reason or "")[:1000],
		"posting_date": nowdate(),
		"leave_approver": _leave_approver_for(employee),
		"follow_via_email": 1,
		"alphax_event_date": event_date or None,
		"alphax_relation": relation or None,
	})
	# The site's own mandatory fields: AlphaX fills what it can work out, the employee answers the rest.
	values = frappe.parse_json(extra) if extra else {}
	missing = []
	for df in _leave_required_fields():
		if _leave_auto_kind(df) == "return_date":
			doc.set(df.fieldname, values.get(df.fieldname) or next_working_day(employee, to_date))
		elif values.get(df.fieldname) not in (None, ""):
			doc.set(df.fieldname, values[df.fieldname])
		elif df.default:
			doc.set(df.fieldname, df.default)
		else:
			missing.append(_(df.label or df.fieldname))
	if missing:
		frappe.throw(_("Please fill in: {0}").format(", ".join(missing)), title=_("Missing information"))
	try:
		doc.insert()  # permissions + HRMS validation (balance, overlap, holidays ...)
	except frappe.MandatoryError as exc:
		frappe.throw(_("Your company requires more information on leave requests ({0}). Please ask HR.").format(str(exc)[:300]),
					 title=_("Missing information"))
	for df in _leave_required_fields():  # files uploaded for attach fields belong to this request now
		if df.fieldtype in ("Attach", "Attach Image") and doc.get(df.fieldname):
			for f in frappe.get_all("File", filters={"file_url": doc.get(df.fieldname), "owner": frappe.session.user,
													 "attached_to_name": ["is", "not set"]}, pluck="name"):
				frappe.db.set_value("File", f, {"attached_to_doctype": "Leave Application", "attached_to_name": doc.name,
												"attached_to_field": df.fieldname})
	warnings = []
	if not doc.leave_approver:
		warnings.append(_("No leave approver is set for you. HR has been asked to review this request."))
	if flt(doc.total_leave_days) == 0:
		warnings.append(_("This request counts as 0 working days. Your holiday list may not cover these dates — please check with HR."))
	if doc.get("alphax_sick_breakdown"):
		warnings.append(doc.alphax_sick_breakdown)
	warnings += _outside_plan(employee, leave_type, from_date, to_date)
	return {"name": doc.name, "total_leave_days": doc.total_leave_days, "status": doc.status, "warnings": warnings}


def _outside_plan(employee, leave_type, from_date, to_date):
	"""Annual leave outside an approved vacation plan is allowed, but the approver should know."""
	from alphax_hr.api._common import settings

	if leave_type != settings().get("annual_leave_type") or not frappe.db.exists("DocType", "AlphaX Leave Plan"):
		return []
	plan = frappe.db.get_value("AlphaX Leave Plan", {"employee": employee, "year": getdate(from_date).year, "status": "Approved"})
	if not plan:
		return []
	inside = frappe.db.exists("AlphaX Leave Plan Period", {"parent": plan, "from_date": ["<=", from_date], "to_date": [">=", to_date]})
	return [] if inside else [_("These dates are outside your approved vacation plan; your approver will see that.")]


@frappe.whitelist()
def withdraw_leave(name):
	"""Delete one of my own leave requests that is still a draft and not yet acted on."""
	employee = current_employee()
	doc = frappe.get_doc("Leave Application", name)
	if doc.employee != employee:
		frappe.throw(_("You can only withdraw your own requests."), frappe.PermissionError)
	if doc.docstatus != 0 or doc.status != "Open":
		frappe.throw(_("Only open requests that have not been approved can be withdrawn."))
	if doc.meta.has_field("workflow_state") and doc.get("workflow_state") not in (None, "", "Draft", "Open"):
		frappe.throw(_("This request is already in the approval workflow."))
	# HRMS gives employees no delete right on Leave Application; ownership and state are checked above.
	frappe.delete_doc("Leave Application", name, ignore_permissions=True)
	return True


# ------------------------------------------------------------- attendance
@frappe.whitelist()
def my_attendance(month=None):
	employee = current_employee()
	ref = getdate(month or nowdate())
	start, end = get_first_day(ref), get_last_day(ref)
	rows = frappe.get_list(
		"Attendance",
		filters={"employee": employee, "attendance_date": ["between", [start, end]], "docstatus": 1},
		fields=["name", "attendance_date", "status", "shift", "working_hours", "late_entry", "early_exit", "leave_type"],
		order_by="attendance_date asc",
		page_length=62,
	)
	summary = {"Present": 0, "Absent": 0, "On Leave": 0, "Half Day": 0, "Work From Home": 0, "late": 0}
	for r in rows:
		summary[r.status] = summary.get(r.status, 0) + 1
		summary["late"] += 1 if r.late_entry else 0
	return {"month": str(start), "rows": rows, "summary": summary, "today": today_status()}


@frappe.whitelist()
def today_status():
	employee = current_employee()
	today = nowdate()
	logs = frappe.get_list(
		"Employee Checkin",
		filters={"employee": employee, "time": ["between", [today + " 00:00:00", today + " 23:59:59"]]},
		fields=["name", "time", "log_type"] + (["alphax_location", "alphax_outside"] if has_field("Employee Checkin", "alphax_location") else []),
		order_by="time asc",
		page_length=50,
	)
	last = logs[-1] if logs else None
	return {
		"date": today,
		"logs": logs,
		**checkin_rules(employee),
		"next_action": "OUT" if last and last.log_type == "IN" else "IN",
		"shift": frappe.db.get_value("Employee", employee, "default_shift"),
	}


def checkin_rules(employee):
	"""Location rule and minimum gap for this employee: their attendance policy, else the company setting."""
	from alphax_hr.api._common import settings
	from alphax_hr.api.attendance_policy import for_employee

	conf = settings()
	pol = for_employee(employee)
	rule = (pol and pol.get("checkin_location_rule")) or conf.get("checkin_location_rule") or "Anywhere"
	gap = cint(conf.get("checkin_min_gap")) if conf.get("checkin_min_gap") is not None else 5
	if pol and str(pol.get("min_punch_gap") or "").strip() != "":
		gap = cint(pol.min_punch_gap)
	return {"location_rule": rule, "min_gap": gap}


def _distance_m(lat1, lon1, lat2, lon2):
	from math import asin, cos, radians, sin, sqrt

	dlat, dlon = radians(lat2 - lat1), radians(lon2 - lon1)
	a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
	return 2 * 6371000 * asin(sqrt(a))


def nearest_location(company, lat, lon):
	if not frappe.db.exists("DocType", "AlphaX Work Location"):
		return None
	best = None
	for loc in frappe.get_all("AlphaX Work Location", filters={"enabled": 1}, fields=["name", "company", "latitude", "longitude", "radius_m"]):
		if loc.company and loc.company != company:
			continue
		d = _distance_m(flt(lat), flt(lon), flt(loc.latitude), flt(loc.longitude))
		if not best or d < best["distance"]:
			best = {"name": loc.name, "distance": int(d), "inside": d <= (cint(loc.radius_m) or 150)}
	return best


@frappe.whitelist()
def check_in(log_type, latitude=None, longitude=None, accuracy=None):
	if log_type not in ("IN", "OUT"):
		frappe.throw(_("Invalid check-in type."))
	employee = current_employee()
	rules = checkin_rules(employee)
	last = frappe.get_list("Employee Checkin", filters={"employee": employee}, fields=["time", "log_type"],
						   order_by="time desc", page_length=1)
	gap = max(rules["min_gap"], 1)
	if last and (now_datetime() - last[0].time).total_seconds() < gap * 60:
		frappe.throw(_("Your last punch ({0} at {1}) was less than {2} minute(s) ago.").format(
			last[0].log_type, last[0].time.strftime("%H:%M"), gap), title=_("Already recorded"))
	has_pos = latitude not in (None, "") and longitude not in (None, "")
	if rules["location_rule"] != "Anywhere" and not has_pos:
		frappe.throw(_("Turn on location for this app to check {0}.").format(log_type.lower()), title=_("Location needed"))
	company = frappe.db.get_value("Employee", employee, "company")
	near = nearest_location(company, latitude, longitude) if has_pos else None
	if rules["location_rule"] == "Inside a work location":
		if not near:
			frappe.throw(_("No work location is set up for your company yet. Ask HR."))
		if not near["inside"]:
			frappe.throw(_("You are {0} m from {1}. Check {2} from your work location.").format(near["distance"], near["name"], log_type.lower()),
						 title=_("Outside the work location"))
	doc = frappe.new_doc("Employee Checkin")
	doc.employee = employee
	doc.log_type = log_type
	doc.time = now_datetime()
	if has_pos and doc.meta.has_field("latitude"):
		doc.latitude = flt(latitude)
		doc.longitude = flt(longitude)
	if doc.meta.has_field("alphax_source"):
		doc.alphax_source = "AlphaX app"
		if near:
			doc.alphax_location, doc.alphax_distance_m, doc.alphax_outside = near["name"], near["distance"], 0 if near["inside"] else 1
	doc.flags.ignore_permissions = True  # the employee checks in for themselves only
	doc.insert()  # HRMS shift validation applies
	return today_status()


# ------------------------------------------------- shift & attendance requests
ATTENDANCE_REASONS = {"Work From Home", "On Duty"}  # HRMS options; a missed punch is filed as On Duty


def _shift_approver(employee):
	emp = frappe.db.get_value("Employee", employee, ["shift_request_approver", "department"], as_dict=True)
	if emp.shift_request_approver:
		return emp.shift_request_approver
	if emp.department:
		row = frappe.db.get_value("Department Approver", {"parent": emp.department, "parentfield": "shift_request_approver"},
								  "approver", order_by="idx asc")
		if row:
			return row
	return None


@frappe.whitelist()
def shift_types():
	login_required()
	return frappe.get_all("Shift Type", fields=["name", "start_time", "end_time"], order_by="name asc")


@frappe.whitelist()
def request_shift(shift_type, from_date, to_date=None, reason=None):
	"""Ask for a different shift. Goes to the shift approver's inbox in AlphaX."""
	employee = current_employee()
	approver = _shift_approver(employee)
	if not approver:
		frappe.throw(_("No shift approver is set for you. Please ask HR to set one."), title=_("Shift approver missing"))
	if to_date and getdate(to_date) < getdate(from_date):
		frappe.throw(_("End date is before the start date."))
	doc = frappe.get_doc({"doctype": "Shift Request", "employee": employee, "shift_type": shift_type,
						  "company": frappe.db.get_value("Employee", employee, "company"),
						  "from_date": from_date, "to_date": to_date or None, "status": "Draft", "approver": approver})
	if reason and doc.meta.has_field("reason"):
		doc.reason = str(reason)[:500]
	doc.insert()
	return {"name": doc.name, "approver": approver}


@frappe.whitelist()
def request_attendance(from_date, to_date, reason, explanation=None, half_day=0, half_day_date=None):
	"""Correct attendance (missed punch, on duty, work from home); approved in the AlphaX inbox."""
	employee = current_employee()
	if reason not in ATTENDANCE_REASONS:
		frappe.throw(_("Choose a reason."))
	if getdate(to_date) < getdate(from_date):
		frappe.throw(_("End date is before the start date."))
	if getdate(from_date) > getdate(nowdate()):
		frappe.throw(_("Attendance can only be corrected for past days or today."))
	if not (explanation or "").strip():
		frappe.throw(_("Please explain what happened (e.g. forgot to punch out)."))
	doc = frappe.get_doc({"doctype": "Attendance Request", "employee": employee,
						  "company": frappe.db.get_value("Employee", employee, "company"),
						  "from_date": from_date, "to_date": to_date, "reason": reason,
						  "explanation": str(explanation)[:1000], "half_day": cint(half_day),
						  "half_day_date": half_day_date if cint(half_day) else None})
	doc.insert()
	return {"name": doc.name}


@frappe.whitelist()
def my_requests(limit=30):
	"""My shift and attendance requests, newest first."""
	employee = current_employee()
	limit = min(cint(limit) or 30, 100)
	shifts = frappe.get_list("Shift Request", filters={"employee": employee}, order_by="creation desc", page_length=limit,
							 fields=["name", "shift_type", "from_date", "to_date", "status", "docstatus", "creation"])
	att = frappe.get_list("Attendance Request", filters={"employee": employee}, order_by="creation desc", page_length=limit,
						  fields=["name", "reason", "from_date", "to_date", "explanation", "docstatus", "creation"])
	rows = [{**r, "type": "Shift Request"} for r in shifts] + [
		{**r, "type": "Attendance Request", "status": {0: "Open", 1: "Approved", 2: "Cancelled"}[r.docstatus]} for r in att]
	if frappe.db.exists("DocType", "AlphaX Request") and frappe.get_meta("AlphaX Request Type").has_field("effect"):
		permit_types = frappe.get_all("AlphaX Request Type", filters={"effect": ["is", "set"]}, pluck="name")
		for r in frappe.get_list("AlphaX Request", filters={"employee": employee, "request_type": ["in", permit_types or [""]]},
								 fields=["name", "request_type", "status", "details", "creation"], order_by="creation desc", page_length=limit):
			d = frappe.parse_json(r.details or "{}") or {}
			rows.append({"name": r.name, "type": "Permission", "request_type": r.request_type, "status": r.status,
						 "from_date": d.get("date"), "to_date": d.get("date"), "time": d.get("time"), "creation": r.creation})
	rows.sort(key=lambda r: str(r["creation"]), reverse=True)
	return rows[:limit]


# --------------------------------------------------------------- payslips
@frappe.whitelist()
def my_payslips(limit=24):
	employee = current_employee()
	slips = frappe.get_list(
		"Salary Slip",
		filters={"employee": employee, "docstatus": 1},
		fields=["name", "start_date", "end_date", "posting_date", "gross_pay", "total_deduction", "net_pay", "currency"],
		order_by="start_date desc",
		page_length=min(cint(limit) or 24, 60),
	)
	return slips


@frappe.whitelist()
def payslip(name):
	employee = current_employee()
	doc = frappe.get_doc("Salary Slip", name)
	if doc.employee != employee or doc.docstatus != 1:
		frappe.throw(_("Payslip not found."), frappe.DoesNotExistError)
	doc.check_permission("read")
	line = lambda r: {"component": r.salary_component, "abbr": r.abbr, "amount": flt(r.amount)}
	return {
		"name": doc.name, "start_date": doc.start_date, "end_date": doc.end_date, "currency": doc.currency,
		"payment_days": doc.payment_days, "total_working_days": doc.total_working_days,
		"earnings": [line(r) for r in doc.earnings], "deductions": [line(r) for r in doc.deductions],
		"gross_pay": flt(doc.gross_pay), "total_deduction": flt(doc.total_deduction), "net_pay": flt(doc.net_pay),
		"pdf_url": "/api/method/alphax_hr.api.payslip.download?name=" + frappe.utils.quote(doc.name),
	}


# --------------------------------------------------------------- expenses
@frappe.whitelist()
def my_expense_claims(limit=20):
	employee = current_employee()
	if not frappe.db.exists("DocType", "Expense Claim"):
		return []
	return frappe.get_list(
		"Expense Claim",
		filters={"employee": employee},
		fields=["name", "posting_date", "total_claimed_amount", "total_sanctioned_amount", "approval_status", "status", "docstatus"],
		order_by="posting_date desc",
		page_length=min(cint(limit) or 20, 100),
	)


@frappe.whitelist()
def upcoming_holidays(days=60):
	employee = current_employee()
	from hrms.hr.utils import get_holiday_list_for_employee

	holiday_list = get_holiday_list_for_employee(employee, raise_exception=False)
	if not holiday_list:
		return {"holiday_list": None, "holidays": []}
	today = nowdate()
	rows = frappe.get_all(  # Holiday rows are not personal data; the list is the employee's own.
		"Holiday",
		filters={"parent": holiday_list, "holiday_date": ["between", [today, add_days(today, cint(days) or 60)]],
				 "weekly_off": 0},
		fields=["holiday_date", "description"],
		order_by="holiday_date asc",
	)
	return {"holiday_list": holiday_list, "holidays": rows}


# --------------------------------------------------------------- expense claims
@frappe.whitelist()
def expense_types():
	current_employee()
	if not frappe.db.exists("DocType", "Expense Claim Type"):
		return []
	return frappe.get_all("Expense Claim Type", fields=["name", "description"], order_by="name asc")


def _expense_approver(emp):
	if emp.get("expense_approver"):
		return emp.expense_approver
	if emp.reports_to:
		user = frappe.db.get_value("Employee", emp.reports_to, "user_id")
		if user:
			return user
	return emp.leave_approver


@frappe.whitelist(methods=["POST"])
def submit_expense(expense_type, amount, expense_date, description=None):
	"""File an expense claim for yourself; it goes to your expense approver (Approvals inbox)."""
	employee = current_employee()
	emp = frappe.get_doc("Employee", employee)
	amount = flt(amount, 2)
	if amount <= 0:
		frappe.throw(_("The amount must be more than zero."))
	if getdate(expense_date) > getdate(nowdate()):
		frappe.throw(_("The expense date cannot be in the future."))
	if not frappe.db.exists("Expense Claim Type", expense_type):
		frappe.throw(_("Unknown expense type."))
	doc = frappe.get_doc({
		"doctype": "Expense Claim", "employee": employee, "company": emp.company, "posting_date": nowdate(),
		"expense_approver": _expense_approver(emp), "approval_status": "Draft",
		"payable_account": frappe.get_cached_value("Company", emp.company, "default_expense_claim_payable_account"),
		"expenses": [{"expense_date": expense_date, "expense_type": expense_type, "amount": amount, "sanctioned_amount": amount,
					  "description": (description or "")[:1000]}],
	})
	doc.flags.ignore_permissions = True  # the employee is the claimant; approver and accounts are set here, not by them
	doc.insert()
	return {"name": doc.name, "approver": doc.expense_approver}


@frappe.whitelist(methods=["POST"])
def withdraw_expense(name):
	employee = current_employee()
	doc = frappe.get_doc("Expense Claim", name)
	if doc.employee != employee or doc.docstatus != 0 or doc.approval_status != "Draft":
		frappe.throw(_("Only your own claims that are still waiting can be withdrawn."))
	frappe.delete_doc("Expense Claim", name, ignore_permissions=True)
	return {"ok": True}


# --------------------------------------------------------------- documents
DOCUMENT_FIELDS = (("alphax_iqama_expiry", "Iqama / ID"), ("valid_upto", "Passport"), ("alphax_work_permit_expiry", "Work permit"),
				   ("contract_end_date", "Contract"), ("alphax_insurance_expiry", "Medical insurance"))


@frappe.whitelist()
def my_documents():
	"""My document expiry dates, files on my employee record and letters issued to me."""
	employee = current_employee()
	emp = frappe.get_doc("Employee", employee)
	today = getdate(nowdate())
	docs = []
	for field, label in DOCUMENT_FIELDS:
		if emp.meta.has_field(field) and emp.get(field):
			days = (getdate(emp.get(field)) - today).days
			docs.append({"document": label, "expiry": str(emp.get(field)), "days_left": days,
						 "state": "expired" if days < 0 else "soon" if days <= 60 else "valid"})
	files = frappe.get_all("File", filters={"attached_to_doctype": "Employee", "attached_to_name": employee, "is_folder": 0},
						   fields=["name", "file_name", "file_url", "creation"], order_by="creation desc", limit_page_length=100)
	letters = []
	if frappe.db.exists("DocType", "AlphaX Request"):
		letters = frappe.get_all("AlphaX Request", filters={"employee": employee, "letter": ["is", "set"]},
								 fields=["name", "request_type", "letter", "modified"], order_by="modified desc")
	return {"documents": docs, "files": [{**f, "creation": str(f.creation)} for f in files],
			"letters": [{**r, "modified": str(r.modified)} for r in letters]}


# --------------------------------------------------------------- my team
@frappe.whitelist()
def my_team():
	"""People who report to me (or whose leave I approve) and where they are today."""
	user = frappe.session.user
	me = frappe.db.get_value("Employee", {"user_id": user}, "name")
	or_filters = {"leave_approver": user}
	if me:
		or_filters["reports_to"] = me
	team = frappe.get_all("Employee", filters={"status": "Active"}, or_filters=or_filters,
						  fields=["name", "employee_name", "designation", "department", "image", "cell_number", "user_id"],
						  order_by="employee_name asc")
	if not team:
		return {"team": [], "summary": {}}
	ids = [t.name for t in team]
	today = nowdate()
	on_leave = {r.employee: r.leave_type for r in frappe.get_all("Leave Application", filters={
		"employee": ["in", ids], "docstatus": 1, "status": "Approved", "from_date": ["<=", today], "to_date": [">=", today]},
		fields=["employee", "leave_type"])}
	checkins = {}
	for c in frappe.get_all("Employee Checkin", filters={"employee": ["in", ids], "time": ["between", [f"{today} 00:00:00", f"{today} 23:59:59"]]},
							fields=["employee", "time", "log_type"], order_by="time asc"):
		checkins.setdefault(c.employee, []).append(c)
	pending = frappe.db.count("Leave Application", {"employee": ["in", ids], "docstatus": 0, "status": "Open"})
	out = []
	for t in team:
		logs = checkins.get(t.name, [])
		state = "on_leave" if t.name in on_leave else ("in" if logs and logs[-1].log_type != "OUT" else "out" if logs else "not_in")
		out.append({**t, "state": state, "leave_type": on_leave.get(t.name),
					"first_in": str(logs[0].time) if logs else None, "last": str(logs[-1].time) if logs else None})
	summary = {k: sum(1 for r in out if r["state"] == k) for k in ("in", "out", "on_leave", "not_in")}
	summary["pending_leave"] = pending
	return {"team": out, "summary": summary}
