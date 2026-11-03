"""Saudi bank list for employee bank details (ERPNext Bank records with abbreviation and IBAN code)."""
from __future__ import annotations

import frappe

from alphax_hr.api._common import login_required
from alphax_hr.saudi.banks import BANKS, by_iban


def seed():
	if not frappe.db.exists("DocType", "Bank"):
		return 0
	meta = frappe.get_meta("Bank")
	made = 0
	for name, abbr, code, swift, ar in BANKS:
		values = {k: v for k, v in (("alphax_abbr", abbr), ("alphax_iban_code", code), ("alphax_name_ar", ar)) if meta.has_field(k)}
		if frappe.db.exists("Bank", name):
			for k, v in values.items():
				if not frappe.db.get_value("Bank", name, k):
					frappe.db.set_value("Bank", name, k, v, update_modified=False)
			continue
		doc = frappe.get_doc({"doctype": "Bank", "bank_name": name, **values})
		if meta.has_field("swift_number") and swift:
			doc.swift_number = swift
		doc.insert(ignore_permissions=True)
		made += 1
	return made


@frappe.whitelist()
def banks():
	login_required()
	meta = frappe.get_meta("Bank")
	fields = ["name"] + [f for f in ("alphax_abbr", "alphax_iban_code", "alphax_name_ar", "swift_number") if meta.has_field(f)]
	rows = frappe.get_all("Bank", fields=fields, order_by="name asc", limit=500)
	return [{"name": r.name, "abbr": r.get("alphax_abbr"), "code": r.get("alphax_iban_code"), "name_ar": r.get("alphax_name_ar"),
			 "swift": r.get("swift_number")} for r in rows]


def name_for_iban(iban):
	"""Bank name for a Saudi IBAN (site's Bank list first, then the built-in list)."""
	code = (iban or "").replace(" ", "").upper()[4:6]
	if len(code) == 2 and frappe.get_meta("Bank").has_field("alphax_iban_code"):
		hit = frappe.db.get_value("Bank", {"alphax_iban_code": code}, "name")
		if hit:
			return hit
	row = by_iban(iban)
	return row[0] if row else None
