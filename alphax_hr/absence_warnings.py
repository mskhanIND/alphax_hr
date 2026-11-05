"""Article 80 watch: absence without a valid reason, from the attendance register.

Daily: at 10 consecutive days or 20 days in the contract year a draft written warning is prepared for HR (the law
requires it before a dismissal under Article 80), and HR and the manager are told. Past 15 consecutive or 30 days in
the year HR is told whether a dismissal without award is possible (only when that warning was issued).
"""
from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import add_days, add_months, getdate, nowdate

from alphax_hr.saudi import absence

VIOLATION = "Absence without a valid reason (Article 80 warning)"
VIOLATION_AR = "غياب بدون سبب مشروع (إنذار المادة 80)"
CACHE_KEY = "alphax:art80"


def seed():
	if frappe.db.exists("DocType", "AlphaX Violation Type") and not frappe.db.exists("AlphaX Violation Type", VIOLATION):
		frappe.get_doc({"doctype": "AlphaX Violation Type", "violation_name": VIOLATION, "title_ar": VIOLATION_AR,
						"category": "Working Hours", "enabled": 1, "steps_json": '[{"action": "Warning"}]',
						"reference": "Saudi Labor Law, Article 80 (written warning at 10 consecutive / 20 days in a contract year)"}
					   ).insert(ignore_permissions=True)


def _cells(today):
	"""{employee: {"name", "employee_name", "department", "joining", "days": [(date, code)], "uses_checkins"}} over the
	last 13 months up to yesterday."""
	from alphax_hr.api.attendance import month_data

	out = {}
	recent_from = getdate(add_days(today, -60))
	start = getdate(add_months(today, -12)).replace(day=1)
	month = start
	while month <= today:
		data = month_data(str(month))
		for r in data["rows"]:
			e = out.setdefault(r["employee"], {"name": r["employee"], "employee_name": r["employee_name"],
											   "department": r["department"], "days": [], "recent": 0, "punched": 0,
											   "no_penalties": r.get("no_penalties")})
			for c in r["cells"]:
				d = getdate(c["date"])
				if c.get("not_employed") or d >= today:
					continue
				e["days"].append((d, c["code"]))
				if d >= recent_from and c["code"] not in ("H", "L", ""):
					e["recent"] += 1
					e["punched"] += 1 if c.get("first_in") else 0
		month = getdate(add_months(month, 1))
	for e in out.values():
		# Unmarked days count as absence only for employees who normally check in (half the working days or more).
		e["uses_checkins"] = bool(e["recent"]) and e["punched"] / e["recent"] >= 0.5
	return out


def compute(today=None):
	"""Article 80 figures for every active employee with absences."""
	today = getdate(today or nowdate())
	joining = {e.name: e.date_of_joining for e in frappe.get_all("Employee", filters={"status": "Active"}, fields=["name", "date_of_joining"])}
	rows = []
	for emp, e in _cells(today).items():
		if emp not in joining or e.get("no_penalties"):
			continue
		ys = absence.contract_year_start(getdate(joining[emp]) if joining[emp] else None, today)
		s = absence.evaluate(sorted(e["days"]), ys, counts_unmarked=e["uses_checkins"])
		if not (s["consecutive"] or s["year_total"]):
			continue
		rows.append({**{k: e[k] for k in ("name", "employee_name", "department")}, **s, "due": absence.stage(s),
					 "keys": {"consecutive": f"art80-c-{emp}-{s['consecutive_from']}", "year": f"art80-y-{emp}-{ys}"}})
	return rows


def _warning(key):
	return frappe.db.get_value("AlphaX Penalty", {"source_ref": key, "status": ["!=", "Cancelled"]}, ["name", "status"], as_dict=True)


def _draft(row, kind):
	from alphax_hr.api import penalties

	key = row["keys"][kind]
	if _warning(key):
		return None
	if kind == "consecutive":
		text = _("Absent without a valid reason for {0} consecutive days since {1}. Under Article 80 a written warning is required "
				 "after 10 consecutive days before the contract can be ended after more than 15.").format(
			row["consecutive"], frappe.utils.formatdate(row["consecutive_from"]))
	else:
		text = _("Absent without a valid reason for {0} days in the contract year that started on {1}. Under Article 80 a written "
				 "warning is required after 20 days before the contract can be ended after more than 30.").format(
			row["year_total"], frappe.utils.formatdate(row["year_start"]))
	doc = frappe.new_doc("AlphaX Penalty")
	doc.update({"employee": row["name"], "violation_type": VIOLATION, "violation_date": row["last_absent"],
				"discovered_on": nowdate(), "description": text, "source_ref": key, "status": "Draft"})
	penalties.preview_doc(doc).insert(ignore_permissions=True)
	return doc.name


def _told(emp, key):
	return frappe.db.exists("AlphaX Approval Reminder", {"reference_doctype": "Employee", "reference_name": emp,
														  "stage": "Absence limit", "approver": key})


def daily():
	"""Scheduled: draft the Article 80 warnings that are due and tell HR about the limits."""
	if not frappe.db.exists("DocType", "AlphaX Penalty"):
		return
	seed()
	from alphax_hr.api import alerts

	rows = compute()
	frappe.cache().set_value(CACHE_KEY, rows, expires_in_sec=3600)
	for row in rows:
		try:
			emp = row["name"]
			for kind, due in (("consecutive", "consecutive_warning"), ("year", "year_warning")):
				if due in row["due"]:
					name = _draft(row, kind)
					if name:
						alerts.event("Absence warning", _("Article 80 warning due: {0}").format(row["employee_name"]),
									 _("A draft written warning is ready in Penalties. Issue it so a later dismissal under Article 80 stays possible."),
									 employee=emp, url="/alphax/penalties", doc=("AlphaX Penalty", name), tag=f"art80-{name}")
			for kind, due in (("consecutive", "consecutive_limit"), ("year", "year_limit")):
				key = row["keys"][kind][:140]
				if due in row["due"] and not _told(emp, key):
					w = _warning(row["keys"][kind])
					issued = bool(w and w.status in ("Issued", "Acknowledged", "Objected"))
					msg = (_("The written warning was issued, so the contract may be ended under Article 80 without the end-of-service "
							 "award, after giving the employee a chance to state their reasons.") if issued else
						   _("No written warning was issued at the earlier threshold, so Article 80 cannot be used for this period."))
					to = alerts.event("Absence warning", _("Article 80 limit reached: {0}").format(row["employee_name"]), msg,
									  employee=emp, url="/alphax/penalties", doc=("Employee", emp), tag=f"art80-lim-{emp}")
					alerts._log_reminder("Employee", emp, "Absence limit", key, to)
			frappe.db.commit()
		except Exception:  # noqa: BLE001
			frappe.db.rollback()
			frappe.log_error(title=f"AlphaX Article 80 watch: {row.get('name')}")


@frappe.whitelist()
def watch(refresh: int | str = 0):
	"""HR: employees with absences without a valid reason, the Article 80 thresholds and the warnings."""
	from alphax_hr.api._common import require_hr

	require_hr()
	rows = None if int(refresh or 0) else frappe.cache().get_value(CACHE_KEY)
	if rows is None:
		rows = compute()
		frappe.cache().set_value(CACHE_KEY, rows, expires_in_sec=3600)
	out = []
	for r in rows:
		if r["consecutive"] < 5 and r["year_total"] < 10:
			continue
		out.append({**{k: str(v) if hasattr(v, "isoformat") else v for k, v in r.items() if k != "keys"},
					"warning_consecutive": _warning(r["keys"]["consecutive"]), "warning_year": _warning(r["keys"]["year"])})
	out.sort(key=lambda r: (-len(r["due"]), -r["consecutive"], -r["year_total"]))
	return {"rows": out, "thresholds": {"consecutive_warning": absence.CONSECUTIVE_WARNING, "consecutive_limit": absence.CONSECUTIVE_LIMIT,
										"year_warning": absence.YEAR_WARNING, "year_limit": absence.YEAR_LIMIT},
			"as_of": str(add_days(nowdate(), -1))}
