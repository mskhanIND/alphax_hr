"""Saudization by profession: a standard profession catalogue, dated localization rules, and the controls on
designations and employees.

Each Designation maps to a standard profession (Saudi occupational classification); a profession belongs to a
Saudization group (Sales, Marketing, Accounting, Administrative support ...). A group has dated rules: either
"Saudis only" or a minimum Saudi share, applying from a number of workers in the group, with the wage from which a
Saudi counts. Rules change often, so they are data HR keeps up to date; the shipped ones carry their source and the
date they were last checked.
"""
from __future__ import annotations

import difflib
import math
import re

import frappe
from frappe import _
from frappe.utils import cint, flt, get_first_day, get_last_day, getdate, nowdate

PROFESSION = "AlphaX Profession"
RULE = "AlphaX Localization Rule"
SAUDIS_ONLY = "Saudis only"
MIN_PERCENT = "Minimum Saudi %"
CHECKED = "2026-11-05"
HRSD = "https://www.hrsd.gov.sa/en/localization-decisions"

# group: [(rule name, kind, percent, from, min workers, min wage, activity, source note)]
RULES = {
	"Administrative support": [("Administrative support 100% (05-04-2026)", SAUDIS_ONLY, 100, "2026-04-05", 0, 0, None,
								"69 administrative-support professions incl. HR, personnel, secretarial, translation, data entry. "
								"Shipped titles are examples; add the rest from the HRSD procedural guide.")],
	"Tourism front office": [("Tourism front office 100% (22-04-2026)", SAUDIS_ONLY, 100, "2026-04-22", 0, 0, "Tourism establishments",
							  "Receptionist, hotel receptionist, telephone operator, information clerk in tourism establishments.")],
	"Marketing": [("Marketing 60% (19-04-2026)", MIN_PERCENT, 60, "2026-04-19", 3, 5500, None, "10 marketing professions.")],
	"Sales": [("Sales 60% (19-04-2026)", MIN_PERCENT, 60, "2026-04-19", 3, 0, None, "Sales professions.")],
	"Procurement": [("Procurement 70% (31-05-2026)", MIN_PERCENT, 70, "2026-05-31", 3, 0, None, "12 procurement professions.")],
	"Project management": [("Project management 70% (14-02-2027)", MIN_PERCENT, 70, "2027-02-14", 3, 0, None,
							"Project management manager, engineer and specialist.")],
	"Accounting": [("Accounting 40% (27-10-2025)", MIN_PERCENT, 40, "2025-10-27", 5, 6000, None, "Phase 1. Saudi accountants need SOCPA accreditation to count; diploma holders count from SAR 4,500."),
				   ("Accounting 50% (27-10-2026)", MIN_PERCENT, 50, "2026-10-27", 5, 6000, None, "Phase 2."),
				   ("Accounting 60% (27-10-2027)", MIN_PERCENT, 60, "2027-10-27", 5, 6000, None, "Phase 3."),
				   ("Accounting 70% (27-10-2028)", MIN_PERCENT, 70, "2028-10-27", 5, 6000, None, "Phase 4.")],
	"Engineering": [("Engineering 30% (30-06-2026)", MIN_PERCENT, 30, "2026-06-30", 5, 8000, None,
					 "46 engineering professions. Saudi engineers need Saudi Council of Engineers accreditation to count.")],
	"Technical engineering": [("Technical engineering 30% (27-07-2025)", MIN_PERCENT, 30, "2025-07-27", 5, 5000, None, "Technical engineering professions.")],
	"Pharmacy": [("Pharmacy 55% (27-07-2025)", MIN_PERCENT, 55, "2025-07-27", 5, 7000, "Pharmacy-related activities",
				  "65% in hospital pharmacy, 35% in community pharmacies and medical complexes: change the % for your activity.")],
	"Dentistry": [("Dentistry 55% (27-01-2026)", MIN_PERCENT, 55, "2026-01-27", 3, 9000, None, "Phase 2.")],
}

# (English, Arabic, group, other titles)
PROFESSIONS = [
	("Human Resources Manager", "مدير موارد بشرية", "Administrative support", "HR Manager\nHead of HR\nHR Director"),
	("Personnel Manager", "مدير شؤون الموظفين", "Administrative support", "Personnel Affairs Manager"),
	("Labour Affairs Manager", "مدير شؤون العمال", "Administrative support", "Labor Affairs Manager"),
	("Human Resources Specialist", "أخصائي موارد بشرية", "Administrative support", "HR Specialist\nHR Officer\nHR Executive\nHR Generalist"),
	("Human Resources Clerk", "موظف موارد بشرية", "Administrative support", "HR Clerk\nHR Assistant\nPersonnel Clerk"),
	("Recruitment Officer", "موظف توظيف", "Administrative support", "Recruitment Specialist\nRecruiter\nTalent Acquisition Specialist"),
	("Government Relations Officer", "معقب", "Administrative support", "GRO\nPublic Relations Officer (Government)\nMuaqqib"),
	("Secretary", "سكرتير", "Administrative support", "Office Secretary"),
	("Executive Secretary", "سكرتير تنفيذي", "Administrative support", "Executive Assistant"),
	("Stenographer", "كاتب اختزال", "Administrative support", ""),
	("Typist", "طابع", "Administrative support", ""),
	("Data Entry Operator", "مدخل بيانات", "Administrative support", "Data Entry Clerk\nData Entry"),
	("Translator", "مترجم", "Administrative support", "Interpreter"),
	("Storekeeper", "أمين مستودع", "Administrative support", "Store Keeper\nWarehouse Keeper"),
	("Receptionist", "موظف استقبال", "Administrative support", "Reception Clerk\nFront Desk"),
	("Hotel Receptionist", "موظف استقبال فندق", "Tourism front office", ""),
	("Telephone Operator", "عامل هاتف", "Tourism front office", "Switchboard Operator"),
	("Information Clerk", "موظف استعلامات", "Tourism front office", ""),
	("Marketing Manager", "مدير تسويق", "Marketing", "Head of Marketing\nMarketing Director"),
	("Marketing Specialist", "أخصائي تسويق", "Marketing", "Marketing Officer\nMarketing Executive\nDigital Marketing Specialist"),
	("Advertising Manager", "مدير إعلان", "Marketing", ""),
	("Advertising Agent", "وكيل إعلان", "Marketing", ""),
	("Advertising Specialist", "أخصائي إعلان", "Marketing", ""),
	("Advertising Designer", "مصمم إعلان", "Marketing", ""),
	("Graphic Designer", "مصمم جرافيك", "Marketing", "Graphics Designer"),
	("Public Relations Manager", "مدير علاقات عامة", "Marketing", "PR Manager"),
	("Public Relations Specialist", "أخصائي علاقات عامة", "Marketing", "PR Specialist\nPR Officer"),
	("Photographer", "مصور", "Marketing", ""),
	("Sales Manager", "مدير مبيعات", "Sales", "Head of Sales\nSales Director"),
	("Retail Sales Manager", "مدير مبيعات التجزئة", "Sales", ""),
	("Wholesale Sales Manager", "مدير مبيعات الجملة", "Sales", ""),
	("Sales Representative", "مندوب مبيعات", "Sales", "Sales Rep\nSalesman\nSales Executive\nSales Officer"),
	("Retail Sales Representative", "مندوب مبيعات تجزئة", "Sales", ""),
	("Wholesale Sales Representative", "مندوب مبيعات جملة", "Sales", ""),
	("Sales Specialist", "أخصائي مبيعات", "Sales", ""),
	("IT and Communications Equipment Sales Specialist", "أخصائي مبيعات أجهزة تقنية المعلومات والاتصالات", "Sales", "IT Sales Specialist"),
	("Commercial Specialist", "أخصائي تجاري", "Sales", "Business Development Specialist"),
	("Goods Broker", "وسيط سلع", "Sales", "Commodity Broker"),
	("Procurement Manager", "مدير مشتريات", "Procurement", "Purchasing Manager\nPurchase Manager\nHead of Procurement"),
	("Procurement Specialist", "أخصائي مشتريات", "Procurement", "Purchasing Specialist\nProcurement Officer\nPurchasing Officer\nBuyer"),
	("Purchasing Representative", "مندوب مشتريات", "Procurement", "Purchase Representative"),
	("Contracts Specialist", "أخصائي عقود", "Procurement", "Contracts Officer"),
	("Project Management Manager", "مدير إدارة المشاريع", "Project management", "PMO Manager\nProject Manager"),
	("Project Management Engineer", "مهندس إدارة مشاريع", "Project management", ""),
	("Project Management Specialist", "أخصائي إدارة مشاريع", "Project management", "Project Coordinator\nPMO Specialist"),
	("Accountant", "محاسب", "Accounting", "General Accountant\nSenior Accountant\nJunior Accountant"),
	("Chief Accountant", "رئيس حسابات", "Accounting", "Head Accountant"),
	("Financial Accountant", "محاسب مالي", "Accounting", ""),
	("Cost Accountant", "محاسب تكاليف", "Accounting", ""),
	("Accounting Manager", "مدير حسابات", "Accounting", "Accounts Manager"),
	("Internal Auditor", "مراجع داخلي", "Accounting", "Internal Audit Specialist\nAuditor"),
	("Civil Engineer", "مهندس مدني", "Engineering", ""),
	("Mechanical Engineer", "مهندس ميكانيكي", "Engineering", ""),
	("Electrical Engineer", "مهندس كهربائي", "Engineering", ""),
	("Industrial Engineer", "مهندس صناعي", "Engineering", "General Industrial Engineer"),
	("Chemical Engineer", "مهندس كيميائي", "Engineering", ""),
	("Civil Engineering Technician", "فني هندسة مدنية", "Technical engineering", ""),
	("Electrical Technician", "فني كهرباء", "Technical engineering", ""),
	("Mechanical Technician", "فني ميكانيكا", "Technical engineering", ""),
	("Pharmacist", "صيدلي", "Pharmacy", ""),
	("Dentist", "طبيب أسنان", "Dentistry", "Dental Specialist\nGeneral Dentist"),
]


def installed():
	return bool(frappe.db.exists("DocType", RULE))


def seed():
	"""Shipped rules and professions; existing ones (and HR's edits) are kept."""
	if not installed():
		return
	for group, rules in RULES.items():
		for name, kind, pct, start, workers, wage, activity, notes in rules:
			if frappe.db.exists(RULE, name):
				continue
			frappe.get_doc({"doctype": RULE, "rule_name": name, "localization_group": group, "enabled": 1, "kind": kind, "percent": pct,
							"effective_from": start, "min_workers": workers, "min_wage": wage, "activity": activity, "source": HRSD,
							"last_reviewed": CHECKED, "notes": notes}).insert(ignore_permissions=True)
	for name, ar, group, aliases in PROFESSIONS:
		if not frappe.db.exists(PROFESSION, name):
			frappe.get_doc({"doctype": PROFESSION, "profession_name": name, "title_ar": ar, "localization_group": group,
							"aliases": aliases}).insert(ignore_permissions=True)


# ------------------------------------------------------------------------------------------------ rules
def _rules():
	cache = getattr(frappe.local, "alphax_loc_rules", None)
	if cache is None:
		cache = frappe.get_all(RULE, filters={"enabled": 1}, fields=["name", "localization_group", "kind", "percent", "effective_from",
																	  "min_workers", "min_wage", "activity", "notes", "last_reviewed"],
							   order_by="effective_from asc") if installed() else []
		frappe.local.alphax_loc_rules = cache
	return cache


def rule_for(group, day=None):
	"""The rule in force for a group on a day (the latest one that has started)."""
	day = getdate(day or nowdate())
	current = None
	for r in _rules():
		if r.localization_group == group and getdate(r.effective_from) <= day:
			current = r
	return current


def next_rule(group, day=None):
	day = getdate(day or nowdate())
	return next((r for r in _rules() if r.localization_group == group and getdate(r.effective_from) > day), None)


def group_of_designation(designation):
	if not designation or not frappe.get_meta("Designation").has_field("alphax_profession"):
		return None, None
	prof = frappe.get_cached_value("Designation", designation, "alphax_profession")
	return prof, (frappe.get_cached_value(PROFESSION, prof, "localization_group") if prof else None)


def counts_as_saudi(emp):
	return bool(cint(emp.get("alphax_is_saudi")) or cint(emp.get("alphax_counts_as_saudi")))


# ------------------------------------------------------------------------------------------------ control
def validate_employee(doc, method=None):
	"""Employee validate: a non-Saudi cannot be given a Saudis-only profession. Existing assignments are only
	reported (HR status and the Saudization page), so older records keep saving."""
	if doc.status != "Active" or counts_as_saudi(doc) or not installed():
		return
	changed = doc.is_new() or doc.has_value_changed("designation") or doc.has_value_changed("status") \
		or doc.has_value_changed("alphax_is_saudi")
	if not changed:
		return
	prof, group = group_of_designation(doc.designation)
	r = rule_for(group) if group else None
	if not r or r.kind != SAUDIS_ONLY:
		return
	mode = frappe.db.get_single_value("AlphaX HR Settings", "saudi_only_control") if frappe.get_meta("AlphaX HR Settings").has_field(
		"saudi_only_control") else "Block"
	msg = _("{0} ({1}) is reserved for Saudi nationals ({2}, since {3}). Choose another designation, or tick "
			"'Counts as Saudi (Nitaqat)' if the employee is the mother of a Saudi citizen or the child of a Saudi woman.").format(
		doc.designation, prof, _(group), frappe.utils.formatdate(r.effective_from))
	if (mode or "Block") == "Block":
		frappe.throw(msg, title=_("Saudis-only profession"))
	elif mode == "Warn":
		frappe.msgprint(msg, title=_("Saudis-only profession"), indicator="orange")


# ------------------------------------------------------------------------------------------------ matching
def _norm(text):
	return re.sub(r"[^a-z0-9؀-ۿ ]+", " ", (text or "").lower()).split()


def _catalogue():
	out = []
	for p in frappe.get_all(PROFESSION, fields=["name", "title_ar", "localization_group", "aliases"]):
		names = [p.name] + ([p.title_ar] if p.title_ar else []) + [a for a in (p.aliases or "").splitlines() if a.strip()]
		out.append((p, [" ".join(_norm(n)) for n in names]))
	return out


STOP = {"of", "and", "the", "&", "-", "senior", "junior", "sr", "jr", "assistant", "lead", "chief", "head"}


def suggest(designation, catalogue=None):
	"""Best standard profession for a designation name: (profession, score 0..1). Suggested only when every
	meaningful word of a profession title is in the designation ("Senior Accountant" -> Accountant), or the names
	are nearly the same (spelling); "Manager" alone or "Product Manager" get no suggestion."""
	words = _norm(designation)
	if not words:
		return None, 0
	have = set(words) - STOP
	joined = " ".join(words)
	best, score = None, 0.0
	for p, names in catalogue or _catalogue():
		for n in names:
			need = set(n.split()) - STOP
			if not need:
				continue
			if n == joined:
				s = 1.0
			elif need <= have:
				# all of the profession's words are there; fewer extras = closer; a title word missing ("Chief") = further
				s = 0.8 + 0.15 * len(need) / max(len(have), 1) + (0.04 if set(n.split()) <= set(words) else -0.04)
			else:
				s = difflib.SequenceMatcher(None, joined, n).ratio()
				s = s if s >= 0.92 else 0.0  # spelling variants only
			if s > score:
				best, score = p.name, s
	return (best, round(score, 2)) if score >= 0.8 else (None, round(score, 2))


# ------------------------------------------------------------------------------------------------ report
def _needed(saudis, total, pct):
	"""Saudis to add (each also adds a worker) to reach pct."""
	r = flt(pct) / 100
	if r >= 1:
		return total - saudis
	if total and saudis / total >= r:
		return 0
	return max(0, math.ceil((r * total - saudis) / (1 - r) - 1e-9))


def report(company=None, day=None):
	"""Per Saudization group: workers, Saudis who count, the rule in force and the next phase, and violations."""
	from alphax_hr.api._wages import wages

	day = getdate(day or nowdate())
	filters = {"status": "Active"}
	if company:
		filters["company"] = company
	meta = frappe.get_meta("Employee")
	fields = ["name", "employee_name", "designation", "department"] + [f for f in ("alphax_is_saudi", "alphax_counts_as_saudi") if meta.has_field(f)]
	emps = frappe.get_all("Employee", filters=filters, fields=fields)
	des = {d.name: d.alphax_profession for d in frappe.get_all("Designation", fields=["name", "alphax_profession"])} \
		if frappe.get_meta("Designation").has_field("alphax_profession") else {}
	groups = {p.name: p.localization_group for p in frappe.get_all(PROFESSION, fields=["name", "localization_group"])}
	by_group = {}
	for e in emps:
		g = groups.get(des.get(e.designation))
		if g:
			by_group.setdefault(g, []).append(e)
	wage_map = wages([e.name for e in emps if groups.get(des.get(e.designation))], get_first_day(day), get_last_day(day)) if by_group else {}
	out = []
	for g in sorted({r.localization_group for r in _rules()} | set(by_group)):
		rows = by_group.get(g, [])
		r, nxt = rule_for(g, day), next_rule(g, day)
		min_wage = flt(r.min_wage) if r else 0
		def counts(e):
			w = wage_map.get(e.name, {})
			return counts_as_saudi(e) and (not min_wage or flt(w.get("basic")) + flt(w.get("housing")) >= min_wage)
		saudi = [e for e in rows if counts_as_saudi(e)]
		counted = [e for e in saudi if counts(e)]
		total = len(rows)
		item = {"group": g, "workers": total, "saudis": len(saudi), "saudis_counted": len(counted),
				"below_wage": [{"name": e.name, "employee_name": e.employee_name} for e in saudi if not counts(e)],
				"percent": round(100 * len(counted) / total, 1) if total else 0, "rule": dict(r) if r else None,
				"next": dict(nxt) if nxt else None, "status": "No rule yet", "needed": 0, "violations": []}
		if not total:
			item["status"] = "No one in these professions" if r else item["status"]
		elif r and r.kind == SAUDIS_ONLY:
			item["violations"] = [{"name": e.name, "employee_name": e.employee_name, "designation": e.designation}
								  for e in rows if not counts_as_saudi(e)]
			item["status"] = "Violation" if item["violations"] else "Compliant"
		elif r:
			applies = total >= cint(r.min_workers)
			item["needed"] = _needed(len(counted), total, r.percent) if applies else 0
			item["status"] = "Not applicable" if not applies else ("Compliant" if not item["needed"] else "Below target")
		elif nxt:
			item["status"] = "Starts later"
		if nxt and nxt.kind != SAUDIS_ONLY and total >= cint(nxt.min_workers):
			item["needed_next"] = _needed(len(counted), total, nxt.percent)
		out.append(item)
	return out
