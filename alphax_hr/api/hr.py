"""HR core: employee directory, profile, create/update, lookups."""
from __future__ import annotations

import re

import frappe
from frappe import _
from frappe.utils import cint, get_datetime, getdate, nowdate

from alphax_hr.api._common import clamp_page, parse_json, require_hr
from alphax_hr.saudi import documents

LIST_FIELDS = ["name", "employee_name", "image", "department", "designation", "branch", "company",
			   "status", "date_of_joining", "user_id", "alphax_is_saudi", "cell_number", "company_email",
			   "alphax_iqama_number", "alphax_iqama_expiry", "reports_to", "employment_type"]
EXPORT_LIMIT = 5000

SECTIONS = {
	"personal": ["first_name", "middle_name", "last_name", "alphax_employee_name_ar", "gender", "date_of_birth", "marital_status",
				 "blood_group", "salutation"],
	"job": ["company", "department", "designation", "branch", "employment_type", "grade", "reports_to",
			"date_of_joining", "alphax_contract_years", "final_confirmation_date", "contract_end_date", "notice_number_of_days",
			"alphax_probation_end_date", "status"],
	"attendance_leave": ["holiday_list", "default_shift", "attendance_device_id", "leave_approver",
						 "expense_approver", "shift_request_approver"],
	"contact": ["cell_number", "personal_email", "company_email", "prefered_contact_email", "user_id",
				"current_address", "permanent_address", "person_to_be_contacted", "emergency_phone_number", "relation"],
	"saudi": ["alphax_is_saudi", "alphax_gosi_registration_date", "alphax_gosi_number", "alphax_iqama_number",
			  "alphax_iqama_expiry", "alphax_border_number", "alphax_work_permit_expiry",
			  "alphax_medical_insurance_expiry", "passport_number", "valid_upto", "alphax_annual_leave_days"],
	"bank": ["salary_mode", "bank_name", "bank_ac_no", "iban"],
	"exit": ["relieving_date", "reason_for_leaving", "resignation_letter_date"],
}
EDITABLE = {f for fields in SECTIONS.values() for f in fields} - {"status"}
LOOKUP_DOCTYPES = {"Company", "Department", "Designation", "Branch", "Employment Type", "Employee Grade",
				   "Holiday List", "Shift Type", "Gender", "User", "Employee", "Leave Type", "Salary Component"}
NEW_EMPLOYEE_CORE = ["first_name", "last_name", "alphax_employee_name_ar", "gender", "date_of_birth", "date_of_joining",
					 "alphax_contract_years", "notice_number_of_days", "alphax_iqama_number", "alphax_is_saudi",
					 "alphax_iqama_expiry", "alphax_gosi_registration_date", "passport_number", "valid_upto",
					 "cell_number", "personal_email", "marital_status", "salary_mode", "bank_name", "bank_ac_no", "iban",
					 "company", "department", "designation", "branch", "employment_type", "reports_to"]
INPUT_TYPES = {"Data", "Link", "Select", "Date", "Datetime", "Check", "Int", "Float", "Currency", "Percent",
			   "Small Text", "Text", "Long Text", "Phone", "Dynamic Link", "Attach", "Attach Image"}
ATTACH_TYPES = {"Attach", "Attach Image"}
NEVER_EDIT = {"name", "owner", "creation", "modified", "modified_by", "docstatus", "idx", "status",
			  "naming_series", "employee", "user_id", "create_user_permission", "lft", "rgt", "old_parent"}


def _site_required_fields(meta):
	"""Mandatory Employee fields as configured on *this* site (core + custom fields +
	property setters from other apps), so forms adapt to each customer."""
	out = []
	for df in meta.fields:
		# Hidden or read-only mandatory fields still block saving in Frappe, so they are shown here too
		# (unless a fetch fills them).
		if not df.reqd or df.fetch_from or cint(df.permlevel) or df.fieldtype not in INPUT_TYPES:
			continue
		if df.fieldtype == "Check":  # unticked is a valid answer; Frappe never treats it as missing
			continue
		if df.fieldname in NEVER_EDIT:
			continue
		out.append(df)
	return out


def _field_spec(df):
	spec = {"fieldname": df.fieldname, "label": _(df.label or df.fieldname), "fieldtype": df.fieldtype,
			"reqd": cint(df.reqd), "default": df.default, "description": _(df.description) if df.description else None}
	if df.fieldtype == "Select":
		spec["options"] = [o for o in (df.options or "").split("\n")]
	elif df.fieldtype == "Link":
		spec["options"] = df.options
	auto = _auto_kind(df)
	if auto:
		spec["auto"] = auto
		if auto == "nationality":
			spec["saudi_value"] = saudi_value(df)
	return spec


def _auto_kind(df):
	"""Fields the form fills itself: contract dates from the joining date and period, nationality from the ID."""
	label = df.label or ""
	if df.fieldtype == "Date" and re.search(r"contract\s*start", label, re.I):
		return "contract_start"
	if df.fieldtype == "Date" and (df.fieldname == "contract_end_date" or re.search(r"contract\s*end", label, re.I)):
		return "contract_end"
	if df.fieldtype in ("Link", "Select", "Data") and re.search(r"nationality", label, re.I):
		return "nationality"
	return None


def saudi_value(df):
	"""The value that means 'Saudi' for a nationality field on this site (Link record, Select option or text)."""
	if df.fieldtype == "Select":
		return next((o for o in (df.options or "").split("\n") if "saudi" in o.lower() and "non" not in o.lower()), None)
	if df.fieldtype == "Link" and df.options:
		if df.options == "Country":
			return "Saudi Arabia" if frappe.db.exists("Country", "Saudi Arabia") else None
		hits = [n for n in frappe.get_all(df.options, filters={"name": ["like", "%saudi%"]}, pluck="name", limit_page_length=10)
				if "non" not in n.lower()]
		return sorted(hits, key=len)[0] if hits else None
	return "Saudi"


def _editable(meta):
	"""Curated sections + whatever this site makes mandatory."""
	return EDITABLE | {df.fieldname for df in _site_required_fields(meta)}


# Legacy (CentralHRMS / IRSAA) Employee fields that hold the same data as an
# AlphaX field. AlphaX fills them so HR never types the same number twice.
MIRRORS = {
	"custom_identity_number": "alphax_iqama_number",
	"iqama_national_id": "alphax_iqama_number",
	"custom_identity_valid_upto": "alphax_iqama_expiry",
	"iqama_expiry_date": "alphax_iqama_expiry",
	"custom_work_permit_expiry_date": "alphax_work_permit_expiry",
	"custom_saudinonsaudi": "alphax_is_saudi",
}


_ID_LABEL = re.compile(r"iqama|national\s*id|border\s*(no|number)|identity\s*(no|number)", re.I)
_EXPIRY_LABEL = re.compile(r"expir|valid", re.I)


def _mirror_source(df):
	"""The AlphaX field a legacy Employee field duplicates, if any.

	Known fieldnames first; otherwise recognise custom fields by their label
	(e.g. 'National ID / Iqama / Border No'), so each site only asks once.
	"""
	if df.fieldname in MIRRORS:
		return MIRRORS[df.fieldname]
	if df.fieldname.startswith("alphax_") or df.fieldname in ("passport_number", "valid_upto"):
		return None
	label = df.label or ""
	if df.fieldtype in ("Data", "Int", "Long Int", "Small Text", "Phone") and _ID_LABEL.search(label) and not _EXPIRY_LABEL.search(label):
		return "alphax_iqama_number"
	if df.fieldtype == "Date" and _ID_LABEL.search(label) and _EXPIRY_LABEL.search(label):
		return "alphax_iqama_expiry"
	if df.fieldtype == "Select" and _is_saudi_select(df):
		return "alphax_is_saudi"
	if df.fieldtype == "Data" and re.search(r"arabic", label, re.I) and re.search(r"name", label, re.I):
		return "alphax_employee_name_ar"
	return None


def _is_saudi_select(df):
	options = [o.lower() for o in (df.options or "").split("\n") if o]
	return any("non" in o and "saudi" in o for o in options) and any("saudi" in o and "non" not in o for o in options)


def _mirror_map(meta):
	return {df.fieldname: src for df in meta.fields if (src := _mirror_source(df)) and meta.has_field(src)}


def _mirror_value(df, source_value):
	if df.fieldtype == "Select" and _is_saudi_select(df):
		options = [o for o in (df.options or "").split("\n") if o]
		want_non = not cint(source_value)
		return next((o for o in options if ("non" in o.lower()) == want_non), None)
	return source_value


def _sync_legacy_saudi_flag(doc, payload):
	"""Fill empty legacy fields from their AlphaX equivalents (and vice versa).

	Uses the value being saved, or the one already on the employee, so a hidden
	duplicate (e.g. a second 'National ID / Iqama' field) never blocks a save.
	"""
	for legacy, source in _mirror_map(doc.meta).items():
		df = doc.meta.get_field(legacy)
		if legacy not in payload and doc.get(legacy) in (None, ""):
			current = payload.get(source) if source in payload else doc.get(source)
			if source == "alphax_is_saudi" and source not in payload and doc.get(source) is None:
				continue
			value = _mirror_value(df, current)
			if value not in (None, "") and (source == "alphax_is_saudi" or current not in (None, "")):
				doc.set(legacy, value)
		elif legacy in payload and source != "alphax_is_saudi" and doc.get(source) in (None, ""):
			doc.set(source, payload.get(legacy))


def _mirrored(meta, payload, fieldname):
	"""True when a legacy field will be filled from an AlphaX field in the payload."""
	source = _mirror_map(meta).get(fieldname)
	return bool(source and (source in payload) and
				(payload.get(source) not in (None, "") or source == "alphax_is_saudi"))


def _fields(meta, names):
	return [n for n in names if meta.has_field(n)]


def _list_filters(meta, search=None, status="Active", department=None, company=None, saudi=None):
	filters = {}
	if status in ("Active", "Inactive", "Suspended", "Left"):
		filters["status"] = status
	if department:
		filters["department"] = department
	if company:
		filters["company"] = company
	if saudi in ("0", "1", 0, 1) and meta.has_field("alphax_is_saudi"):
		filters["alphax_is_saudi"] = cint(saudi)
	or_filters = None
	if search:
		term = "%" + str(search)[:80] + "%"
		or_filters = [["employee_name", "like", term], ["name", "like", term]]
		if meta.has_field("alphax_iqama_number"):
			or_filters.append(["alphax_iqama_number", "like", term])
	return filters, or_filters


def _required_to_check(meta):
	"""Mandatory fields to count per employee; legacy duplicates count via their AlphaX field."""
	mirrors = _mirror_map(meta)
	return [df for df in _site_required_fields(meta) if df.fieldname not in mirrors]


@frappe.whitelist()
def employees(search=None, status="Active", department=None, company=None, saudi=None, start=0, page_length=25):
	require_hr()
	meta = frappe.get_meta("Employee")
	start, page_length = clamp_page(start, page_length)
	filters, or_filters = _list_filters(meta, search, status, department, company, saudi)
	required = _required_to_check(meta)
	fields = list(dict.fromkeys(_fields(meta, LIST_FIELDS) + ["name"] + [df.fieldname for df in required]))
	rows = frappe.get_list("Employee", filters=filters, or_filters=or_filters, fields=fields,
						   order_by="employee_name asc", start=start, page_length=page_length)
	for r in rows:
		r["missing"] = [_(df.label) for df in required if r.get(df.fieldname) in (None, "")]
		for df in required:
			if df.fieldname not in LIST_FIELDS:
				r.pop(df.fieldname, None)
	total = frappe.get_list("Employee", filters=filters, or_filters=or_filters, fields=["count(name) as n"])[0].n
	departments = [d.department for d in frappe.get_list("Employee", filters={"department": ["is", "set"]},
				   fields=["department"], group_by="department", order_by="department asc", page_length=500)]
	return {"rows": rows, "total": total, "start": start, "page_length": page_length, "departments": departments}


@frappe.whitelist()
def export_employees(search=None, status="Active", department=None, company=None, saudi=None, file_format="xlsx"):
	"""Download the filtered directory (permission-aware) as Excel or CSV."""
	require_hr()
	meta = frappe.get_meta("Employee")
	filters, or_filters = _list_filters(meta, search, status, department, company, saudi)
	mirrors = _mirror_map(meta)
	names = ["name", "employee_name"] + [f for sec in SECTIONS.values() for f in sec]
	names += [df.fieldname for df in _site_required_fields(meta) if df.fieldname not in mirrors]
	fields = [f for f in dict.fromkeys(names) if f == "name" or meta.has_field(f)]
	rows = frappe.get_list("Employee", filters=filters, or_filters=or_filters, fields=fields,
						   order_by="employee_name asc", page_length=EXPORT_LIMIT)
	header = [_("Employee ID") if f == "name" else _(meta.get_label(f)) for f in fields]
	data = [header] + [[_cell(r.get(f)) for f in fields] for r in rows]
	stamp = nowdate()
	if file_format == "csv":
		from frappe.utils.csvutils import to_csv

		frappe.response["filecontent"] = to_csv(data).encode("utf-8-sig")  # BOM so Excel shows Arabic correctly
		frappe.response["filename"] = f"employees-{stamp}.csv"
	else:
		from frappe.utils.xlsxutils import make_xlsx

		frappe.response["filecontent"] = make_xlsx(data, "Employees").getvalue()
		frappe.response["filename"] = f"employees-{stamp}.xlsx"
	frappe.response["type"] = "binary"


def _cell(value):
	if value is None:
		return ""
	if hasattr(value, "isoformat"):
		return value.isoformat()
	return value


@frappe.whitelist()
def org_chart(company=None, department=None):
	"""Active employees with their manager, for the organisation chart."""
	require_hr()
	filters = {"status": "Active"}
	if company:
		filters["company"] = company
	if department:
		filters["department"] = department
	rows = frappe.get_list("Employee", filters=filters, page_length=EXPORT_LIMIT, order_by="employee_name asc",
						   fields=["name", "employee_name", "designation", "department", "reports_to", "image"])
	return {"rows": rows}


@frappe.whitelist()
def employee(name):
	require_hr()
	doc = frappe.get_doc("Employee", name)
	doc.check_permission("read")
	doc.apply_fieldlevel_read_permissions()
	meta = doc.meta
	sections = {}
	for key, names in SECTIONS.items():
		sections[key] = {f: doc.get(f) for f in _fields(meta, names)}
	curated = {f for names in SECTIONS.values() for f in names}
	mirrors = _mirror_map(meta)
	extra = [df for df in _site_required_fields(meta) if df.fieldname not in curated and df.fieldname not in mirrors]
	if extra:
		sections["company_required"] = {df.fieldname: doc.get(df.fieldname) for df in extra}
	labels = {f: _(meta.get_label(f)) for names in SECTIONS.values() for f in _fields(meta, names)}
	labels.update({df.fieldname: _(df.label) for df in extra})
	fields = {df.fieldname: _field_spec(df) for df in meta.fields if df.fieldname in curated or df in extra}
	missing_fields = []
	for df in _site_required_fields(meta):
		if doc.get(df.fieldname) in (None, ""):
			target = mirrors.get(df.fieldname, df.fieldname)  # a legacy duplicate is fixed via its AlphaX field
			if target not in missing_fields:
				missing_fields.append(target)
	missing_required = [labels.get(f) or _(meta.get_label(f)) for f in missing_fields]
	today = getdate(nowdate())
	docs = {
		"iqama": documents.bucket(getdate(doc.get("alphax_iqama_expiry")) if doc.get("alphax_iqama_expiry") else None, today),
		"passport": documents.bucket(getdate(doc.valid_upto) if doc.get("valid_upto") else None, today),
		"work_permit": documents.bucket(getdate(doc.get("alphax_work_permit_expiry")) if doc.get("alphax_work_permit_expiry") else None, today),
		"contract": documents.bucket(getdate(doc.contract_end_date) if doc.get("contract_end_date") else None, today),
	}
	return {
		"name": doc.name, "employee_name": doc.employee_name, "image": doc.image, "modified": str(doc.modified),
		"sections": sections, "labels": labels, "fields": fields, "documents": docs,
		"missing_required": missing_required, "missing_fields": missing_fields,
		"can_write": bool(frappe.has_permission("Employee", "write", doc)),
		"issues": (["mandatory_fields_missing"] if missing_fields else []) + _issues(doc),
	}


def _issues(doc):
	"""Data problems that silently break leave, attendance or compliance."""
	issues = []
	year = getdate(nowdate()).year
	if not doc.holiday_list:
		issues.append("no_holiday_list")
	else:
		to_date = frappe.db.get_value("Holiday List", doc.holiday_list, "to_date")
		if to_date and getdate(to_date).year < year:
			issues.append("holiday_list_outdated")
	if not doc.leave_approver:
		issues.append("no_leave_approver")
	if not doc.user_id:
		issues.append("no_user_account")
	if doc.get("alphax_is_saudi") and not doc.get("alphax_gosi_registration_date"):
		issues.append("gosi_registration_date_missing")
	if not doc.get("alphax_is_saudi") and not doc.get("alphax_iqama_number"):
		issues.append("iqama_missing")
	if not doc.get("alphax_is_saudi") and not doc.get("alphax_iqama_expiry"):
		issues.append("iqama_expiry_missing")
	if not doc.get("alphax_is_saudi") and doc.meta.has_field("passport_number") and not doc.get("passport_number"):
		issues.append("passport_missing")
	return issues


@frappe.whitelist()
def update_employee(name, data, modified):
	require_hr()
	payload = parse_json(data, {})
	doc = frappe.get_doc("Employee", name)
	doc.check_permission("write")
	if not modified or get_datetime(modified) != get_datetime(doc.modified):
		frappe.throw(_("Someone else changed this employee. Reload and try again."), frappe.TimestampMismatchError)
	allowed = _editable(doc.meta)
	changes = {k: v for k, v in payload.items() if k in allowed and doc.meta.has_field(k)}
	if not changes:
		frappe.throw(_("Nothing to update."))
	doc.update(changes)
	_sync_legacy_saudi_flag(doc, changes)
	doc.save()
	return employee(doc.name)


STEP_RULES = [  # first match wins; checked against fieldname + label
	("personal", r"\bclass\b|marital|blood|e-?mail|mobile|cell|phone|address|emergency|relation|salutation|insurance"),
	("bank", r"bank|iban|account\s*(no|number)|salary\s*mode|payment\s*mode"),
	("contract", r"joining|contract|notice|probation|confirmation"),
	("employee", r"name|gender|birth|religion|iqama|national|border|passport|saudi|identity|gosi|visa|expir|valid"),
	("organization", r"company|department|designation|branch|employment|reports|grade|division|cost.?center|shift|"
					 r"holiday|approver|location|project|payroll"),
]


def _step_for(df):
	text = f"{df.fieldname} {df.label or ''}"
	for step, pattern in STEP_RULES:
		if re.search(pattern, text, re.I):
			return step
	return "personal"  # anything else: with the personal details


@frappe.whitelist()
def new_employee_form():
	"""Fields the 'New employee' screen must show on this site."""
	require_hr()
	meta = frappe.get_meta("Employee")
	core = []
	for f in NEW_EMPLOYEE_CORE:
		df = meta.get_field(f)
		if df:
			core.append({**_field_spec(df), "step": _step_for(df)})
	core_names = {f["fieldname"] for f in core}
	mirrors = _mirror_map(meta)
	required = []
	for df in _site_required_fields(meta):
		if df.fieldname in core_names:
			continue
		spec = {**_field_spec(df), "step": _step_for(df)}
		if mirrors.get(df.fieldname) in core_names:
			spec["mirrors"] = mirrors[df.fieldname]  # filled from the AlphaX field; not shown twice
		required.append(spec)
	return {"core": core, "required": required}


def _draft_employee(payload):
	"""An unsaved Employee built the way create_employee will build it (defaults, mirrors, company holiday list)."""
	meta = frappe.get_meta("Employee")
	allowed = _editable(meta) | set(NEW_EMPLOYEE_CORE)
	doc = frappe.new_doc("Employee")
	doc.update({k: v for k, v in payload.items() if k in allowed and meta.has_field(k) and v not in (None, "")})
	_sync_legacy_saudi_flag(doc, payload)
	doc.status = "Active"
	if not doc.get("holiday_list") and doc.get("company"):
		doc.holiday_list = frappe.get_cached_value("Company", doc.company, "default_holiday_list")
	# Same automatic values the save will set, so the mandatory check sees them.
	from alphax_hr import employee_rules
	from alphax_hr.saudi import identity

	kind, _err = identity.classify_id(doc.get("alphax_iqama_number"))
	if kind and meta.has_field("alphax_is_saudi"):
		doc.alphax_is_saudi = 1 if kind == identity.SAUDI else 0
	employee_rules._auto_dates(doc)
	employee_rules._saudi_defaults(doc)
	return doc


def _missing_specs(doc):
	"""Mandatory fields Frappe itself would reject, with form specs (includes attachments and hidden-in-form fields)."""
	out = []
	for fieldname, _msg in doc._get_missing_mandatory_fields():
		df = doc.meta.get_field(fieldname)
		if df and df.fieldtype not in ("Table", "Table MultiSelect"):
			out.append({**_field_spec(df), "step": _step_for(df), "mandatory": True})
	return out


@frappe.whitelist()
def check_new_employee(data):
	"""Dry run before Create: which mandatory fields are still empty (nothing is saved)."""
	require_hr()
	doc = _draft_employee(parse_json(data, {}))
	return {"missing": _missing_specs(doc)}


@frappe.whitelist()
def create_employee(data):
	require_hr()
	payload = parse_json(data, {})
	doc = _draft_employee(payload)
	missing = _missing_specs(doc)
	if missing:
		frappe.throw(_("Please fill in: {0}").format(", ".join(m["label"] for m in missing)), title=_("Missing information"))
	doc.insert()
	_claim_attachments(doc, payload)
	package = payload.get("salary")
	if isinstance(package, dict) and package.get("mode"):
		from alphax_hr.api.salary import assign

		assign(doc.name, package, doc.date_of_joining)  # same transaction: a salary error undoes the whole create
	return employee(doc.name)


@frappe.whitelist()
def field_map():
	"""Diagnostics: which site fields AlphaX fills from its own (duplicates) and which mandatory fields it will ask for."""
	require_hr()
	meta = frappe.get_meta("Employee")
	mirrors = _mirror_map(meta)
	return {
		"mirrors": [{"fieldname": f, "label": _(meta.get_label(f)), "fieldtype": meta.get_field(f).fieldtype,
					 "from": src, "from_label": _(meta.get_label(src))} for f, src in mirrors.items()],
		"required": [{"fieldname": df.fieldname, "label": _(df.label), "fieldtype": df.fieldtype, "hidden": cint(df.hidden),
					  "read_only": cint(df.read_only), "step": _step_for(df), "mirrored": df.fieldname in mirrors}
					 for df in _site_required_fields(meta)],
		"unhandled_id_like": [{"fieldname": df.fieldname, "label": _(df.label), "fieldtype": df.fieldtype}
							  for df in meta.fields if df.reqd and _ID_LABEL.search(df.label or "")
							  and df.fieldname not in mirrors and not df.fieldname.startswith("alphax_")],
	}


def _claim_attachments(doc, payload):
	"""Files uploaded in the form before the employee existed are attached to it now."""
	for df in doc.meta.fields:
		url = payload.get(df.fieldname) if df.fieldtype in ATTACH_TYPES else None
		if not url:
			continue
		for name in frappe.get_all("File", filters={"file_url": url, "owner": frappe.session.user,
													 "attached_to_name": ["is", "not set"]}, pluck="name"):
			frappe.db.set_value("File", name, {"attached_to_doctype": "Employee", "attached_to_name": doc.name,
											  "attached_to_field": df.fieldname})


@frappe.whitelist()
def lookup(doctype, txt="", filters=None):
	"""Typeahead for Link fields, limited to HR-relevant doctypes and permissions."""
	require_hr()
	employee_links = {df.options for df in frappe.get_meta("Employee").fields if df.fieldtype == "Link" and df.options}
	if doctype not in LOOKUP_DOCTYPES | employee_links:
		frappe.throw(_("Lookup not allowed."), frappe.PermissionError)
	from frappe.desk.search import search_link

	return search_link(doctype, txt=str(txt or "")[:80], filters=parse_json(filters), page_length=20)


@frappe.whitelist()
def org_summary():
	require_hr()
	rows = frappe.get_list("Employee", filters={"status": "Active"}, fields=["department", "count(name) as n"],
						   group_by="department", order_by="n desc", page_length=100)
	total = sum(r.n for r in rows)
	joiners = frappe.get_list("Employee", filters={"date_of_joining": [">=", frappe.utils.add_days(nowdate(), -30)]},
							  fields=["count(name) as n"])[0].n
	leavers = frappe.get_list("Employee", filters={"relieving_date": [">=", frappe.utils.add_days(nowdate(), -30)]},
							  fields=["count(name) as n"])[0].n
	return {"active": total, "by_department": rows, "joiners_30d": joiners, "leavers_30d": leavers}


@frappe.whitelist()
def set_photo(name, file_url):
	"""Use an uploaded File (attached to this employee) as the profile picture."""
	require_hr()
	doc = frappe.get_doc("Employee", name)
	doc.check_permission("write")
	if not frappe.db.exists("File", {"file_url": file_url, "attached_to_doctype": "Employee", "attached_to_name": name}):
		frappe.throw(_("Upload the picture to this employee first."))
	if not re.search(r"\.(png|jpe?g|webp|gif)$", file_url or "", re.I):
		frappe.throw(_("Use a PNG, JPG or WebP image."))
	doc.db_set("image", file_url)
	return employee(name)


@frappe.whitelist()
def export_org_chart(department=None, company=None, file_format="xlsx"):
	"""Reporting lines as a table: level, manager, team size; people without a manager are flagged."""
	require_hr()
	rows = org_chart(company, department)["rows"]
	by_id = {r.name: r for r in rows}
	children = {}
	for r in rows:
		children.setdefault(r.reports_to, []).append(r.name)

	def team(n, seen):
		if n in seen:
			return 0
		seen.add(n)
		return sum(1 + team(c, seen) for c in children.get(n, []))

	def level(r):
		lvl, cur, seen = 1, r, set()
		while cur.reports_to and cur.reports_to in by_id and cur.name not in seen:
			seen.add(cur.name); cur = by_id[cur.reports_to]; lvl += 1
		return lvl

	table = [[_("Employee ID"), _("Employee"), _("Designation"), _("Department"), _("Reports to (ID)"), _("Reports to"),
			  _("Level"), _("Team size"), _("Note")]]
	for r in sorted(rows, key=lambda r: (level(r), r.employee_name)):
		mgr = by_id.get(r.reports_to)
		note = "" if r.reports_to else _("No reporting manager")
		if r.reports_to and not mgr:
			note = _("Manager not in this list (inactive or other department)")
		table.append([r.name, r.employee_name, r.designation or "", r.department or "", r.reports_to or "",
					  mgr.employee_name if mgr else "", level(r), team(r.name, set()), note])
	if file_format == "csv":
		from frappe.utils.csvutils import to_csv

		frappe.response["filecontent"] = to_csv(table).encode("utf-8-sig")
		frappe.response["filename"] = f"org-chart-{nowdate()}.csv"
	else:
		from frappe.utils.xlsxutils import make_xlsx

		frappe.response["filecontent"] = make_xlsx(table, "Org chart").getvalue()
		frappe.response["filename"] = f"org-chart-{nowdate()}.xlsx"
	frappe.response["type"] = "binary"
