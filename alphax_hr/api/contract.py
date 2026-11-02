"""Bilingual (English / Arabic) employment contract in the layout of the Qiwa unified contract."""
from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import add_days, cint, flt, formatdate, getdate, nowdate

from alphax_hr.api._common import require_hr, settings


def _label_value(doc, pattern):
	import re

	for df in doc.meta.fields:
		if df.fieldtype in ("Data", "Link", "Select") and re.search(pattern, df.label or "", re.I) and doc.get(df.fieldname):
			return doc.get(df.fieldname)
	return None


def contract_data(employee):
	emp = frappe.get_doc("Employee", employee)
	emp.check_permission("read")
	company = frappe.get_doc("Company", emp.company)
	from alphax_hr.api.salary import current
	from alphax_hr.saudi import leave as annual

	sal = (current(employee) or {}).get("current")
	years = emp.get("alphax_contract_years")
	conf = settings()
	join = getdate(emp.date_of_joining) if emp.date_of_joining else None
	annual_days = cint(emp.get("alphax_annual_leave_days")) or (
		cint(conf.annual_fixed_days) if conf.annual_policy == annual.POLICY_FIXED and conf.annual_fixed_days else annual.ANNUAL_BASE_DAYS)
	address = frappe.db.sql("""select a.address_line1, a.city, a.country from `tabAddress` a join `tabDynamic Link` l on l.parent=a.name
		where l.link_doctype='Company' and l.link_name=%s order by a.is_primary_address desc limit 1""", emp.company, as_dict=True)
	probation_end = emp.get("alphax_probation_end_date")
	probation_days = (getdate(probation_end) - join).days + 1 if probation_end and join else cint(conf.probation_days) or 90
	return {
		"today": formatdate(nowdate()),
		"company": {"name": company.company_name, "name_ar": _label_value(company, r"arabic") or company.company_name,
					"tax_id": company.tax_id, "cr": _label_value(company, r"commercial|\bcr\b|registration"),
					"address": ", ".join(x for x in (address[0].address_line1, address[0].city, address[0].country) if x) if address else ""},
		"employee": {"name": emp.employee_name, "name_ar": emp.get("alphax_employee_name_ar") or "", "id": emp.get("alphax_iqama_number") or "",
					 "nationality": _label_value(emp, r"nationality") or (_("Saudi") if cint(emp.get("alphax_is_saudi")) else ""),
					 "gender": emp.gender, "dob": formatdate(emp.date_of_birth) if emp.date_of_birth else "", "mobile": emp.cell_number or "",
					 "email": emp.personal_email or emp.company_email or "", "iban": emp.get("iban") or "", "bank": emp.get("bank_name") or ""},
		"job": {"designation": emp.designation or "", "department": emp.department or "", "location": emp.branch or "",
				"start": formatdate(join) if join else "",
				"type": _("Indefinite") if years == "Indefinite" else _("Fixed term"),
				"type_ar": "غير محدد المدة" if years == "Indefinite" else "محدد المدة",
				"years": years if years and str(years).isdigit() else "",
				"end": formatdate(emp.contract_end_date) if emp.get("contract_end_date") else "",
				"probation_days": probation_days, "notice_days": cint(emp.notice_number_of_days) or 60,
				"daily_hours": 8, "weekly_hours": 48, "annual_days": annual_days},
		"salary": {"rows": [{"component": r.salary_component, "amount": flt(r.amount)} for r in (sal or {}).get("earnings", [])],
				   "gross": flt((sal or {}).get("gross")), "currency": company.default_currency or "SAR"} if sal else None,
	}


@frappe.whitelist()
def preview(employee):
	"""Contract as HTML. (Not named "html": some servers treat a method ending in .html/.pdf as a file.)"""
	return html(employee)


def html(employee):
	require_hr()
	data = contract_data(employee)
	return {"html": frappe.render_template("alphax_hr/templates/alphax/contract.html", data), "employee_name": data["employee"]["name"]}


def _pdf_bytes(employee):
	from frappe.utils.pdf import get_pdf

	body = frappe.render_template("alphax_hr/templates/alphax/contract.html", contract_data(employee))
	return get_pdf(body, {"page-size": "A4", "margin-top": "12mm", "margin-bottom": "12mm", "margin-left": "10mm",
						  "margin-right": "10mm", "encoding": "UTF-8"})


@frappe.whitelist(methods=["GET"])
def download(employee):
	"""Contract PDF download (see preview for why this is not called "pdf")."""
	return pdf(employee)


def pdf(employee):
	"""Download the contract as PDF (read-only)."""
	require_hr()
	frappe.response["filename"] = f"Employment-Contract-{employee}.pdf"
	frappe.response["filecontent"] = _pdf_bytes(employee)
	frappe.response["type"] = "pdf"


@frappe.whitelist(methods=["POST"])
def save(employee):
	"""Attach the contract PDF to the employee (private file)."""
	require_hr()
	frappe.get_doc("Employee", employee).check_permission("write")
	f = frappe.get_doc({"doctype": "File", "file_name": f"Employment-Contract-{employee}.pdf", "content": _pdf_bytes(employee),
						"is_private": 1, "attached_to_doctype": "Employee", "attached_to_name": employee}).insert()
	return {"file_url": f.file_url}
