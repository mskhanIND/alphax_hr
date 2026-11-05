"""Holiday lists inside AlphaX: see which lists are current, extend a list into next year, create a new one with the
Saudi public holidays filled in, and set it on employees or as a company default — without the Frappe desk.

Leave day counts, attendance and payroll payment days all read the employee's HRMS Holiday List (or the company
default). A list that has ended means leave after that date cannot be applied for and absences are not counted.
"""
from __future__ import annotations

from collections import Counter
from datetime import date, timedelta

import frappe
from frappe import _
from frappe.utils import add_days, cint, getdate, nowdate

from alphax_hr.api._common import parse_json, require_hr, require_hr_manager

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
SOON_DAYS = 60
WEEKLY_OFF_TEXT = "Weekly off"


def _personal(name):
	return bool(frappe.db.get_value("Holiday List", name, "alphax_employee")) if frappe.get_meta("Holiday List").has_field("alphax_employee") else False


def weekly_pattern(doc):
	"""Weekdays (0=Mon) that are weekly offs in this list: from its last ten weeks of weekly-off rows, else the
	list's own Weekly Off setting."""
	rows = [getdate(h.holiday_date) for h in doc.holidays if cint(h.weekly_off)]
	if rows:
		end = max(rows)
		recent = Counter(d.weekday() for d in rows if d > end - timedelta(days=70))
		days = sorted(w for w, n in recent.items() if n >= 3)
		if days:
			return days
	if doc.get("weekly_off") in WEEKDAYS:
		return [WEEKDAYS.index(doc.weekly_off)]
	return []


def public_holidays(start, end, country="SA"):
	"""Public holidays between start and end from the holidays library ERPNext ships with. Islamic holidays are
	estimates until the moon sighting; HR can move them. Returns (rows, available)."""
	start, end = getdate(start), getdate(end)
	try:
		import holidays as lib

		cal = lib.country_holidays(country, years=list(range(start.year, end.year + 1)), language="en_US")
	except Exception:  # noqa: BLE001 - library missing or shadowed on this server
		return [], False
	return [{"date": str(d), "description": str(n)} for d, n in sorted(cal.items()) if start <= d <= end], True


def _rows_for(start, end, weekdays, public):
	"""Holiday rows: public holidays first (a weekly off on the same day keeps the holiday name)."""
	rows, seen = [], set()
	for h in public:
		d = getdate(h["date"])
		if start <= d <= end and d not in seen:
			rows.append({"holiday_date": d, "description": h.get("description") or _("Public holiday"), "weekly_off": 0})
			seen.add(d)
	d = start
	while d <= end:
		if d.weekday() in weekdays and d not in seen:
			rows.append({"holiday_date": d, "description": _(WEEKLY_OFF_TEXT), "weekly_off": 1})
			seen.add(d)
		d += timedelta(days=1)
	return sorted(rows, key=lambda r: r["holiday_date"])


def _status(to_date, from_date, today):
	to_date, from_date = getdate(to_date), getdate(from_date)
	if to_date < today:
		return "Ended", (today - to_date).days
	if from_date > today:
		return "Future", (from_date - today).days
	left = (to_date - today).days
	return ("Ends soon" if left < SOON_DAYS else "Current"), left


def _employees_by_list():
	"""Active employees per base list (personal week-off lists count for the list they were made from)."""
	meta = frappe.get_meta("Holiday List")
	base_of = {}
	if meta.has_field("alphax_base_list"):
		base_of = {h.name: h.alphax_base_list for h in frappe.get_all("Holiday List", filters={"alphax_employee": ["is", "set"]},
																	   fields=["name", "alphax_base_list"])}
	defaults = {c.name: c.default_holiday_list for c in frappe.get_all("Company", fields=["name", "default_holiday_list"])}
	per, none = Counter(), []
	for e in frappe.get_all("Employee", filters={"status": "Active"}, fields=["name", "employee_name", "holiday_list", "company"]):
		hl = e.holiday_list or defaults.get(e.company)
		if not hl:
			none.append(e)
			continue
		per[base_of.get(hl) or hl] += 1
	return per, none, defaults, base_of


@frappe.whitelist()
def overview():
	require_hr()
	today = getdate(nowdate())
	per, none, defaults, base_of = _employees_by_list()
	lists = []
	filters = {"alphax_employee": ["is", "not set"]} if frappe.get_meta("Holiday List").has_field("alphax_employee") else {}
	for h in frappe.get_all("Holiday List", filters=filters, fields=["name", "from_date", "to_date", "weekly_off"], order_by="to_date desc"):
		doc = frappe.get_doc("Holiday List", h.name)
		status, days = _status(h.to_date, h.from_date, today)
		public = [r for r in doc.holidays if not cint(r.weekly_off)]
		lists.append({"name": h.name, "from_date": str(h.from_date), "to_date": str(h.to_date), "status": status, "days": days,
					  "weekly_off": [WEEKDAYS[w] for w in weekly_pattern(doc)], "public_holidays": len(public),
					  "employees": per.get(h.name, 0), "personal_lists": sum(1 for b in base_of.values() if b == h.name),
					  "default_for": [c for c, d in defaults.items() if d == h.name],
					  "next_year_end": str(date(getdate(h.to_date).year + 1, 12, 31))})
	problems = []
	for item in lists:
		if not item["employees"] and not item["default_for"]:
			continue
		who = _("{0} employees").format(item["employees"]) + (
			" · " + _("default for {0}").format(", ".join(item["default_for"])) if item["default_for"] else "")
		if item["status"] == "Ended":
			problems.append({"level": "error", "list": item["name"], "action": "extend",
							 "text": _("'{0}' ended on {1} ({2}). Leave after that date cannot be applied for and attendance is not counted. "
									   "Extend it, or create a new list and move the employees.").format(item["name"], frappe.utils.formatdate(item["to_date"]), who)})
		elif item["status"] == "Ends soon":
			problems.append({"level": "warn", "list": item["name"], "action": "extend",
							 "text": _("'{0}' ends on {1}, in {2} days ({3}). Leave for next year cannot be applied for until it is extended.").format(
								 item["name"], frappe.utils.formatdate(item["to_date"]), item["days"], who)})
	if none:
		problems.append({"level": "error", "action": "assign", "list": None,
						 "text": _("{0} employees have no holiday list and their company has no default: their leave days and attendance cannot be counted.").format(len(none)),
						 "employees": [{"name": e.name, "employee_name": e.employee_name} for e in none[:50]]})
	_rows, available = public_holidays(today, today)
	return {"lists": lists, "problems": problems, "companies": sorted(defaults), "library": available,
			"weekdays": WEEKDAYS, "can_edit": bool(set(frappe.get_roles()) & {"HR Manager", "System Manager"})}


@frappe.whitelist()
def suggest(from_date: str, to_date: str, weekly_off: str | list | None = None):
	"""Holidays a new list or an extension would get (for HR to check before saving)."""
	require_hr()
	start, end = getdate(from_date), getdate(to_date)
	if end < start:
		frappe.throw(_("The end date is before the start date."))
	public, available = public_holidays(start, end)
	return {"public": public, "library": available,
			"weekly_off_days": len(_rows_for(start, end, [WEEKDAYS.index(w) for w in (parse_json(weekly_off) or []) if w in WEEKDAYS], []))}


@frappe.whitelist(methods=["POST"])
def create(data: str | dict):
	"""A new holiday list: weekly offs for the chosen days plus the public holidays HR kept."""
	require_hr_manager()
	d = parse_json(data) or {}
	name = (d.get("name") or "").strip()
	if not name:
		frappe.throw(_("Give the holiday list a name."))
	if frappe.db.exists("Holiday List", name):
		frappe.throw(_("A holiday list named {0} already exists.").format(name))
	start, end = getdate(d.get("from_date")), getdate(d.get("to_date"))
	if end < start:
		frappe.throw(_("The end date is before the start date."))
	weekdays = [WEEKDAYS.index(w) for w in d.get("weekly_off") or [] if w in WEEKDAYS]
	doc = frappe.get_doc({"doctype": "Holiday List", "holiday_list_name": name, "from_date": start, "to_date": end,
						  "weekly_off": WEEKDAYS[weekdays[0]] if len(weekdays) == 1 else None,
						  "holidays": _rows_for(start, end, weekdays, d.get("public") or [])})
	if doc.meta.has_field("country"):
		doc.country = "Saudi Arabia"
	doc.insert()
	_assign(name, d.get("assign") or {})
	return overview()


@frappe.whitelist(methods=["POST"])
def extend(name: str, to_date: str, public: str | list | None = None):
	"""Carry a list into a later period: same weekly offs, the public holidays HR kept. Personal week-off lists made
	from it (roster) are extended with their own week-offs and receive the public holidays."""
	require_hr_manager()
	doc = frappe.get_doc("Holiday List", name)
	if doc.get("alphax_employee"):
		frappe.throw(_("This is an employee's own week-off list; extend the list it was made from."))
	old_end, new_end = getdate(doc.to_date), getdate(to_date)
	if new_end <= old_end:
		frappe.throw(_("Choose a date after {0}.").format(frappe.utils.formatdate(old_end)))
	start = add_days(old_end, 1)
	start = getdate(start)
	public = parse_json(public) if public is not None else public_holidays(start, new_end)[0]
	for name_p in frappe.get_all("Holiday List", filters={"alphax_base_list": name}, pluck="name") if doc.meta.has_field("alphax_base_list") else []:
		p = frappe.get_doc("Holiday List", name_p)
		if getdate(p.to_date) < new_end:
			p_start = max(getdate(add_days(p.to_date, 1)), start)
			for r in _rows_for(p_start, new_end, weekly_pattern(p), []):
				p.append("holidays", r)
			p.to_date = new_end
			p.save(ignore_permissions=True)
	for r in _rows_for(start, new_end, weekly_pattern(doc), public):
		doc.append("holidays", r)
	doc.to_date = new_end
	doc.save()  # copies the public holidays into the personal lists (week_off.sync_public_holidays)
	return overview()


@frappe.whitelist()
def holidays_of(name: str):
	require_hr()
	doc = frappe.get_doc("Holiday List", name)
	return {"name": name, "from_date": str(doc.from_date), "to_date": str(doc.to_date),
			"holidays": [{"date": str(h.holiday_date), "description": h.description, "weekly_off": cint(h.weekly_off)}
						 for h in sorted(doc.holidays, key=lambda h: getdate(h.holiday_date)) if not cint(h.weekly_off)],
			"weekly_off": [WEEKDAYS[w] for w in weekly_pattern(doc)]}


@frappe.whitelist(methods=["POST"])
def save_public(name: str, holidays: str | list):
	"""Replace the public holidays of a list (e.g. when the Eid dates are announced); weekly offs are kept."""
	require_hr_manager()
	doc = frappe.get_doc("Holiday List", name)
	rows = parse_json(holidays) or []
	lo, hi = getdate(doc.from_date), getdate(doc.to_date)
	keep = [h for h in doc.holidays if cint(h.weekly_off)]
	new = {}
	for r in rows:
		d = getdate(r.get("date"))
		if not lo <= d <= hi:
			frappe.throw(_("{0} is outside the list ({1} to {2}).").format(frappe.utils.formatdate(d), frappe.utils.formatdate(lo), frappe.utils.formatdate(hi)))
		new[d] = (r.get("description") or _("Public holiday"))[:140]
	doc.holidays = []
	for h in keep:
		if getdate(h.holiday_date) not in new:
			doc.append("holidays", {"holiday_date": h.holiday_date, "description": h.description, "weekly_off": 1})
	for d, desc in new.items():
		doc.append("holidays", {"holiday_date": d, "description": desc, "weekly_off": 0})
	doc.holidays.sort(key=lambda h: getdate(h.holiday_date))
	for i, h in enumerate(doc.holidays, 1):
		h.idx = i
	doc.save()
	return holidays_of(name)


def _assign(name, a):
	"""Set a list as company default and/or on employees. Employees on their own week-off list keep it and get it
	re-based on this list."""
	out = {"employees": 0, "personal": 0}
	for company in a.get("companies") or []:
		if frappe.db.exists("Company", company):
			frappe.db.set_value("Company", company, "default_holiday_list", name)
	targets = set(a.get("employees") or [])
	if a.get("from_list"):
		targets |= set(frappe.get_all("Employee", filters={"status": "Active", "holiday_list": a["from_list"]}, pluck="name"))
	if a.get("without_list"):
		targets |= set(frappe.get_all("Employee", filters={"status": "Active", "holiday_list": ["is", "not set"]}, pluck="name"))
	for emp in targets:
		current = frappe.db.get_value("Employee", emp, "holiday_list")
		if current and _personal(current):
			frappe.db.set_value("Holiday List", current, "alphax_base_list", name)
			out["personal"] += 1
			continue
		frappe.db.set_value("Employee", emp, "holiday_list", name)  # one field; other data gaps must not block it
		out["employees"] += 1
	return out


@frappe.whitelist(methods=["POST"])
def assign(name: str, data: str | dict):
	require_hr_manager()
	if not frappe.db.exists("Holiday List", name):
		frappe.throw(_("Holiday list {0} not found.").format(name))
	res = _assign(name, parse_json(data) or {})
	return {**overview(), "assigned": res}
