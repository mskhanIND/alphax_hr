"""AlphaX payslip: bilingual, with company stamp and authorised signature chosen by HR.

Images are embedded (base64) so PDFs never fail on broken or private image links.
Also available to ERPNext as the "AlphaX Salary Slip" print format (Jinja method alphax_payslip).
"""
from __future__ import annotations

import base64
import mimetypes
import os

import frappe
from frappe import _
from frappe.utils import flt, formatdate, fmt_money, getdate

from alphax_hr.api._common import is_hr, login_required, settings

PRINT_FORMAT = "AlphaX Salary Slip"
PENALTY_WORDS = ("penalty", "penalties", "disciplin", "fine", "violation")


def _data_uri(url):
	"""Inline a /files or /private/files image; None when missing (never breaks the PDF)."""
	if not url:
		return None
	if url.startswith("data:"):
		return url
	from urllib.parse import unquote

	path = unquote(url.split("?")[0])
	if path.startswith("/private/files/"):
		full = frappe.get_site_path("private", "files", path[len("/private/files/"):])
	elif path.startswith("/files/"):
		full = frappe.get_site_path("public", "files", path[len("/files/"):])
	else:
		return None
	base = os.path.realpath(frappe.get_site_path("private" if path.startswith("/private/") else "public", "files"))
	full = os.path.realpath(full)
	if not full.startswith(base + os.sep) or not os.path.exists(full):
		return None
	mime = mimetypes.guess_type(full)[0] or "image/png"
	# Reviewed: path is fixed, or resolved and checked to stay inside the site's files folder.
	with open(full, "rb") as f:  # nosemgrep
		return f"data:{mime};base64,{base64.b64encode(f.read()).decode()}"


def _mask(acc):
	acc = (acc or "").replace(" ", "")
	return f"{acc[:4]} •••• {acc[-4:]}" if len(acc) > 8 else acc


def context(doc):
	conf = settings()
	company = frappe.get_cached_doc("Company", doc.company)
	emp = frappe.get_doc("Employee", doc.employee)
	logo = company.get("company_logo") or frappe.db.get_value("Letter Head", {"is_default": 1}, "image")
	cur = doc.currency or company.default_currency
	money = lambda v: fmt_money(flt(v), currency=cur)  # noqa: E731
	earnings = [{"name": r.salary_component, "amount": money(r.amount)} for r in doc.earnings if flt(r.amount)]
	deductions, penalties = [], []
	for r in doc.deductions:
		if not flt(r.amount):
			continue
		row = {"name": r.salary_component, "amount": money(r.amount)}
		(penalties if any(w in r.salary_component.lower() for w in PENALTY_WORDS) else deductions).append(row)
	loans = flt(doc.get("total_loan_repayment"))
	annual = None
	if conf.get("annual_leave_type"):
		try:
			from hrms.hr.doctype.leave_application.leave_application import get_leave_balance_on

			annual = flt(get_leave_balance_on(doc.employee, conf.annual_leave_type, getdate(doc.end_date)), 1)
		except Exception:  # noqa: BLE001 - balance is informative only
			annual = None
	warnings = []
	if frappe.db.exists("DocType", "AlphaX Penalty"):
		warnings = frappe.get_all("AlphaX Penalty", filters={"employee": doc.employee, "status": ["in", ["Issued", "Acknowledged", "Objected"]],
															 "violation_date": ["between", [doc.start_date, doc.end_date]]},
								  fields=["violation_type", "violation_date", "action"], order_by="violation_date asc")
	show = bool(conf.get("payslip_show_stamp"))
	return {
		"doc": doc, "company": company.company_name, "company_ar": company.get("company_name_in_arabic") or "",
		"tax_id": company.tax_id or "", "logo": _data_uri(logo),
		"period": f"{formatdate(doc.start_date)} – {formatdate(doc.end_date)}", "month": getdate(doc.start_date).strftime("%B %Y"),
		"employee": {"id": emp.name, "name": emp.employee_name, "name_ar": emp.get("alphax_employee_name_ar") or "",
					 "designation": emp.designation or "", "department": (emp.department or "").rsplit(" - ", 1)[0],
					 "joined": formatdate(emp.date_of_joining) if emp.date_of_joining else "",
					 "id_number": emp.get("alphax_iqama_number") or "", "bank": emp.get("bank_name") or "",
					 "account": _mask(doc.get("bank_account_no") or emp.get("iban") or emp.get("bank_ac_no"))},
		"days": {"working": flt(doc.total_working_days, 1), "paid": flt(doc.payment_days, 1),
				 "absent": flt(doc.get("absent_days"), 1), "lwp": flt(doc.get("leave_without_pay"), 1)},
		"earnings": earnings, "deductions": deductions, "penalties": penalties,
		"loans": money(loans) if loans else None,
		"gross": money(doc.gross_pay), "total_deduction": money(flt(doc.total_deduction) + loans),
		"net": money(doc.rounded_total or doc.net_pay), "in_words": doc.get("total_in_words") or "",
		"annual_balance": annual, "warnings": [{**w, "violation_date": formatdate(w.violation_date)} for w in warnings],
		"stamp": _data_uri(conf.get("payslip_stamp")) if show else None,
		"signature": _data_uri(conf.get("payslip_signature")) if show else None,
		"signatory": conf.get("payslip_signatory") or "", "signatory_title": conf.get("payslip_signatory_title") or "",
		"note": conf.get("payslip_note") or "", "note_ar": conf.get("payslip_note_ar") or "",
		"draft": doc.docstatus == 0,
	}


def alphax_payslip(doc):
	"""Jinja method for the ERPNext print format: {{ alphax_payslip(doc) }}."""
	# Reviewed: template path is fixed in the app, or an HR-authored letter rendered in Frappe's sandboxed Jinja.
	return frappe.render_template("alphax_hr/templates/alphax/payslip.html", context(doc))  # nosemgrep


def _get(name):
	user = login_required()
	doc = frappe.get_doc("Salary Slip", name)
	own = frappe.db.get_value("Employee", {"user_id": user}, "name") == doc.employee
	if not (own or is_hr(user)):
		frappe.throw(_("Not permitted."), frappe.PermissionError)
	if own and not is_hr(user) and doc.docstatus != 1:
		frappe.throw(_("This payslip is not final yet."), frappe.PermissionError)
	return doc


@frappe.whitelist()
def preview(name: str):
	return {"html": alphax_payslip(_get(name))}


@frappe.whitelist(methods=["GET"])
def download(name: str):
	from frappe.utils.pdf import get_pdf

	doc = _get(name)
	html = f"<!doctype html><html><head><meta charset='utf-8'></head><body>{alphax_payslip(doc)}</body></html>"
	frappe.response.filename = f"Payslip-{doc.employee}-{getdate(doc.start_date).strftime('%Y-%m')}.pdf"
	frappe.response.filecontent = get_pdf(html, {"page-size": "A4", "margin-top": "10mm", "margin-bottom": "10mm",
												  "margin-left": "10mm", "margin-right": "10mm", "encoding": "UTF-8"})
	frappe.response.type = "pdf"


@frappe.whitelist(methods=["POST"])
def install_print_format(make_default: int | str = 1):
	"""Create (or refresh) the ERPNext print format so desk printing and e-mailed slips use the same layout."""
	from alphax_hr.api._common import require_hr_manager

	require_hr_manager()
	if frappe.db.exists("Print Format", PRINT_FORMAT):
		pf = frappe.get_doc("Print Format", PRINT_FORMAT)
	else:
		pf = frappe.new_doc("Print Format")
		pf.name = PRINT_FORMAT
	pf.update({"doc_type": "Salary Slip", "module": "AlphaX HR", "standard": "No", "custom_format": 1, "print_format_type": "Jinja",
			   "html": "{{ alphax_payslip(doc) }}", "disabled": 0, "css": ""})
	pf.flags.ignore_permissions = True
	pf.save()
	if frappe.utils.cint(make_default):
		from frappe.custom.doctype.property_setter.property_setter import make_property_setter

		make_property_setter("Salary Slip", None, "default_print_format", PRINT_FORMAT, "Data", for_doctype=True)
	return {"name": pf.name, "default": bool(frappe.utils.cint(make_default))}


@frappe.whitelist()
def latest_slip():
	from alphax_hr.api._common import require_hr

	require_hr()
	rows = frappe.get_list("Salary Slip", filters={"docstatus": ["<", 2]}, pluck="name", order_by="end_date desc, modified desc", page_length=1)
	return rows[0] if rows else None
