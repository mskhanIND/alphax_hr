"""Employee requests: one engine for letters, government services, finance, travel, assets and separation.

Request types are configuration (fields, approvals, SLA, letter). A request moves
Pending Manager -> Pending HR -> Approved (-> Completed), or Rejected / Cancelled.
"""
from __future__ import annotations

import json

import frappe
from frappe import _
from frappe.utils import add_days, cint, flt, getdate, now_datetime, nowdate

from alphax_hr.api._common import current_employee, is_hr, login_required, parse_json, require_hr, require_hr_manager

OPEN = ("Pending Manager", "Pending HR")
FIELD_TYPES = {"Data", "Date", "Time", "Int", "Currency", "Select", "Text", "Check"}
EFFECTS = ("Excuse late arrival", "Excuse early exit")

# Seeded on install; HR can edit or add types afterwards.
DEFAULT_TYPES = [
	{"request_type_name": "Salary Certificate", "title_ar": "تعريف بالراتب", "category": "Letter", "needs_manager": 0, "output": "Letter",
	 "sla_days": 2, "fields": [{"fieldname": "addressed_to", "label": "Addressed to", "label_ar": "موجه إلى", "type": "Data", "reqd": 1},
							   {"fieldname": "purpose", "label": "Purpose", "label_ar": "الغرض", "type": "Select",
								"options": ["Bank", "Embassy", "Government", "Other"], "reqd": 1}],
	 "letter_title": "Salary Certificate", "letter_body":
		"This is to certify that {{ employee.employee_name }} ({{ employee.nationality }}, ID {{ employee.id }}) has been working with "
		"{{ company }} as {{ employee.designation }} since {{ employee.date_of_joining }}{% if salary %}, with a total monthly salary of "
		"{{ salary.gross }} {{ salary.currency }}{% endif %}. This certificate is issued at the employee's request to {{ details.addressed_to }} "
		"without any liability on the company.",
	 "letter_body_ar":
		"تشهد {{ company }} بأن {{ employee.employee_name }} (الهوية {{ employee.id }}) يعمل لديها بوظيفة {{ employee.designation }} منذ "
		"{{ employee.date_of_joining }}{% if salary %} براتب شهري إجمالي قدره {{ salary.gross }} {{ salary.currency }}{% endif %}، "
		"وقد أُعطيت له هذه الشهادة بناءً على طلبه لتقديمها إلى {{ details.addressed_to }} دون أدنى مسؤولية على الشركة."},
	{"request_type_name": "Employment Letter", "title_ar": "خطاب تعريف", "category": "Letter", "needs_manager": 0, "output": "Letter",
	 "sla_days": 2, "fields": [{"fieldname": "addressed_to", "label": "Addressed to", "label_ar": "موجه إلى", "type": "Data", "reqd": 1}],
	 "letter_title": "Employment Letter", "letter_body":
		"This is to certify that {{ employee.employee_name }}, ID {{ employee.id }}, is employed by {{ company }} as {{ employee.designation }} "
		"since {{ employee.date_of_joining }}. Issued at the employee's request to {{ details.addressed_to }}.",
	 "letter_body_ar": "تشهد {{ company }} بأن {{ employee.employee_name }} (الهوية {{ employee.id }}) يعمل لديها بوظيفة {{ employee.designation }} "
					   "منذ {{ employee.date_of_joining }}، وأُعطيت له هذه الشهادة بناءً على طلبه لتقديمها إلى {{ details.addressed_to }}."},
	{"request_type_name": "Experience Letter", "title_ar": "شهادة خبرة", "category": "Letter", "needs_manager": 0, "output": "Letter", "sla_days": 3,
	 "fields": [], "letter_title": "Experience Certificate", "letter_body":
		"This is to certify that {{ employee.employee_name }} worked with {{ company }} as {{ employee.designation }} from "
		"{{ employee.date_of_joining }}{% if employee.relieving_date %} to {{ employee.relieving_date }}{% endif %}.",
	 "letter_body_ar": "تشهد {{ company }} بأن {{ employee.employee_name }} عمل لديها بوظيفة {{ employee.designation }} منذ {{ employee.date_of_joining }}"
					   "{% if employee.relieving_date %} حتى {{ employee.relieving_date }}{% endif %}."},
	{"request_type_name": "Late Arrival Permission", "title_ar": "استئذان تأخير", "category": "Attendance", "needs_manager": 1, "needs_hr": 0,
	 "sla_days": 1, "effect": "Excuse late arrival",
	 "description": "Ask your manager to excuse arriving late on a day (before or after it happens).",
	 "fields": [{"fieldname": "date", "label": "Date", "label_ar": "التاريخ", "type": "Date", "reqd": 1},
				{"fieldname": "time", "label": "Expected arrival time", "label_ar": "وقت الحضور المتوقع", "type": "Time", "reqd": 1}]},
	{"request_type_name": "Early Exit Permission", "title_ar": "استئذان خروج مبكر", "category": "Attendance", "needs_manager": 1, "needs_hr": 0,
	 "sla_days": 1, "effect": "Excuse early exit",
	 "description": "Ask your manager to leave before the end of your shift.",
	 "fields": [{"fieldname": "date", "label": "Date", "label_ar": "التاريخ", "type": "Date", "reqd": 1},
				{"fieldname": "time", "label": "Leaving at", "label_ar": "وقت الخروج", "type": "Time", "reqd": 1}]},
	{"request_type_name": "Exit & Re-entry Visa", "title_ar": "تأشيرة خروج وعودة", "category": "Government", "non_saudi_only": 1, "sla_days": 3,
	 "fields": [{"fieldname": "visa_type", "label": "Visa type", "label_ar": "نوع التأشيرة", "type": "Select", "options": ["Single", "Multiple"], "reqd": 1},
				{"fieldname": "from_date", "label": "Travel date", "label_ar": "تاريخ السفر", "type": "Date", "reqd": 1},
				{"fieldname": "to_date", "label": "Return date", "label_ar": "تاريخ العودة", "type": "Date", "reqd": 1},
				{"fieldname": "destination", "label": "Destination", "label_ar": "الوجهة", "type": "Data"}]},
	{"request_type_name": "Final Exit Visa", "title_ar": "تأشيرة خروج نهائي", "category": "Government", "non_saudi_only": 1, "sla_days": 5,
	 "fields": [{"fieldname": "exit_date", "label": "Exit date", "label_ar": "تاريخ الخروج", "type": "Date", "reqd": 1}]},
	{"request_type_name": "Iqama Renewal", "title_ar": "تجديد الإقامة", "category": "Government", "non_saudi_only": 1, "needs_manager": 0,
	 "sla_days": 5, "fields": []},
	{"request_type_name": "Salary Advance", "title_ar": "سلفة على الراتب", "category": "Finance", "sla_days": 3,
	 "fields": [{"fieldname": "amount", "label": "Amount", "label_ar": "المبلغ", "type": "Currency", "reqd": 1},
				{"fieldname": "months", "label": "Repay over (months)", "label_ar": "السداد خلال (أشهر)", "type": "Int", "reqd": 1}]},
	{"request_type_name": "Business Trip", "title_ar": "انتداب / رحلة عمل", "category": "Travel", "sla_days": 2,
	 "fields": [{"fieldname": "destination", "label": "Destination", "label_ar": "الوجهة", "type": "Data", "reqd": 1},
				{"fieldname": "from_date", "label": "From", "label_ar": "من", "type": "Date", "reqd": 1},
				{"fieldname": "to_date", "label": "To", "label_ar": "إلى", "type": "Date", "reqd": 1},
				{"fieldname": "purpose", "label": "Purpose", "label_ar": "الغرض", "type": "Text", "reqd": 1}]},
	{"request_type_name": "Asset Request", "title_ar": "طلب عهدة", "category": "Asset", "sla_days": 3,
	 "fields": [{"fieldname": "asset_type", "label": "Asset", "label_ar": "العهدة", "type": "Select",
				 "options": ["Laptop", "Mobile phone", "SIM card", "Vehicle", "Access card", "Other"], "reqd": 1}]},
	{"request_type_name": "Passport Release", "title_ar": "تسليم الجواز", "category": "Document", "non_saudi_only": 1, "sla_days": 2,
	 "needs_manager": 0,
	 "fields": [{"fieldname": "from_date", "label": "Needed from", "label_ar": "مطلوب من", "type": "Date", "reqd": 1},
				{"fieldname": "to_date", "label": "Return by", "label_ar": "الإرجاع بتاريخ", "type": "Date"}]},
	{"request_type_name": "Resignation", "title_ar": "استقالة", "category": "Separation", "sla_days": 5,
	 "fields": [{"fieldname": "last_working_day", "label": "Last working day", "label_ar": "آخر يوم عمل", "type": "Date", "reqd": 1}]},
	{"request_type_name": "Profile Update", "title_ar": "تحديث البيانات الشخصية", "category": "Document", "needs_manager": 0, "needs_hr": 1,
	 "sla_days": 3, "effect": "Update employee record",
	 "description": "Update your passport, Iqama, marital status or bank details. HR checks the document and updates your file.",
	 "fields": []},
	{"request_type_name": "General Request", "title_ar": "طلب عام", "category": "Other", "sla_days": 3, "fields": []},
]


def seed_types():
	if not frappe.db.exists("DocType", "AlphaX Request Type"):
		return
	for t in DEFAULT_TYPES:
		if frappe.db.exists("AlphaX Request Type", t["request_type_name"]):
			continue
		doc = {k: v for k, v in t.items() if k != "fields"}
		doc.update({"doctype": "AlphaX Request Type", "fields_json": json.dumps(t["fields"], ensure_ascii=False)})
		frappe.get_doc(doc).insert(ignore_permissions=True)


def _type_dict(t):
	return {"name": t.name, "title": t.request_type_name, "title_ar": t.title_ar, "category": t.category,
			"description": t.description, "needs_manager": cint(t.needs_manager), "needs_hr": cint(t.needs_hr),
			"requires_attachment": cint(t.requires_attachment), "non_saudi_only": cint(t.non_saudi_only),
			"sla_days": cint(t.sla_days), "output": t.output, "enabled": cint(t.enabled), "effect": t.get("effect"),
			"fields": parse_json(t.fields_json, []) or [],
			"special": t.get("effect") == "Update employee record"}


@frappe.whitelist()
def types(include_disabled=0):
	login_required()
	filters = {} if cint(include_disabled) and is_hr() else {"enabled": 1}
	rows = frappe.get_all("AlphaX Request Type", filters=filters, fields=["*"], order_by="category asc, request_type_name asc")
	return [_type_dict(t) for t in rows]


def _clean_details(spec, details):
	out = {}
	for f in spec:
		v = details.get(f["fieldname"])
		if f.get("reqd") and v in (None, "", []):
			frappe.throw(_("Please fill in: {0}").format(f.get("label")), title=_("Missing information"))
		if v in (None, ""):
			continue
		if f.get("type") == "Select" and f.get("options") and v not in f["options"]:
			frappe.throw(_("Invalid value for {0}.").format(f.get("label")))
		if f.get("type") in ("Int",):
			v = cint(v)
		elif f.get("type") == "Currency":
			v = flt(v, 2)
			if v <= 0:
				frappe.throw(_("{0} must be more than zero.").format(f.get("label")))
		elif f.get("type") == "Date":
			v = str(getdate(v))
		elif f.get("type") == "Time":
			v = str(v).strip()[:8]
			parts = v.split(":")
			if len(parts) < 2 or not all(p.isdigit() for p in parts) or not (0 <= int(parts[0]) < 24 and 0 <= int(parts[1]) < 60):
				frappe.throw(_("Invalid time for {0} (use HH:MM).").format(f.get("label")))
			v = f"{int(parts[0]):02d}:{int(parts[1]):02d}"
		elif f.get("type") == "Check":
			v = 1 if cint(v) else 0
		else:
			v = str(v)[:2000]
		out[f["fieldname"]] = v
	if out.get("from_date") and out.get("to_date") and getdate(out["to_date"]) < getdate(out["from_date"]):
		frappe.throw(_("The end date is before the start date."))
	return out


def _manager(employee):
	e = frappe.db.get_value("Employee", employee, ["leave_approver", "reports_to"], as_dict=True)
	if e.reports_to:
		user = frappe.db.get_value("Employee", e.reports_to, "user_id")
		if user:
			return user
	return e.leave_approver


@frappe.whitelist(methods=["POST"])
def create(request_type, details=None, reason=None, employee=None):
	"""Raise a request (for yourself; HR may raise one for any employee)."""
	user = login_required()
	if employee and employee != current_employee(required=False):
		require_hr()
	employee = employee or current_employee()
	t = frappe.get_doc("AlphaX Request Type", request_type)
	if not cint(t.enabled):
		frappe.throw(_("This request type is not available."))
	if t.get("effect") == "Update employee record":
		frappe.throw(_("Use My Profile → Request a change to update your details."))
	if cint(t.non_saudi_only) and cint(frappe.db.get_value("Employee", employee, "alphax_is_saudi")):
		frappe.throw(_("{0} is only for non-Saudi employees.").format(t.request_type_name))
	data = _clean_details(parse_json(t.fields_json, []) or [], parse_json(details, {}) or {})
	if t.request_type_name == "Resignation":
		_check_resignation(employee, data)
	if t.get("effect"):
		_check_permission(employee, t, data)
	approver = _manager(employee) if cint(t.needs_manager) else None
	if approver == user:
		approver = None  # a manager's own request skips their own approval
	status = "Pending Manager" if approver else ("Pending HR" if cint(t.needs_hr) else "Approved")
	doc = frappe.get_doc({"doctype": "AlphaX Request", "employee": employee, "request_type": request_type, "status": status,
						  "approver": approver, "details": json.dumps(data, ensure_ascii=False), "reason": (reason or "")[:2000],
						  "due_on": add_days(nowdate(), cint(t.sla_days) or 3)})
	doc.flags.alphax_engine = True
	doc.insert()
	if status == "Approved":
		_on_approved(doc, t)
	return {"name": doc.name, "status": doc.status}


def _check_resignation(employee, data):
	notice = cint(frappe.db.get_value("Employee", employee, "notice_number_of_days")) or 30
	lwd = getdate(data["last_working_day"])
	if lwd < getdate(nowdate()):
		frappe.throw(_("The last working day cannot be in the past."))
	if (lwd - getdate(nowdate())).days + 1 < notice:
		data["short_notice"] = _("Shorter than the {0}-day notice period (Art. 75).").format(notice)


def _check_permission(employee, t, data):
	"""Late/early permissions: one per day and type, within a week back / a month ahead, monthly limit."""
	from alphax_hr.api._common import settings

	day = getdate(data.get("date"))
	if not data.get("date"):
		frappe.throw(_("Please choose the date."))
	if day < getdate(add_days(nowdate(), -7)) or day > getdate(add_days(nowdate(), 30)):
		frappe.throw(_("Permissions can be requested up to 7 days after the day and 30 days before it."))
	same_effect = frappe.get_all("AlphaX Request Type", filters={"effect": t.effect}, pluck="name")
	active = frappe.get_all("AlphaX Request", filters={"employee": employee, "request_type": ["in", same_effect],
													   "status": ["not in", ["Rejected", "Cancelled"]]}, fields=["details"])
	days = [getdate((parse_json(r.details, {}) or {}).get("date")) for r in active if (parse_json(r.details, {}) or {}).get("date")]
	if day in days:
		frappe.throw(_("You already have a {0} for {1}.").format(t.request_type_name, frappe.utils.formatdate(day)))
	limit = cint(settings().get("permissions_per_month"))
	from alphax_hr.api.attendance_policy import for_employee

	pol = for_employee(employee)
	if pol and str(pol.permissions_per_month or "").strip() != "":
		limit = cint(pol.permissions_per_month)
	if limit:
		all_types = frappe.get_all("AlphaX Request Type", filters={"effect": ["in", list(EFFECTS)]}, pluck="name")
		month = [r for r in frappe.get_all("AlphaX Request", filters={"employee": employee, "request_type": ["in", all_types],
																	 "status": ["not in", ["Rejected", "Cancelled"]]}, fields=["details"])
				 if (d := (parse_json(r.details, {}) or {}).get("date")) and getdate(d).month == day.month and getdate(d).year == day.year]
		if len(month) >= limit:
			frappe.throw(_("You have used all {0} late/early permissions for this month.").format(limit))


def excused(employees, start, end):
	"""{(employee, date): {"late": "HH:MM" or True, "early": ...}} from approved permissions."""
	types = {r.name: r.effect for r in frappe.get_all("AlphaX Request Type", filters={"effect": ["in", list(EFFECTS)]}, fields=["name", "effect"])} \
		if frappe.db.exists("DocType", "AlphaX Request Type") and frappe.get_meta("AlphaX Request Type").has_field("effect") else {}
	if not types or not employees:
		return {}
	out = {}
	for r in frappe.get_all("AlphaX Request", filters={"employee": ["in", list(employees)], "request_type": ["in", list(types)],
													   "status": ["in", ["Approved", "Completed"]]}, fields=["employee", "request_type", "details"]):
		d = parse_json(r.details, {}) or {}
		if not d.get("date"):
			continue
		day = getdate(d["date"])
		if getdate(start) <= day <= getdate(end):
			key = "late" if types[r.request_type] == "Excuse late arrival" else "early"
			out.setdefault((r.employee, day), {})[key] = d.get("time") or True
	return out


def actions_for(doc, user):
	"""Approve / Reject / Complete / Cancel available to this user for one request."""
	hr = is_hr(user)
	acts = []
	if doc.status == "Pending Manager" and (doc.approver == user or hr):
		acts = ["Approve", "Reject"]
	elif doc.status == "Pending HR" and hr:
		acts = ["Approve", "Reject"]
	elif doc.status == "Approved" and hr:
		acts = ["Complete"]
	own = frappe.db.get_value("Employee", {"user_id": user}, "name")
	if doc.status in OPEN and doc.employee == own:
		acts.append("Cancel")
	return acts


def decide(name, action, comment=None):
	user = login_required()
	doc = frappe.get_doc("AlphaX Request", name)
	if action not in actions_for(doc, user):
		frappe.throw(_("You cannot perform '{0}' on this request.").format(action), frappe.PermissionError)
	t = frappe.get_doc("AlphaX Request Type", doc.request_type)
	if comment:
		doc.add_comment("Comment", frappe.utils.escape_html(str(comment)[:2000]))
	if action == "Reject":
		doc.status = "Rejected"
	elif action == "Cancel":
		doc.status = "Cancelled"
	elif action == "Complete":
		doc.status = "Completed"
		if comment:
			doc.hr_note = str(comment)[:2000]
	elif action == "Approve":
		if t.get("effect") == "Update employee record" and _needs_document(parse_json(doc.details, {}) or {}) \
				and not frappe.db.exists("File", {"attached_to_doctype": "AlphaX Request", "attached_to_name": name}):
			frappe.throw(_("Ask the employee to attach a copy of the new document first."))
		if cint(t.requires_attachment) and not frappe.db.exists("File", {"attached_to_doctype": "AlphaX Request", "attached_to_name": name}):
			frappe.throw(_("{0} needs a supporting document before approval.").format(t.request_type_name))
		doc.status = "Pending HR" if doc.status == "Pending Manager" and cint(t.needs_hr) else "Approved"
	if action != "Cancel":
		doc.decided_by, doc.decided_on = user, now_datetime()
	doc.flags.alphax_engine = True
	doc.save(ignore_permissions=True)  # permission checked above via actions_for
	if doc.status == "Approved":
		_on_approved(doc, t)
	return {"name": doc.name, "status": doc.status}


def _on_approved(doc, t):
	details = parse_json(doc.details, {}) or {}
	if t.get("effect") == "Update employee record":
		_apply_profile_changes(doc, details)
		return
	if t.get("effect"):
		doc.status = "Completed"  # nothing for HR to do: the attendance register reads it
		doc.flags.alphax_engine = True
		doc.save(ignore_permissions=True)
	if t.output == "Letter":
		doc.letter = _make_letter(doc, t, details)
		doc.status = "Completed"
		doc.flags.alphax_engine = True
		doc.save(ignore_permissions=True)
	if t.request_type_name == "Resignation":
		emp = frappe.get_doc("Employee", doc.employee)
		emp.resignation_letter_date = getdate(doc.creation)
		emp.relieving_date = details.get("last_working_day")
		emp.flags.ignore_mandatory = True
		emp.save(ignore_permissions=True)


def _letter_context(doc, details):
	from alphax_hr.api.contract import contract_data

	data = contract_data(doc.employee)
	emp = frappe.get_doc("Employee", doc.employee)
	return {"employee": {"employee_name": emp.employee_name, "id": data["employee"]["id"], "nationality": data["employee"]["nationality"],
						 "designation": emp.designation or "", "date_of_joining": frappe.utils.formatdate(emp.date_of_joining),
						 "relieving_date": frappe.utils.formatdate(emp.relieving_date) if emp.relieving_date else ""},
			"company": data["company"]["name"], "company_ar": data["company"]["name_ar"], "details": frappe._dict(details),
			"salary": frappe._dict({"gross": f"{data['salary']['gross']:,.2f}", "currency": data["salary"]["currency"]}) if data["salary"] else None,
			"today": frappe.utils.formatdate(nowdate())}


def _make_letter(doc, t, details):
	from frappe.utils.pdf import get_pdf

	ctx = _letter_context(doc, details)
	body = frappe.render_template(t.letter_body or "", ctx)
	body_ar = frappe.render_template(t.letter_body_ar or "", ctx)
	html = frappe.render_template("alphax_hr/templates/alphax/letter.html",
								  {**ctx, "title": t.letter_title or t.request_type_name, "title_ar": t.title_ar or "",
								   "body": body, "body_ar": body_ar, "ref": doc.name})
	f = frappe.get_doc({"doctype": "File", "file_name": f"{doc.name}.pdf", "content": get_pdf(html), "is_private": 1,
						"attached_to_doctype": "AlphaX Request", "attached_to_name": doc.name}).insert(ignore_permissions=True)
	return f.file_url


def _row(r):
	return {**r, "messages": 0, "details": parse_json(r.get("details"), {}) or {}, "overdue": bool(r.get("due_on") and r.status in OPEN
																					  and getdate(r.due_on) < getdate(nowdate()))}


FIELDS = ["name", "employee", "employee_name", "request_type", "status", "approver", "due_on", "creation", "details", "reason",
		  "letter", "decided_by", "decided_on", "department"]


def _attach_counts(rows):
	users = {r["name"]: frappe.db.get_value("Employee", r["employee"], "user_id") for r in rows}
	counts = message_counts([r["name"] for r in rows], users)
	for r in rows:
		c = counts.get(r["name"], {})
		r["messages"] = c.get("count", 0)
		r["last_from_employee"] = c.get("last_from_employee", False)
	return rows


@frappe.whitelist()
def mine(limit=50):
	employee = current_employee()
	return _attach_counts([_row(r) for r in frappe.get_list("AlphaX Request", filters={"employee": employee}, fields=FIELDS,
															 order_by="creation desc", page_length=min(cint(limit) or 50, 200))])


@frappe.whitelist()
def all_requests(status=None, request_type=None, department=None, overdue=0, limit=200):
	require_hr()
	filters = {}
	if status == "open":
		filters["status"] = ["in", list(OPEN)]
	elif status:
		filters["status"] = status
	if request_type:
		filters["request_type"] = request_type
	if department:
		filters["department"] = department
	rows = [_row(r) for r in frappe.get_list("AlphaX Request", filters=filters, fields=FIELDS, order_by="creation desc",
											 page_length=min(cint(limit) or 200, 1000))]
	if cint(overdue):
		rows = [r for r in rows if r["overdue"]]
	_attach_counts(rows)
	counts = {}
	for r in frappe.get_list("AlphaX Request", fields=["status", "count(name) as n"], group_by="status"):
		counts[r.status] = r.n
	return {"rows": rows, "counts": counts}


@frappe.whitelist(methods=["POST"])
def update_type(name, data):
	require_hr_manager()
	payload = parse_json(data, {})
	t = frappe.get_doc("AlphaX Request Type", name)
	for k in ("enabled", "needs_manager", "needs_hr", "requires_attachment", "non_saudi_only", "sla_days", "description",
			  "title_ar", "letter_body", "letter_body_ar", "letter_title"):
		if k in payload:
			t.set(k, payload[k])
	if "fields" in payload:
		spec = payload["fields"] or []
		for fdef in spec:
			if not fdef.get("fieldname") or fdef.get("type") not in FIELD_TYPES:
				frappe.throw(_("Each field needs a fieldname and a type ({0}).").format(", ".join(sorted(FIELD_TYPES))))
		t.fields_json = json.dumps(spec, ensure_ascii=False)
	t.save()
	return _type_dict(t)


def query_conditions(user=None):
	"""Employees see their own requests and the ones waiting on them; HR sees all."""
	user = user or frappe.session.user
	if user == "Administrator" or is_hr(user):
		return ""
	emp = frappe.db.get_value("Employee", {"user_id": user}, "name") or ""
	return "(`tabAlphaX Request`.employee = {0} or `tabAlphaX Request`.approver = {1})".format(
		frappe.db.escape(emp), frappe.db.escape(user))


def has_permission(doc, ptype=None, user=None):
	user = user or frappe.session.user
	if user == "Administrator" or is_hr(user):
		return True
	emp = frappe.db.get_value("Employee", {"user_id": user}, "name")
	return bool((emp and doc.employee == emp) or doc.approver == user)


@frappe.whitelist(methods=["POST"])
def cancel(name):
	"""The employee withdraws an open request."""
	return decide(name, "Cancel")


# ------------------------------------------------------------------ profile updates (HR approves)
PROFILE_CHANGE_FIELDS = (
	("passport_number", "Passport number", True), ("valid_upto", "Passport expiry", True), ("date_of_issue", "Passport issue date", True),
	("place_of_issue", "Passport place of issue", True), ("alphax_iqama_number", "Iqama / ID number", True),
	("alphax_iqama_expiry", "Iqama / ID expiry", True), ("alphax_work_permit_expiry", "Work permit expiry", True),
	("marital_status", "Marital status", False), ("blood_group", "Blood group", False),
	("alphax_employee_name_ar", "Full name (Arabic)", False), ("bank_name", "Bank", False), ("iban", "IBAN", False),
	("bank_ac_no", "Bank account number", False),
)


def profile_fields():
	meta = frappe.get_meta("Employee")
	out = []
	for fn, label, document in PROFILE_CHANGE_FIELDS:
		df = meta.get_field(fn)
		if not df:
			continue
		spec = {"fieldname": fn, "label": _(label), "fieldtype": df.fieldtype, "document": document}
		if df.fieldtype == "Select":
			spec["options"] = (df.options or "").split("\n")
		elif df.fieldtype == "Link":
			spec["options"] = df.options
		out.append(spec)
	return out


def _needs_document(details):
	docs = {fn for fn, _l, d in PROFILE_CHANGE_FIELDS if d}
	return bool(set((details.get("changes") or {})) & docs)


def create_profile_update(employee, changes, reason=None):
	t_name = frappe.db.get_value("AlphaX Request Type", {"effect": "Update employee record", "enabled": 1})
	if not t_name:
		frappe.throw(_("Profile updates are not enabled. Ask HR."))
	specs = {f["fieldname"]: f for f in profile_fields()}
	emp = frappe.get_doc("Employee", employee)
	clean = {}
	for fn, value in (parse_json(changes, {}) or {}).items():
		if fn not in specs:
			frappe.throw(_("{0} cannot be changed here.").format(fn))
		spec = specs[fn]
		value = (str(value).strip() if value is not None else "")[:140]
		if not value:
			continue
		if spec["fieldtype"] == "Date":
			value = str(getdate(value))
		if spec["fieldtype"] == "Select" and spec.get("options") and value not in spec["options"]:
			frappe.throw(_("Invalid value for {0}.").format(spec["label"]))
		if spec["fieldtype"] == "Link" and not frappe.db.exists(spec["options"], value):
			frappe.throw(_("{0} '{1}' does not exist.").format(spec["label"], value))
		if str(emp.get(fn) or "") == value:
			continue
		clean[fn] = {"label": spec["label"], "from": str(emp.get(fn) or ""), "to": value}
	if not clean:
		frappe.throw(_("Nothing has changed."))
	if frappe.db.exists("AlphaX Request", {"employee": employee, "request_type": t_name, "status": ["in", list(OPEN)]}):
		frappe.throw(_("You already have a profile update waiting for HR."))
	t = frappe.get_doc("AlphaX Request Type", t_name)
	doc = frappe.get_doc({"doctype": "AlphaX Request", "employee": employee, "request_type": t_name, "status": "Pending HR",
						  "details": json.dumps({"changes": clean}, ensure_ascii=False), "reason": (reason or "")[:2000],
						  "due_on": add_days(nowdate(), cint(t.sla_days) or 3)})
	doc.flags.alphax_engine = True
	doc.insert(ignore_permissions=True)
	return {"name": doc.name, "status": doc.status, "needs_document": _needs_document({"changes": clean})}


def _apply_profile_changes(doc, details):
	emp = frappe.get_doc("Employee", doc.employee)
	for fn, c in (details.get("changes") or {}).items():
		if emp.meta.has_field(fn):
			emp.set(fn, c["to"])
	emp.flags.ignore_mandatory = True
	emp.flags.ignore_links = True  # Link values were checked when the employee asked
	emp.save(ignore_permissions=True)
	for f in frappe.get_all("File", filters={"attached_to_doctype": "AlphaX Request", "attached_to_name": doc.name},
							fields=["file_url", "file_name", "is_private"]):
		frappe.get_doc({"doctype": "File", "file_url": f.file_url, "file_name": f.file_name, "is_private": f.is_private,
						"attached_to_doctype": "Employee", "attached_to_name": doc.employee}).insert(ignore_permissions=True)
	doc.status = "Completed"
	doc.flags.alphax_engine = True
	doc.save(ignore_permissions=True)


# ------------------------------------------------------------------ conversation with HR
def _can_talk(doc, user):
	if is_hr(user) or doc.approver == user:
		return True
	return doc.employee == frappe.db.get_value("Employee", {"user_id": user}, "name")


@frappe.whitelist()
def messages(name):
	user = login_required()
	doc = frappe.get_doc("AlphaX Request", name)
	if not _can_talk(doc, user):
		frappe.throw(_("Not permitted."), frappe.PermissionError)
	rows = frappe.get_all("Comment", filters={"reference_doctype": "AlphaX Request", "reference_name": name, "comment_type": "Comment"},
						  fields=["name", "content", "owner", "creation"], order_by="creation asc")
	emp_user = frappe.db.get_value("Employee", doc.employee, "user_id")
	return [{"text": frappe.utils.strip_html(r.content or ""), "by": frappe.utils.get_fullname(r.owner), "at": str(r.creation),
			 "mine": r.owner == user, "from_employee": r.owner == emp_user} for r in rows]


@frappe.whitelist(methods=["POST"])
def post_message(name, text):
	user = login_required()
	doc = frappe.get_doc("AlphaX Request", name)
	if not _can_talk(doc, user):
		frappe.throw(_("Not permitted."), frappe.PermissionError)
	text = (text or "").strip()[:2000]
	if not text:
		frappe.throw(_("Write a message first."))
	doc.add_comment("Comment", frappe.utils.escape_html(text))
	emp_user = frappe.db.get_value("Employee", doc.employee, "user_id")
	to = emp_user if user != emp_user else (doc.approver if doc.status == "Pending Manager" else doc.decided_by)
	if to and to != user:
		frappe.get_doc({"doctype": "Notification Log", "for_user": to, "type": "Alert", "document_type": "AlphaX Request",
						"document_name": doc.name, "from_user": user,
						"subject": _("New message on {0}: {1}").format(doc.request_type, text[:80])}).insert(ignore_permissions=True)
	return messages(name)


def message_counts(names, employee_users):
	"""{request: {"count": n, "last_from_employee": bool}} for list views."""
	out = {}
	if not names:
		return out
	for c in frappe.get_all("Comment", filters={"reference_doctype": "AlphaX Request", "reference_name": ["in", names],
												 "comment_type": "Comment"}, fields=["reference_name", "owner"], order_by="creation asc"):
		o = out.setdefault(c.reference_name, {"count": 0, "last_from_employee": False})
		o["count"] += 1
		o["last_from_employee"] = c.owner == employee_users.get(c.reference_name)
	return out
