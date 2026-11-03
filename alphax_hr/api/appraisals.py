"""Appraisals: HRMS Appraisal Cycles and Appraisals, shown and opened inside AlphaX."""
from __future__ import annotations

import frappe
from frappe.utils import cint, flt

from alphax_hr.api._common import current_employee, require_hr

FIELDS = ["name", "employee", "employee_name", "department", "designation", "appraisal_cycle", "docstatus", "total_score",
		  "self_score", "avg_feedback_score", "goal_score_percentage", "final_score", "start_date", "end_date", "modified"]


def _rows(filters, limit=500):
	if not frappe.db.exists("DocType", "Appraisal"):
		return []
	meta = frappe.get_meta("Appraisal")
	rows = frappe.get_list("Appraisal", filters=filters, fields=[f for f in FIELDS if f in ("name", "docstatus", "modified") or meta.has_field(f)],
						   order_by="modified desc", page_length=min(cint(limit) or 500, 2000))
	for r in rows:
		r["status"] = {0: "Draft", 1: "Submitted", 2: "Cancelled"}[r.docstatus]
		for k in ("start_date", "end_date", "modified"):
			if r.get(k):
				r[k] = str(r[k])
	return rows


@frappe.whitelist()
def cycles():
	require_hr()
	if not frappe.db.exists("DocType", "Appraisal Cycle"):
		return {"installed": False, "cycles": []}
	out = frappe.get_list("Appraisal Cycle", fields=["name", "cycle_name", "start_date", "end_date", "status", "company"],
						  order_by="start_date desc", page_length=200)
	for c in out:
		stats = frappe.get_all("Appraisal", filters={"appraisal_cycle": c.name, "docstatus": ["<", 2]},
							   fields=["count(name) as n", "sum(case when docstatus=1 then 1 else 0 end) as done", "avg(final_score) as avg"])[0]
		c.update({"appraisals": cint(stats.n), "submitted": cint(stats.done), "average": flt(stats.avg, 2),
				  "start_date": str(c.start_date), "end_date": str(c.end_date)})
	return {"installed": True, "cycles": out}


@frappe.whitelist()
def appraisals(cycle=None, department=None):
	require_hr()
	filters = {"docstatus": ["<", 2]}
	if cycle:
		filters["appraisal_cycle"] = cycle
	if department:
		filters["department"] = department
	return _rows(filters)


@frappe.whitelist()
def mine():
	"""The employee's own appraisals. Many sites give employees no role access to Appraisal, so the list is
	read for their own employee only (scores, not the form); the record opens only where they may read it."""
	employee = current_employee()
	if not frappe.db.exists("DocType", "Appraisal"):
		return []
	meta = frappe.get_meta("Appraisal")
	rows = frappe.get_all("Appraisal", filters={"employee": employee, "docstatus": ["<", 2]},
						  fields=[f for f in FIELDS if f in ("name", "docstatus", "modified") or meta.has_field(f)],
						  order_by="modified desc", limit_page_length=50)
	can_open = frappe.has_permission("Appraisal", "read")
	for r in rows:
		r["status"] = {0: "Draft", 1: "Submitted", 2: "Cancelled"}[r.docstatus]
		r["can_open"] = can_open
		for k in ("start_date", "end_date", "modified"):
			if r.get(k):
				r[k] = str(r[k])
	return rows
