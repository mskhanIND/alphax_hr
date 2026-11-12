"""Wage Protection: checks before salaries are paid, and the Mudad payroll file filled from the run.

Mudad gives each establishment its own payroll template (Payroll Management → Create Payroll → Upload Payroll File →
Download Template), already listing its registered employees. Mudad requires that name, ID, basic, housing, transport
and total are not changed, so AlphaX never writes those columns: it compares them with payroll and lists differences
(usually a contract or GOSI wage that was not updated). It fills the other columns it recognises (other allowances,
overtime, commissions, deductions, net) from the salary slips, matching employees by ID number, and keeps the file's
layout. A template it cannot read is reported, not guessed.
"""
from __future__ import annotations

import io
import re

import frappe
from frappe import _
from frappe.utils import cint, flt

from alphax_hr.saudi import identity

PROTECTED = ("name", "id", "basic", "housing", "transport", "total")
COLUMNS = {  # normalised header names, exact first, then "contains"
	"id": ["employeeidnumber", "idnumber", "nationalid", "nationalidiqama", "iqamanumber", "iqama", "رقمالهوية",
		   "رقمهويةالموظف", "رقمالإقامة", "رقمالاقامة", "رقمالهويةالإقامة", "الهوية", "رقمالسجلالمدني"],
	"name": ["employeename", "name", "fullname", "اسمالموظف", "الاسم"],
	"basic": ["basicsalary", "basic", "basicwage", "الراتبالأساسي", "الراتبالاساسي", "الأجرالأساسي", "الاساسي", "الأساسي"],
	"housing": ["housingallowance", "housing", "بدلالسكن", "السكن"],
	"transport": ["transportationallowance", "transportallowance", "transportation", "transport", "بدلالنقل", "بدلالمواصلات"],
	"total": ["totalsalary", "total", "grosssalary", "إجماليالراتب", "اجماليالراتب", "الإجمالي", "الاجمالي"],
	"overtime": ["overtime", "overtimeamount", "العملالإضافي", "العملالاضافي", "الإضافي"],
	"commission": ["commissions", "commission", "العمولات", "عمولات"],
	"other": ["otherallowances", "otherallowance", "otherearnings", "additions", "بدلاتأخرى", "البدلاتالأخرى", "بدلاتاخرى",
			  "الإضافات"],
	"deductions": ["deductions", "totaldeductions", "deduction", "الخصومات", "إجماليالخصومات", "الاستقطاعات", "الحسميات"],
	"net": ["netsalary", "net", "netpay", "صافيالراتب", "الصافي", "صافيالأجر"],
}


def _norm(text):
	return re.sub(r"[\s_\-./()\[\]:]+", "", str(text or "")).lower().replace("ـ", "")


def _which(header):
	h = _norm(header)
	if not h:
		return None
	for key, names in COLUMNS.items():
		if h in names:
			return key
	for key, names in COLUMNS.items():
		if any(len(n) >= 5 and n in h for n in names):
			return key
	return None


# ------------------------------------------------------------------ payroll rows
def payroll_rows(company, month, run=None, submitted_only=True):
	"""One row per salary slip of the run with what WPS needs."""
	from alphax_hr.api import components
	from alphax_hr.api.banks import name_for_iban
	from alphax_hr.api.payroll_control import _doc_ids, _get_period, _slip_filters

	doc = _get_period(company, month, create=False, run=run)
	filters = _slip_filters(company, month, _doc_ids(doc) if doc else None)
	if submitted_only:
		filters["docstatus"] = 1
	slips = frappe.get_all("Salary Slip", filters=filters, order_by="employee_name asc",
						   fields=["name", "employee", "employee_name", "gross_pay", "total_deduction", "net_pay", "docstatus"])
	if not slips:
		return []
	keys = {k: components.get(k) for k in ("basic", "housing", "transport", "overtime", "commission")}
	parts = {}
	for d in frappe.get_all("Salary Detail", filters={"parent": ["in", [s.name for s in slips]], "parenttype": "Salary Slip",
													   "parentfield": "earnings"}, fields=["parent", "salary_component", "amount"]):
		p = parts.setdefault(d.parent, {k: 0.0 for k in keys})
		for k, comp in keys.items():
			if comp and d.salary_component == comp:
				p[k] += flt(d.amount)
	meta = frappe.get_meta("Employee")
	fields = [f for f in ("name", "iban", "bank_name", "bank_ac_no", "alphax_iqama_number", "salary_mode") if f == "name" or meta.has_field(f)]
	emps = {e.name: e for e in frappe.get_all("Employee", filters={"name": ["in", [s.employee for s in slips]]}, fields=fields)}
	out = []
	for s in slips:
		e = emps.get(s.employee) or frappe._dict()
		p = parts.get(s.name) or {k: 0.0 for k in keys}
		iban = identity.normalise_iban(e.get("iban") or e.get("bank_ac_no") or "")
		out.append(frappe._dict(
			employee=s.employee, employee_name=s.employee_name, id=identity.normalise(e.get("alphax_iqama_number") or ""),
			iban=iban, bank=e.get("bank_name") or name_for_iban(iban) or "", salary_mode=e.get("salary_mode") or "Bank",
			basic=flt(p["basic"], 2), housing=flt(p["housing"], 2), transport=flt(p["transport"], 2),
			overtime=flt(p["overtime"], 2), commission=flt(p["commission"], 2),
			other=flt(flt(s.gross_pay) - p["basic"] - p["housing"] - p["transport"] - p["overtime"] - p["commission"], 2),
			gross=flt(s.gross_pay, 2), deductions=flt(s.total_deduction, 2), net=flt(s.net_pay, 2), slip=s.name))
	return out


def problems(rows):
	"""What would make the bank or Mudad reject a row, or pay the wrong person."""
	issues = []
	seen_iban, seen_id = {}, {}

	def add(r, code, text, level="error"):
		issues.append({"employee": r.employee, "employee_name": r.employee_name, "code": code, "message": text, "level": level})

	for r in rows:
		kind, err = identity.classify_id(r.id) if r.id else (None, "missing")
		if not r.id:
			add(r, "no_id", _("No national ID / Iqama number"))
		elif err:
			add(r, "bad_id", _("ID / Iqama number {0} is not valid").format(r.id))
		if (r.salary_mode or "Bank") == "Bank":
			if not r.iban:
				add(r, "no_iban", _("No IBAN"))
			elif identity.iban_error(r.iban):
				add(r, "bad_iban", _("IBAN {0} is not valid ({1})").format(r.iban, identity.iban_error(r.iban)))
			elif not r.bank:
				add(r, "no_bank", _("The bank of IBAN {0} is not known").format(r.iban), "warning")
		if r.net <= 0:
			add(r, "no_net", _("Net salary is {0}").format(r.net))
		if r.iban:
			if r.iban in seen_iban:
				add(r, "same_iban", _("Same IBAN as {0}").format(seen_iban[r.iban]), "warning")
			seen_iban.setdefault(r.iban, r.employee_name)
		if r.id:
			if r.id in seen_id:
				add(r, "same_id", _("Same ID number as {0}").format(seen_id[r.id]))
			seen_id.setdefault(r.id, r.employee_name)
	return issues


# ------------------------------------------------------------------ Mudad template
def _read(content):
	import openpyxl

	try:
		wb = openpyxl.load_workbook(io.BytesIO(content))
	except Exception:  # noqa: BLE001
		frappe.throw(_("This is not an Excel file. Upload the .xlsx template downloaded from Mudad."))
	ws = wb.worksheets[0]
	for r in range(1, min(ws.max_row, 15) + 1):
		cols = {}
		for c in range(1, ws.max_column + 1):
			key = _which(ws.cell(r, c).value)
			if key and key not in cols:
				cols[key] = c
		if "id" in cols and len(cols) >= 3:
			return wb, ws, r, cols
	frappe.throw(_("No ID number column was found in the first rows of the file. Upload the template downloaded from Mudad."))


def fill_mudad(content, rows, wages=None):
	"""Fill a Mudad template: returns (xlsx bytes, report)."""
	wb, ws, head, cols = _read(content)
	by_id = {r.id: r for r in rows if r.id}
	report = {"columns": {k: ws.cell(head, c).value for k, c in cols.items()}, "filled": [k for k in cols if k not in PROTECTED],
			  "kept": [k for k in cols if k in PROTECTED], "matched": 0, "differences": [], "not_in_payroll": [],
			  "not_in_template": [], "totals": {"net": 0.0, "deductions": 0.0}}
	used = set()
	for r in range(head + 1, ws.max_row + 1):
		raw = ws.cell(r, cols["id"]).value
		if raw in (None, ""):
			continue
		key = identity.normalise(str(raw).split(".")[0] if isinstance(raw, float) else str(raw))
		row = by_id.get(key)
		name = ws.cell(r, cols["name"]).value if "name" in cols else key
		if not row:
			report["not_in_payroll"].append({"id": key, "name": name})
			continue
		used.add(key)
		report["matched"] += 1
		values = {"other": row.other, "overtime": row.overtime, "commission": row.commission, "deductions": row.deductions,
				  "net": row.net}
		if "overtime" not in cols:
			values["other"] = flt(values["other"] + row.overtime, 2)
		if "commission" not in cols:
			values["other"] = flt(values["other"] + row.commission, 2)
		for k, v in values.items():
			if k in cols:
				ws.cell(r, cols[k]).value = flt(v, 2)
		report["totals"]["net"] += row.net
		report["totals"]["deductions"] += row.deductions
		w = (wages or {}).get(row.employee) or {}
		for k in ("basic", "housing"):
			if k in cols and w.get(k) is not None:
				theirs = flt(ws.cell(r, cols[k]).value)
				if abs(theirs - flt(w[k])) > 0.5:
					report["differences"].append({"employee": row.employee, "employee_name": row.employee_name, "field": k,
												  "mudad": theirs, "alphax": flt(w[k], 2)})
	for row in rows:
		if row.id and row.id not in used:
			report["not_in_template"].append({"employee": row.employee, "employee_name": row.employee_name, "id": row.id})
		elif not row.id:
			report["not_in_template"].append({"employee": row.employee, "employee_name": row.employee_name, "id": None})
	report["totals"] = {k: flt(v, 2) for k, v in report["totals"].items()}
	out = io.BytesIO()
	wb.save(out)
	return out.getvalue(), report


# ------------------------------------------------------------------ API
def _hr():
	from alphax_hr.api._common import require_hr

	require_hr()


@frappe.whitelist()
def check(company: str, month: str, run: str | None = None):
	"""Checks before paying: rows, totals and what would be rejected."""
	_hr()
	rows = payroll_rows(company, month, run)
	issues = problems(rows)
	return {"employees": len(rows), "net": flt(sum(r.net for r in rows), 2), "gross": flt(sum(r.gross for r in rows), 2),
			"by_bank": _by_bank(rows), "issues": issues, "errors": sum(1 for i in issues if i["level"] == "error"),
			"warnings": sum(1 for i in issues if i["level"] == "warning"), "ready": bool(rows) and not any(
				i["level"] == "error" for i in issues)}


def _by_bank(rows):
	out = {}
	for r in rows:
		key = r.bank or (_("Cash / cheque") if (r.salary_mode or "Bank") != "Bank" else _("Unknown bank"))
		b = out.setdefault(key, {"bank": key, "employees": 0, "net": 0.0})
		b["employees"] += 1
		b["net"] = flt(b["net"] + r.net, 2)
	return sorted(out.values(), key=lambda b: -b["net"])


@frappe.whitelist(methods=["POST"])
def mudad(company: str, month: str, file_url: str, run: str | None = None):
	"""Fill the Mudad template the user uploaded; returns the report and a private link to the filled file."""
	_hr()
	f = frappe.get_doc("File", {"file_url": file_url})
	if f.owner != frappe.session.user and "System Manager" not in frappe.get_roles():
		frappe.throw(_("Upload the template yourself."), frappe.PermissionError)
	rows = payroll_rows(company, month, run)
	if not rows:
		frappe.throw(_("No submitted salary slips for this month yet."))
	from alphax_hr.api._wages import wages
	from alphax_hr.api.payroll_control import _bounds

	start, end = _bounds(month)
	content, report = fill_mudad(f.get_content(), rows, wages([r.employee for r in rows], start, end))
	name = f"mudad-payroll-{company}-{start.strftime('%Y-%m')}.xlsx".replace(" ", "-")
	out = frappe.get_doc({"doctype": "File", "file_name": name, "content": content, "is_private": 1})
	out.insert(ignore_permissions=True)
	report["file_url"] = out.file_url
	report["file_name"] = name
	report["issues"] = problems(rows)
	return report
