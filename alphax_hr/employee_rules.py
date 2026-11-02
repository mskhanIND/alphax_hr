"""Employee master rules (requirements A1-A9), run on every Employee save."""
from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import add_days, cint, date_diff, getdate, nowdate

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
