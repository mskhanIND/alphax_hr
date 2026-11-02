"""Leave balances and ledger: per employee (self or HR) and for the whole workforce (HR)."""
from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, nowdate

from alphax_hr import leave_engine
from alphax_hr.api._common import current_employee, is_hr, require_hr


def _can_view(employee):
	user = frappe.session.user
	if is_hr(user):
		return True
	own = frappe.db.get_value("Employee", {"user_id": user}, "name")
	if own == employee:
		return True
	return bool(frappe.db.get_value("Employee", employee, "leave_approver") == user)


def _balances(employee, on):
	from hrms.hr.doctype.leave_application.leave_application import get_leave_details

	details = get_leave_details(employee, on).get("leave_allocation", {}) or {}
	rows = []
	for lt, d in sorted(details.items()):
		rows.append({"leave_type": lt, "allocated": flt(d.get("total_leaves")), "expired": flt(d.get("expired_leaves")),
					 "taken": flt(d.get("leaves_taken")), "pending": flt(d.get("leaves_pending_approval")),
					 "balance": flt(d.get("remaining_leaves"))})
	return rows


@frappe.whitelist()
def summary(employee=None, date=None):
	"""Balances per leave type, the Art. 117 sick-leave year, and the ledger with running balances."""
	employee = employee or current_employee()
	if not _can_view(employee):
		frappe.throw(_("Not permitted."), frappe.PermissionError)
	on = getdate(date or nowdate())
	entries = frappe.get_all("Leave Ledger Entry", filters={"employee": employee, "docstatus": 1},
							 fields=["leave_type", "transaction_type", "transaction_name", "leaves", "from_date", "to_date",
									 "is_carry_forward", "is_expired", "creation"],
							 order_by="from_date asc, creation asc", limit_page_length=2000)
	running = {}
	ledger = []
	for e in entries:
		running[e.leave_type] = running.get(e.leave_type, 0) + flt(e.leaves)
		ledger.append({**e, "from_date": str(e.from_date), "to_date": str(e.to_date), "creation": str(e.creation),
					   "balance": round(running[e.leave_type], 2)})
	ledger.reverse()  # newest first
	return {"employee": employee, "employee_name": frappe.db.get_value("Employee", employee, "employee_name"),
			"date": str(on), "balances": _balances(employee, on), "sick": leave_engine.sick_status(employee, on),
			"ledger": ledger[:300]}


@frappe.whitelist()
def workforce(department=None, date=None, limit=500):
	"""HR: balance of every leave type for every active employee (one row per employee)."""
	require_hr()
	on = getdate(date or nowdate())
	filters = {"status": "Active"}
	if department:
		filters["department"] = department
	emps = frappe.get_list("Employee", filters=filters, fields=["name", "employee_name", "department"],
						   order_by="employee_name asc", page_length=min(cint(limit) or 500, 1000))
	types, rows = set(), []
	for e in emps:
		bal = {b["leave_type"]: b for b in _balances(e.name, on)}
		types |= set(bal)
		sick = leave_engine.sick_status(e.name, on)
		rows.append({"employee": e.name, "employee_name": e.employee_name, "department": e.department,
					 "balances": bal, "sick_left": sick["left"] if sick else None, "sick_used": sick["used"] if sick else None})
	return {"date": str(on), "leave_types": sorted(types), "rows": rows}


@frappe.whitelist()
def export_workforce(department=None, date=None, file_format="xlsx"):
	data = workforce(department, date)
	types = data["leave_types"]
	head = [_("Employee ID"), _("Employee"), _("Department")]
	for lt in types:
		head += [f"{lt} · {_('Allocated')}", f"{lt} · {_('Taken')}", f"{lt} · {_('Pending')}", f"{lt} · {_('Balance')}"]
	head += [_("Sick used (Art. 117 year)"), _("Sick left")]
	table = [head]
	for r in data["rows"]:
		line = [r["employee"], r["employee_name"], r["department"] or ""]
		for lt in types:
			b = r["balances"].get(lt) or {}
			line += [b.get("allocated", ""), b.get("taken", ""), b.get("pending", ""), b.get("balance", "")]
		line += [r["sick_used"] if r["sick_used"] is not None else "", r["sick_left"] if r["sick_left"] is not None else ""]
		table.append(line)
	if file_format == "csv":
		from frappe.utils.csvutils import to_csv

		frappe.response["filecontent"] = to_csv(table).encode("utf-8-sig")
		frappe.response["filename"] = f"leave-balances-{data['date']}.csv"
	else:
		from frappe.utils.xlsxutils import make_xlsx

		frappe.response["filecontent"] = make_xlsx(table, "Leave balances").getvalue()
		frappe.response["filename"] = f"leave-balances-{data['date']}.xlsx"
	frappe.response["type"] = "binary"
