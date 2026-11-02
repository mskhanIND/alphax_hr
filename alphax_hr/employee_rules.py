"""Employee master rules (requirements A1-A9), run on every Employee save."""
from __future__ import annotations

import re

import frappe
from frappe import _
from frappe.utils import add_days, add_months, cint, date_diff, getdate, nowdate

from alphax_hr.saudi import identity

ID_FIELD = "alphax_iqama_number"

MESSAGES = {
    "id_not_digits": _("National ID / Iqama number must contain digits only."),
    "id_wrong_length": _("National ID / Iqama number must be 10 digits."),
    "id_bad_prefix": _("National ID / Iqama number must start with 1 (Saudi), 2 (Iqama) or 3/4 (border number)."),
    "iban_bad_characters": _("IBAN may contain only letters and digits."),
    "iban_wrong_length": _("IBAN has the wrong length (Saudi IBANs are 24 characters)."),
    "iban_bad_checksum": _("IBAN check digits are wrong. Please re-check the number."),
}


def _settings():
	if not frappe.db.exists("DocType", "AlphaX HR Settings"):
		return frappe._dict()
	return frappe.get_cached_doc("AlphaX HR Settings")


def validate(doc, method=None):
	conf = _settings()
	_validate_identity(doc)
	_validate_iban(doc, conf)
	_validate_age(doc, conf)
	_set_probation(doc, conf)
	_validate_annual_days(doc)
	_auto_dates(doc)
	_saudi_defaults(doc)
	_passport_rule(doc, conf)


def _changed(doc, *fields):
	previous = doc.get_doc_before_save()
	return previous is None or any(previous.get(f) != doc.get(f) for f in fields)


def _fields_by_label(doc, pattern, fieldtypes):
	rx = re.compile(pattern, re.I)
	return [df for df in doc.meta.fields if df.fieldtype in fieldtypes and rx.search(df.label or "")
			and not df.fieldname.startswith("alphax_")]


def _auto_dates(doc):
	"""Contract dates from the joining date and the contract period (1-5 years)."""
	if not doc.date_of_joining:
		return
	years = doc.get("alphax_contract_years")
	if years and doc.meta.has_field("contract_end_date") and _changed(doc, "alphax_contract_years", "date_of_joining"):
		if str(years).isdigit():
			doc.contract_end_date = add_days(add_months(doc.date_of_joining, 12 * cint(years)), -1)
		elif years == "Indefinite":
			doc.contract_end_date = None
	for df in _fields_by_label(doc, r"contract\s*start", ("Date",)):  # site fields like "Contract Start Date"
		if not doc.get(df.fieldname):
			doc.set(df.fieldname, doc.date_of_joining)


def _saudi_defaults(doc):
	"""For Saudi nationals (ID starting with 1): nationality and first GOSI registration default from the record."""
	if not cint(doc.get("alphax_is_saudi")):
		return
	if doc.meta.has_field("alphax_gosi_registration_date") and not doc.get("alphax_gosi_registration_date") and doc.date_of_joining:
		doc.alphax_gosi_registration_date = doc.date_of_joining
	for df in _fields_by_label(doc, r"nationality", ("Link", "Select", "Data")):
		if doc.get(df.fieldname):
			continue
		if df.fieldtype == "Link" and df.options == "Country" and frappe.db.exists("Country", "Saudi Arabia"):
			doc.set(df.fieldname, "Saudi Arabia")
		elif df.fieldtype == "Link" and df.options and frappe.db.exists(df.options, "Saudi"):
			doc.set(df.fieldname, "Saudi")
		elif df.fieldtype == "Select":
			opt = next((o for o in (df.options or "").split("\n") if "saudi" in o.lower() and "non" not in o.lower()), None)
			if opt:
				doc.set(df.fieldname, opt)
		elif df.fieldtype == "Data":
			doc.set(df.fieldname, "Saudi")


def _passport_rule(doc, conf):
	if not cint(conf.get("passport_non_saudi_only")) or not doc.meta.has_field("passport_number"):
		return
	# Enforced for new employees and ID changes; older records show it under Data issues instead of blocking edits.
	if not (doc.is_new() or _changed(doc, "alphax_iqama_number")):
		return
	if not cint(doc.get("alphax_is_saudi")) and not (doc.get("passport_number") or "").strip() and doc.get("alphax_iqama_number"):
		frappe.throw(_("Passport number is required for non-Saudi employees."), title=_("Missing information"))


def _validate_annual_days(doc):
	days = doc.get("alphax_annual_leave_days")
	if days in (None, "", 0):
		return
	if cint(days) < 21 or cint(days) > 366:
		frappe.throw(_("Annual leave days in the contract must be at least 21 (Saudi Labor Law, Art. 109)."),
					 title=_("Annual leave"))


def _validate_identity(doc):
	if not doc.meta.has_field(ID_FIELD):
		return
	number = identity.normalise(doc.get(ID_FIELD))
	if not number:
		return
	kind, error = identity.classify_id(number)
	if error:
		frappe.throw(MESSAGES[error], title=_("Invalid ID number"))
	doc.set(ID_FIELD, number)
	# The number decides nationality: 1 = Saudi national ID, 2/3/4 = non-Saudi.
	doc.alphax_is_saudi = 1 if kind == identity.SAUDI else 0
	duplicate = frappe.db.get_value("Employee", {ID_FIELD: number, "name": ["!=", doc.name or ""]}, "name")
	if duplicate:
		frappe.throw(_("ID number {0} already belongs to employee {1}.").format(number, duplicate), title=_("Duplicate ID number"))


def _validate_iban(doc, conf):
	if not cint(conf.get("validate_iban", 1)) or not doc.meta.has_field("iban") or not doc.get("iban"):
		return
	error = identity.iban_error(doc.iban)
	if error:
		frappe.throw(MESSAGES[error], title=_("Invalid IBAN"))
	doc.iban = identity.normalise_iban(doc.iban)


def _validate_age(doc, conf):
	if not doc.date_of_birth:
		return
	dob = getdate(doc.date_of_birth)
	if dob > getdate(nowdate()):
		frappe.throw(_("Date of birth cannot be in the future."))
	min_age = cint(conf.get("min_employee_age") or 0)
	if min_age and doc.date_of_joining:
		age_at_joining = date_diff(doc.date_of_joining, dob) / 365.25
		if age_at_joining < min_age:
			frappe.throw(_("Employee must be at least {0} years old at joining.").format(min_age))


def _set_probation(doc, conf):
	if not doc.meta.has_field("alphax_probation_end_date") or not doc.date_of_joining:
		return
	days = cint(conf.get("probation_days") or 0)
	if not days:
		return
	if days > 180:
		frappe.throw(_("Probation cannot exceed 180 days under the Saudi Labor Law."))
	previous = doc.get_doc_before_save()
	joining_changed = bool(previous and previous.date_of_joining != doc.date_of_joining)
	if not doc.alphax_probation_end_date or joining_changed:
		doc.alphax_probation_end_date = add_days(doc.date_of_joining, days - 1)
