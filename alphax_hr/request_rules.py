"""Checks that every request must pass before it is saved, and the overlap control between leave, business trips,
attendance requests and late/early permissions.

All messages are written for the employee: what is wrong and what to do instead.
"""
from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import add_days, cint, date_diff, flt, formatdate, getdate, nowdate

from alphax_hr.api._common import parse_json

TRIP = "Business Trip"
OPEN_REQUEST = ["not in", ["Rejected", "Cancelled"]]

# Longest sensible spans; anything longer is almost always a typing mistake (e.g. a return date in 2037).
MAX_TRIP_DAYS = 90
MAX_PASSPORT_DAYS = 180
MAX_EXIT_REENTRY_DAYS = 365
MAX_FUTURE_DAYS = 365
BACKDATE_DAYS = 7

# Request types that may only be open once at a time per employee.
ONE_OPEN = {"Resignation", "Final Exit Visa", "Loan Request", "Salary Advance", "Loan Postponement", "Iqama Renewal",
			"Passport Release", "Appraisal Request"}


def _today():
	return getdate(nowdate())


def _fmt(d):
	return formatdate(d)


# ---------------------------------------------------------------- overlap (leave · trip · permission · attendance)
def leave_on(employee, start, end=None, exclude=None):
	"""Open or approved leave applications touching [start, end]."""
	end = end or start
	filters = {"employee": employee, "docstatus": ["<", 2], "status": ["not in", ["Rejected", "Cancelled"]],
			   "from_date": ["<=", end], "to_date": [">=", start]}
	if exclude:
		filters["name"] = ["!=", exclude]
	return frappe.get_all("Leave Application", filters=filters, fields=["name", "leave_type", "from_date", "to_date", "status"])


def _trip_types():
	return frappe.get_all("AlphaX Request Type", filters={"category": "Travel"}, pluck="name") or [TRIP]


def trips_on(employee, start, end=None, exclude=None):
	"""Open or approved business trips touching [start, end]."""
	end = getdate(end or start)
	start = getdate(start)
	filters = {"employee": employee, "request_type": ["in", _trip_types()], "status": OPEN_REQUEST}
	if exclude:
		filters["name"] = ["!=", exclude]
	out = []
	for r in frappe.get_all("AlphaX Request", filters=filters, fields=["name", "request_type", "details", "status"]):
		d = parse_json(r.details, {}) or {}
		if not d.get("from_date"):
			continue
		f, t = getdate(d["from_date"]), getdate(d.get("to_date") or d["from_date"])
		if f <= end and t >= start:
			out.append({"name": r.name, "from_date": f, "to_date": t, "status": r.status})
	return out


def _describe_leave(rows):
	r = rows[0]
	return _("{0} from {1} to {2} ({3})").format(_(r.leave_type), _fmt(r.from_date), _fmt(r.to_date), r.name)


def _describe_trip(rows):
	r = rows[0]
	return _("business trip from {0} to {1} ({2})").format(_fmt(r["from_date"]), _fmt(r["to_date"]), r["name"])


def check_trip_overlap(employee, start, end, exclude=None):
	if lv := leave_on(employee, start, end):
		frappe.throw(_("You are on leave in these dates: {0}. Change or cancel the leave first.").format(_describe_leave(lv)),
					 title=_("Dates overlap"))
	if tr := trips_on(employee, start, end, exclude=exclude):
		frappe.throw(_("You already have a {0}.").format(_describe_trip(tr)), title=_("Dates overlap"))


def check_day_is_working(employee, day, what):
	"""A late/early permission or an attendance request makes no sense on a day of leave or travel."""
	if lv := leave_on(employee, day):
		frappe.throw(_("{0} is not needed on {1}: you are on {2}.").format(what, _fmt(day), _describe_leave(lv)), title=_("Dates overlap"))
	if tr := trips_on(employee, day):
		frappe.throw(_("{0} is not needed on {1}: you are on a {2}.").format(what, _fmt(day), _describe_trip(tr)), title=_("Dates overlap"))


def validate_leave_overlap(doc):
	"""Leave Application: refuse leave on the days of an open or approved business trip."""
	if doc.get("status") in ("Rejected", "Cancelled") or not doc.from_date or not doc.to_date:
		return
	if tr := trips_on(doc.employee, doc.from_date, doc.to_date):
		frappe.throw(_("These dates overlap a {0}. Change the trip or the leave dates.").format(_describe_trip(tr)), title=_("Dates overlap"))


def validate_attendance_request(doc, method=None):
	"""HRMS Attendance Request: no attendance correction for days of leave or of a business trip."""
	if doc.get("docstatus") == 2 or not doc.from_date:
		return
	end = doc.to_date or doc.from_date
	if lv := leave_on(doc.employee, doc.from_date, end):
		frappe.throw(_("These dates overlap {0}. Cancel the leave before asking to mark attendance.").format(_describe_leave(lv)),
					 title=_("Dates overlap"))
	if (doc.get("reason") or "") != "On Duty" and (tr := trips_on(doc.employee, doc.from_date, end)):
		frappe.throw(_("These dates are covered by a {0}; the trip already counts as work.").format(_describe_trip(tr)),
					 title=_("Dates overlap"))


# ---------------------------------------------------------------- per request type
def _not_past(d, label, allow_days=0):
	if getdate(d) < getdate(add_days(nowdate(), -allow_days)):
		if allow_days:
			frappe.throw(_("{0} can be at most {1} days in the past.").format(label, allow_days))
		frappe.throw(_("{0} cannot be in the past.").format(label))


def _not_too_far(d, label, days=MAX_FUTURE_DAYS):
	if getdate(d) > getdate(add_days(nowdate(), days)):
		frappe.throw(_("{0} is more than {1} days ahead. Please check the date.").format(label, days))


def _span(start, end, max_days, what):
	days = date_diff(end, start) + 1
	if days > max_days:
		frappe.throw(_("{0} is {1} days long; the longest allowed is {2} days. Please check the dates.").format(what, days, max_days))


def _iqama_valid_until(employee, day, what):
	exp = frappe.db.get_value("Employee", employee, "alphax_iqama_expiry") \
		if frappe.get_meta("Employee").has_field("alphax_iqama_expiry") else None
	if exp and getdate(exp) < getdate(day):
		frappe.throw(_("Your Iqama expires on {0}, before {1}. Request an Iqama renewal first.").format(_fmt(exp), what))


def _one_open(employee, request_type):
	if request_type not in ONE_OPEN:
		return
	open_ = frappe.get_all("AlphaX Request", filters={"employee": employee, "request_type": request_type,
													  "status": ["in", ["Pending Manager", "Pending HR", "Pending Management"]]}, pluck="name")
	if open_:
		frappe.throw(_("You already have a {0} waiting for approval ({1}). Wait for the decision or withdraw it first.").format(
			_(request_type), open_[0]), title=_("Already requested"))


def _same_pending(employee, request_type, data):
	"""Stops double submissions: the very same request still waiting."""
	for r in frappe.get_all("AlphaX Request", filters={"employee": employee, "request_type": request_type,
													   "status": ["in", ["Pending Manager", "Pending HR", "Pending Management"]]},
							fields=["name", "details"]):
		d = parse_json(r.details, {}) or {}
		if d and {k: v for k, v in d.items() if k != "short_notice"} == data:
			frappe.throw(_("The same request is already waiting ({0}).").format(r.name), title=_("Already requested"))


def active_loans(employee):
	"""Loans still being repaid, newest first: [{name, label}]"""
	if not frappe.db.exists("DocType", "AlphaX Loan"):
		return []
	rows = frappe.get_all("AlphaX Loan", filters={"employee": employee, "status": ["in", ["Disbursed", "Repaying"]],
												  "loan_type": "Loan"},
						  fields=["name", "amount", "creation"], order_by="creation desc")
	out = []
	for r in rows:
		left = frappe.db.count("AlphaX Loan Installment", {"parent": r.name, "status": "Scheduled"})
		if left:
			out.append({"name": r.name, "label": f"{r.name} · {flt(r.amount):,.2f}"})
	return out


def validate(employee, request_type, data):
	"""Run every check for a new request. ``data`` is the cleaned details (dates as ISO strings)."""
	name = request_type
	_one_open(employee, name)
	_same_pending(employee, name, data)
	f, t = data.get("from_date"), data.get("to_date")

	if name == TRIP or (f and t and frappe.db.get_value("AlphaX Request Type", name, "category") == "Travel"):
		_not_past(f, _("The trip start"), BACKDATE_DAYS)
		_not_too_far(f, _("The trip start"))
		_span(f, t, MAX_TRIP_DAYS, _("The trip"))
		check_trip_overlap(employee, f, t)

	elif name == "Exit & Re-entry Visa":
		_not_past(f, _("The travel date"))
		_not_too_far(f, _("The travel date"))
		_span(f, t, MAX_EXIT_REENTRY_DAYS, _("The visa period"))
		_iqama_valid_until(employee, f, _("the travel date"))

	elif name == "Final Exit Visa":
		_not_past(data["exit_date"], _("The exit date"))
		_not_too_far(data["exit_date"], _("The exit date"), 180)

	elif name == "Passport Release":
		_not_past(f, _("The date the passport is needed"))
		_not_too_far(f, _("The date the passport is needed"), 90)
		if t:
			_span(f, t, MAX_PASSPORT_DAYS, _("Keeping the passport"))

	elif name == "Resignation":
		_not_too_far(data["last_working_day"], _("The last working day"))

	elif name in ("Loan Request", "Salary Advance"):
		from alphax_hr.api.loans import _next_month, _validate_terms

		months = cint(data.get("months")) or 1
		if months < 1:
			frappe.throw(_("Repay over at least 1 month."))
		kind = "Salary advance" if name == "Salary Advance" else "Loan"
		terms = _validate_terms(employee, kind, flt(data.get("amount")), months, _next_month(), 0)
		if terms["problems"]:
			frappe.throw("<br>".join(terms["problems"][:3] + [
				_("Spread it over at least {0} months to stay within 10% of your wage (Art. 92).").format(terms["min_months"])]),
				title=_("Saudi Labor Law limits"))

	elif name == "Loan Postponement":
		loans = active_loans(employee)
		if not loans:
			frappe.throw(_("You have no loan being repaid, so there is nothing to postpone."), title=_("No loan"))
		loan = data.get("loan") or (loans[0]["name"] if len(loans) == 1 else None)
		if not loan:
			frappe.throw(_("Choose which loan to postpone."))
		if loan not in {x["name"] for x in loans}:
			frappe.throw(_("Loan {0} is not one of your loans being repaid.").format(loan))
		data["loan"] = loan
		if not 1 <= cint(data.get("months")) <= 3:
			frappe.throw(_("An installment can be postponed by 1 to 3 months."))

	elif name == "Appraisal Request":
		inc = data.get("proposed_increase")
		if inc not in (None, "") and not 0 < cint(inc) <= 100:
			frappe.throw(_("The proposed increase must be between 1% and 100%."))
		if data.get("effective_date"):
			_not_past(data["effective_date"], _("The effective date"), 31)
			_not_too_far(data["effective_date"], _("The effective date"))

	elif name in ("Late Arrival Permission", "Early Exit Permission") or data.get("date") and data.get("time"):
		check_day_is_working(employee, data["date"], _(name))

	# Any other dated request: dates must be sensible.
	for key in ("date", "from_date", "to_date", "exit_date", "last_working_day", "effective_date"):
		if data.get(key):
			_not_too_far(data[key], _("The date"), 730)
	return data


def type_extras(t, employee):
	"""Per-employee adjustments of a request type for the form: the employee's loans to postpone, or why it is unavailable."""
	if t.get("request_type_name") != "Loan Postponement" or not employee:
		return {}
	loans = active_loans(employee)
	if not loans:
		return {"unavailable": _("You have no loan being repaid.")}
	fields = [f for f in (parse_json(t.get("fields_json"), []) or []) if f.get("fieldname") != "loan"]
	fields.insert(0, {"fieldname": "loan", "label": "Loan", "label_ar": "القرض", "type": "Select", "reqd": 1,
					  "options": [x["name"] for x in loans], "option_labels": {x["name"]: x["label"] for x in loans}})
	return {"fields": fields}
