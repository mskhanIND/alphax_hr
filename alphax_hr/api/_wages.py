"""Resolve the wage figures the Saudi rules need from HRMS payroll data.

Source of truth, in order:
1. Salary Slip components of the period, mapped in AlphaX HR Settings.
2. The latest submitted Salary Structure Assignment ``base`` (treated as
   basic only; a warning is returned so HR can fix the mapping).
"""
from __future__ import annotations

from collections import defaultdict

import frappe
from frappe.utils import flt

from alphax_hr.api._common import settings


def component_map():
	conf = settings()
	result = defaultdict(set)
	for row in conf.component_map:
		result[row.purpose].add(row.salary_component)
	return result


def slip_components(employees, start, end):
	"""{employee: {component: amount}} from submitted slips overlapping the period (latest slip wins)."""
	if not employees:
		return {}
	slips = frappe.get_list(
		"Salary Slip",
		filters={"employee": ["in", list(employees)], "docstatus": 1,
				 "start_date": ["<=", end], "end_date": [">=", start]},
		fields=["name", "employee", "end_date"],
		order_by="end_date asc",
		page_length=50000,
	)
	latest = {}
	for s in slips:
		latest[s.employee] = s.name
	if not latest:
		return {}
	details = frappe.get_list(
		"Salary Detail",
		parent_doctype="Salary Slip",
		filters={"parent": ["in", list(latest.values())], "parentfield": "earnings"},
		fields=["parent", "salary_component", "amount"],
		page_length=100000,
	)
	by_slip = defaultdict(dict)
	for d in details:
		by_slip[d.parent][d.salary_component] = by_slip[d.parent].get(d.salary_component, 0) + flt(d.amount)
	return {emp: by_slip.get(slip, {}) for emp, slip in latest.items()}


def latest_base(employees, on):
	if not employees:
		return {}
	rows = frappe.get_list(
		"Salary Structure Assignment",
		filters={"employee": ["in", list(employees)], "docstatus": 1, "from_date": ["<=", on]},
		fields=["employee", "base", "from_date"],
		order_by="from_date asc",
		page_length=10000,
	)
	return {r.employee: flt(r.base) for r in rows}


def wages(employees, start, end):
	"""{employee: {"basic", "housing", "eosb_wage", "source", "warnings"}}"""
	cmap = component_map()
	slips = slip_components(employees, start, end)
	bases = latest_base([e for e in employees if e not in slips], end)
	out = {}
	for emp in employees:
		warnings = []
		if emp in slips:
			comps = slips[emp]
			basic = sum(comps.get(c, 0) for c in cmap.get("GOSI Basic", ()))
			housing = sum(comps.get(c, 0) for c in cmap.get("GOSI Housing", ()))
			eosb_wage = sum(comps.get(c, 0) for c in cmap.get("EOSB Wage", ())) or basic + housing
			source = "salary_slip"
			if not cmap.get("GOSI Basic"):
				warnings.append("component_mapping_missing")
		elif emp in bases:
			basic, housing, eosb_wage, source = bases[emp], 0.0, bases[emp], "salary_structure_assignment"
			warnings.append("no_salary_slip_for_period")
		else:
			basic = housing = eosb_wage = 0.0
			source = "none"
			warnings.append("no_salary_data")
		out[emp] = {"basic": flt(basic, 2), "housing": flt(housing, 2), "eosb_wage": flt(eosb_wage, 2),
					"source": source, "warnings": warnings}
	return out
