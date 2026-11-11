"""New joiners fill in their own details before HR creates the employee.

HR invites a joiner (name, contact, company, department, designation, joining date) and shares a private link. The joiner
opens /joiner?key=… without an account, fills the form in Arabic or English and uploads documents. HR reviews it, asks for
changes (the link opens again with HR's note) or creates the employee from it: the New employee screen opens filled in,
and the documents move to the employee.
"""
from __future__ import annotations

import json
import re

import frappe
from frappe import _
from frappe.utils import add_days, cint, get_url, getdate, now_datetime, today

from alphax_hr.api._common import parse_json, require_hr, require_hr_manager

DT = "AlphaX Joiner"
LINK_DAYS = 14
MAX_FILE_MB = 8
FILE_TYPES = {"pdf", "jpg", "jpeg", "png", "heic", "webp"}
OPEN = ("Invited", "Changes requested")

# (key, English, Arabic, type, required, section, options)
FORM = [
	("first_name", "First name", "الاسم الأول", "text", 1, "personal", None),
	("middle_name", "Middle name", "اسم الأب", "text", 0, "personal", None),
	("last_name", "Family name", "اسم العائلة", "text", 1, "personal", None),
	("alphax_employee_name_ar", "Full name in Arabic", "الاسم الكامل بالعربية", "text", 0, "personal", None),
	("gender", "Gender", "الجنس", "select", 1, "personal", ["Male", "Female"]),
	("date_of_birth", "Date of birth", "تاريخ الميلاد", "date", 1, "personal", None),
	("nationality", "Nationality", "الجنسية", "text", 1, "personal", None),
	("marital_status", "Marital status", "الحالة الاجتماعية", "select", 0, "personal", ["Single", "Married", "Divorced", "Widowed"]),
	("alphax_iqama_number", "National ID / Iqama number", "رقم الهوية / الإقامة", "id", 1, "identity", None),
	("alphax_iqama_expiry", "ID / Iqama expiry", "تاريخ انتهاء الهوية / الإقامة", "date", 0, "identity", None),
	("alphax_border_number", "Border number (new arrivals)", "رقم الحدود (للقادمين الجدد)", "text", 0, "identity", None),
	("passport_number", "Passport number", "رقم الجواز", "text", 0, "identity", None),
	("valid_upto", "Passport expiry", "تاريخ انتهاء الجواز", "date", 0, "identity", None),
	("cell_number", "Mobile", "الجوال", "phone", 1, "contact", None),
	("personal_email", "Personal e-mail", "البريد الإلكتروني الشخصي", "email", 0, "contact", None),
	("current_address", "Address in Saudi Arabia", "العنوان في المملكة", "textarea", 0, "contact", None),
	("person_to_be_contacted", "Emergency contact name", "اسم شخص للطوارئ", "text", 1, "contact", None),
	("relation", "Relation", "صلة القرابة", "text", 0, "contact", None),
	("emergency_phone_number", "Emergency contact phone", "جوال شخص الطوارئ", "phone", 1, "contact", None),
	("bank_name", "Bank", "البنك", "text", 0, "bank", None),
	("iban", "IBAN", "رقم الآيبان", "iban", 0, "bank", None),
	("education", "Highest qualification", "أعلى مؤهل", "text", 0, "bank", None),
	("photo", "Personal photo", "صورة شخصية", "file", 0, "documents", None),
	("id_copy", "Copy of ID / Iqama", "صورة الهوية / الإقامة", "file", 1, "documents", None),
	("passport_copy", "Copy of passport", "صورة الجواز", "file", 0, "documents", None),
	("iban_letter", "IBAN letter from the bank", "خطاب الآيبان من البنك", "file", 0, "documents", None),
	("certificates", "Qualification certificate", "شهادة المؤهل", "file", 0, "documents", None),
]
SECTIONS = [("personal", "Personal details", "البيانات الشخصية"), ("identity", "Identity", "الهوية"),
			("contact", "Contact", "التواصل"), ("bank", "Bank & education", "البنك والتعليم"),
			("documents", "Documents", "المستندات")]
FILES = [k for k, *_r, in FORM if _r[2] == "file"]
EMPLOYEE_FILE = {"photo": "image"}


def _row(doc):
	data = json.loads(doc.data or "{}")
	return {"name": doc.name, "full_name": doc.full_name, "status": doc.status, "mobile": doc.mobile, "email": doc.email,
			"company": doc.company, "department": doc.department, "designation": doc.designation, "branch": doc.branch,
			"date_of_joining": str(doc.date_of_joining) if doc.date_of_joining else None,
			"expires_on": str(doc.expires_on) if doc.expires_on else None,
			"submitted_on": str(doc.submitted_on) if doc.submitted_on else None, "hr_note": doc.hr_note,
			"employee": doc.employee, "link": _link(doc), "data": data,
			"expired": bool(doc.expires_on and getdate(doc.expires_on) < getdate(today()) and doc.status in OPEN)}


def _link(doc):
	return get_url(f"/joiner?key={doc.token}") if doc.token else None


# ------------------------------------------------------------------ HR
@frappe.whitelist()
def overview(status: str | None = None):
	require_hr()
	rows = [_row(frappe.get_doc(DT, n)) for n in frappe.get_all(DT, filters={"status": status} if status else {},
																  pluck="name", order_by="modified desc", limit=500)]
	counts = {s: frappe.db.count(DT, {"status": s}) for s in ("Invited", "Submitted", "Changes requested", "Converted", "Cancelled")}
	return {"rows": rows, "counts": counts, "form": form_spec(), "can_edit": bool(set(frappe.get_roles()) & {"HR Manager", "System Manager"})}


@frappe.whitelist(methods=["POST"])
def invite(data: str | dict):
	require_hr()
	v = parse_json(data) or {}
	if not (v.get("full_name") or "").strip():
		frappe.throw(_("Enter the joiner's name."))
	if not (v.get("mobile") or v.get("email")):
		frappe.throw(_("Enter a mobile number or e-mail so the link can reach the joiner."))
	doc = frappe.get_doc({"doctype": DT, "status": "Invited", "token": frappe.generate_hash(length=32),
						  "expires_on": add_days(today(), cint(v.get("days")) or LINK_DAYS), "invited_by": frappe.session.user,
						  **{k: (v.get(k) or None) for k in ("full_name", "mobile", "email", "company", "department",
															  "designation", "branch", "date_of_joining")}})
	doc.insert(ignore_permissions=True)
	return _row(doc)


@frappe.whitelist(methods=["POST"])
def send_link(name: str):
	"""E-mail the link to the joiner (HR pressed Send)."""
	require_hr()
	doc = frappe.get_doc(DT, name)
	if not doc.email:
		frappe.throw(_("This joiner has no e-mail; share the link by WhatsApp or SMS instead."))
	from alphax_hr.api.branding import brand

	b = brand()
	frappe.sendmail(recipients=[doc.email], subject=_("Welcome to {0}: your joining form").format(b["title"]),
					message=_("Dear {0},<br><br>Welcome! Before your first day, please fill in your details and upload your "
							  "documents here:<br><a href=\"{1}\">{1}</a><br><br>The link is valid until {2}.").format(
						frappe.utils.escape_html(doc.full_name), _link(doc), frappe.utils.format_date(doc.expires_on)),
					now=True)
	return {"sent": doc.email}


@frappe.whitelist(methods=["POST"])
def renew(name: str, days: int | str = LINK_DAYS):
	"""A new link (the old one stops working) and more days."""
	require_hr()
	doc = frappe.get_doc(DT, name)
	if doc.status in ("Converted", "Cancelled"):
		frappe.throw(_("This form is closed."))
	doc.token = frappe.generate_hash(length=32)
	doc.expires_on = add_days(today(), cint(days) or LINK_DAYS)
	doc.save(ignore_permissions=True)
	return _row(doc)


@frappe.whitelist(methods=["POST"])
def request_changes(name: str, note: str):
	require_hr()
	if not (note or "").strip():
		frappe.throw(_("Tell the joiner what to correct."))
	doc = frappe.get_doc(DT, name)
	if doc.status != "Submitted":
		frappe.throw(_("Only a submitted form can be sent back."))
	doc.status, doc.hr_note = "Changes requested", note.strip()
	if not doc.expires_on or getdate(doc.expires_on) < getdate(add_days(today(), 3)):
		doc.expires_on = add_days(today(), 7)
	doc.save(ignore_permissions=True)
	return _row(doc)


@frappe.whitelist(methods=["POST"])
def cancel(name: str):
	require_hr()
	doc = frappe.get_doc(DT, name)
	if doc.status == "Converted":
		frappe.throw(_("The employee was already created from this form."))
	doc.status, doc.token = "Cancelled", None
	doc.save(ignore_permissions=True)
	return _row(doc)


@frappe.whitelist()
def prefill(name: str):
	"""Values for the New employee screen: what HR set on the invitation plus the joiner's answers (employee fields only)."""
	require_hr()
	doc = frappe.get_doc(DT, name)
	if doc.status == "Converted":
		frappe.throw(_("The employee was already created from this form: {0}").format(doc.employee))
	data = json.loads(doc.data or "{}")
	meta = frappe.get_meta("Employee")
	out = {k: doc.get(k) for k in ("company", "department", "designation", "branch") if doc.get(k)}
	if doc.date_of_joining:
		out["date_of_joining"] = str(doc.date_of_joining)
	for key, *_rest in FORM:
		target = EMPLOYEE_FILE.get(key, key)
		if data.get(key) not in (None, "") and meta.has_field(target):
			out[target] = data[key]
	if "gender" in out and not frappe.db.exists("Gender", out["gender"]):
		out.pop("gender")
	if data.get("nationality") and meta.has_field("nationality"):
		out["nationality"] = data["nationality"]
	extra = {k: data.get(k) for k, *_r in FORM if data.get(k) not in (None, "")
			 and not meta.has_field(EMPLOYEE_FILE.get(k, k)) and k not in FILES}
	files = {k: data.get(k) for k in FILES if data.get(k)}
	return {"values": out, "extra": extra, "files": files, "joiner": doc.name, "full_name": doc.full_name}


def on_employee_created(employee, joiner):
	"""create_employee() was given a joiner: close the form and move its documents to the employee."""
	if not joiner or not frappe.db.exists(DT, joiner):
		return
	doc = frappe.get_doc(DT, joiner)
	for f in frappe.get_all("File", filters={"attached_to_doctype": DT, "attached_to_name": joiner},
							fields=["name", "attached_to_field"]):
		frappe.db.set_value("File", f.name, {"attached_to_doctype": "Employee", "attached_to_name": employee,
											 "attached_to_field": EMPLOYEE_FILE.get(f.attached_to_field) or None})
	doc.status, doc.employee, doc.token = "Converted", employee, None
	doc.save(ignore_permissions=True)


# ------------------------------------------------------------------ joiner (no login, by link)
def form_spec():
	return {"sections": [{"key": k, "en": en, "ar": ar} for k, en, ar in SECTIONS],
			"fields": [{"key": k, "en": en, "ar": ar, "type": t, "required": r, "section": s, "options": o}
					   for k, en, ar, t, r, s, o in FORM]}


def _by_key(key):
	key = str(key or "").strip()
	if not re.fullmatch(r"[0-9a-f]{32}", key):
		frappe.throw(_("This link is not valid."), frappe.PermissionError)
	name = frappe.db.get_value(DT, {"token": key}, "name")
	if not name:
		frappe.throw(_("This link is not valid or was replaced by a newer one. Ask HR for a new link."), frappe.PermissionError)
	doc = frappe.get_doc(DT, name)
	return doc


def _open(doc):
	if doc.status not in OPEN:
		frappe.throw(_("This form was already sent. HR will contact you if anything is missing."), frappe.ValidationError)
	if doc.expires_on and getdate(doc.expires_on) < getdate(today()):
		frappe.throw(_("This link has expired. Ask HR for a new link."), frappe.ValidationError)


def _limited():
	"""At most 60 saves / uploads an hour from one address (the link works without an account)."""
	if not getattr(frappe.local, "request_ip", None):
		return lambda fn: fn
	from frappe.rate_limiter import rate_limit

	return rate_limit(limit=60, seconds=3600)


@frappe.whitelist(allow_guest=True, methods=["GET"])  # nosemgrep  # access by the 32-character link key only
def public_form(key: str):
	doc = _by_key(key)
	from alphax_hr.api.branding import brand

	b = brand()
	return {"name": doc.full_name, "status": doc.status, "hr_note": doc.hr_note if doc.status == "Changes requested" else None,
			"expires_on": str(doc.expires_on) if doc.expires_on else None, "company": doc.company,
			"designation": doc.designation, "date_of_joining": str(doc.date_of_joining) if doc.date_of_joining else None,
			"values": json.loads(doc.data or "{}") if doc.status in OPEN else {}, "open": doc.status in OPEN and not (
				doc.expires_on and getdate(doc.expires_on) < getdate(today())),
			"brand": {"title": b.get("title"), "logo": b.get("logo")}, **form_spec()}


def _validate(values):
	from alphax_hr.saudi import identity

	errors = {}
	for k, en, _ar, t, req, _s, opts in FORM:
		v = values.get(k)
		v = v.strip() if isinstance(v, str) else v
		values[k] = v
		if req and not v:
			errors[k] = "required"
			continue
		if not v:
			continue
		if t == "id":
			kind, err = identity.classify_id(v)
			if err:
				errors[k] = "id"
		elif t == "iban" and not re.fullmatch(r"SA\d{22}", re.sub(r"\s", "", v).upper()):
			errors[k] = "iban"
		elif t == "email" and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", v):
			errors[k] = "email"
		elif t == "phone" and not re.fullmatch(r"\+?[\d\s-]{8,16}", v):
			errors[k] = "phone"
		elif t == "date":
			try:
				getdate(v)
			except Exception:  # noqa: BLE001
				errors[k] = "date"
		elif t == "select" and opts and v not in opts:
			errors[k] = "option"
	if values.get("iban"):
		values["iban"] = re.sub(r"\s", "", values["iban"]).upper()
	return errors


@frappe.whitelist(allow_guest=True, methods=["POST"])  # nosemgrep  # access by the 32-character link key only
def public_save(key: str, values: str | dict, submit: int | str = 0):
	"""Save the answers (draft) or send them to HR. Files keep the URLs returned by public_upload."""
	_limited()(lambda: None)()
	doc = _by_key(key)
	_open(doc)
	given = parse_json(values) or {}
	known = {k for k, *_r in FORM}
	have = json.loads(doc.data or "{}")
	clean = {k: (str(v)[:500] if v is not None else None) for k, v in given.items() if k in known and k not in FILES}
	for k in FILES:  # only files this form uploaded
		if given.get(k) and frappe.db.exists("File", {"file_url": given[k], "attached_to_doctype": DT, "attached_to_name": doc.name}):
			clean[k] = given[k]
		elif have.get(k):
			clean[k] = have[k]
	merged = {**have, **clean}
	errors = _validate(merged) if cint(submit) else {}
	if errors:
		return {"ok": False, "errors": errors}
	doc.data = json.dumps(merged, ensure_ascii=False)
	if cint(submit):
		doc.status, doc.submitted_on = "Submitted", now_datetime()
		first = " ".join(x for x in (merged.get("first_name"), merged.get("last_name")) if x)
		if first and first.lower() != (doc.full_name or "").lower():
			doc.full_name = first[:140]
	doc.save(ignore_permissions=True)
	if cint(submit):
		from alphax_hr.api import alerts

		alerts.event("New joiner", _("Joining form received: {0}").format(doc.full_name),
					 _("{0} sent the joining form{1}. Review it and create the employee.").format(
						 doc.full_name, f" ({doc.designation})" if doc.designation else ""),
					 url="/alphax/joiners", doc=(DT, doc.name), tag=f"joiner-{doc.name}")
	return {"ok": True, "status": doc.status}


@frappe.whitelist(allow_guest=True, methods=["POST"])  # nosemgrep  # access by the 32-character link key only
def public_upload(key: str, field: str):
	"""One document for the form (PDF or image, private, attached to this joiner's form)."""
	_limited()(lambda: None)()
	doc = _by_key(key)
	_open(doc)
	if field not in FILES:
		frappe.throw(_("Unknown document."))
	upload = frappe.request.files.get("file") if frappe.request else None
	if not upload:
		frappe.throw(_("Choose a file."))
	name = re.sub(r"[^\w.\- ]", "_", upload.filename or "file")[:120]
	ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
	if ext not in FILE_TYPES:
		frappe.throw(_("Upload a PDF or a photo (JPG, PNG)."))
	content = upload.stream.read(MAX_FILE_MB * 1024 * 1024 + 1)
	if len(content) > MAX_FILE_MB * 1024 * 1024:
		frappe.throw(_("The file is larger than {0} MB.").format(MAX_FILE_MB))
	for old in frappe.get_all("File", filters={"attached_to_doctype": DT, "attached_to_name": doc.name, "attached_to_field": field},
							  pluck="name"):
		frappe.delete_doc("File", old, ignore_permissions=True)
	f = frappe.get_doc({"doctype": "File", "file_name": f"{field}-{name}", "content": content, "is_private": 1,
						"attached_to_doctype": DT, "attached_to_name": doc.name, "attached_to_field": field})
	f.flags.ignore_permissions = True
	f.insert()
	have = json.loads(doc.data or "{}")
	have[field] = f.file_url
	frappe.db.set_value(DT, doc.name, "data", json.dumps(have, ensure_ascii=False), update_modified=False)
	return {"field": field, "file_url": f.file_url, "file_name": name}
