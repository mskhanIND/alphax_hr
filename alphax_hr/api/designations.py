"""Designations page: standardize designations to professions, merge duplicates, Saudization by profession."""
from __future__ import annotations

from collections import Counter

import frappe
from frappe import _
from frappe.utils import flt

from alphax_hr import saudization as sz
from alphax_hr.api._common import parse_json, require_hr, require_hr_manager, settings

RULE_FIELDS = ["rule_name", "localization_group", "enabled", "kind", "percent", "effective_from", "min_workers", "min_wage",
			   "activity", "source", "last_reviewed", "notes"]
PROF_FIELDS = ["profession_name", "title_ar", "code", "localization_group", "aliases"]


def _designations():
	meta = frappe.get_meta("Employee")
	fields = ["designation"] + [f for f in ("alphax_is_saudi", "alphax_counts_as_saudi") if meta.has_field(f)]
	total, saudi = Counter(), Counter()
	for e in frappe.get_all("Employee", filters={"status": "Active", "designation": ["is", "set"]}, fields=fields):
		total[e.designation] += 1
		saudi[e.designation] += 1 if sz.counts_as_saudi(e) else 0
	groups = {p.name: p.localization_group for p in frappe.get_all(sz.PROFESSION, fields=["name", "localization_group"])}
	cat = sz._catalogue()
	rows = []
	for d in frappe.get_all("Designation", fields=["name", "alphax_profession"], order_by="name asc"):
		group = groups.get(d.alphax_profession)
		r = sz.rule_for(group) if group else None
		row = {"name": d.name, "employees": total[d.name], "saudis": saudi[d.name], "non_saudis": total[d.name] - saudi[d.name],
			   "profession": d.alphax_profession, "group": group, "saudis_only": bool(r and r.kind == sz.SAUDIS_ONLY)}
		row["violation"] = row["saudis_only"] and row["non_saudis"] > 0
		if not d.alphax_profession:
			row["suggestion"], row["score"] = sz.suggest(d.name, cat)
		rows.append(row)
	return rows


@frappe.whitelist()
def overview():
	require_hr()
	rows = _designations()
	conf = settings()
	return {"designations": rows, "report": sz.report(conf.default_company),
			"rules": [{k: r.get(k) for k in ["name", *RULE_FIELDS]} for r in frappe.get_all(sz.RULE, fields=["name", *RULE_FIELDS],
																							  order_by="localization_group asc, effective_from asc")],
			"professions": frappe.get_all(sz.PROFESSION, fields=["name", *PROF_FIELDS], order_by="localization_group asc, profession_name asc"),
			"groups": sorted({r.localization_group for r in frappe.get_all(sz.RULE, fields=["localization_group"])}),
			"counts": {"total": len(rows), "mapped": sum(1 for r in rows if r["profession"]),
					   "suggested": sum(1 for r in rows if not r["profession"] and r.get("suggestion")),
					   "violations": sum(1 for r in rows if r["violation"])},
			"control": conf.get("saudi_only_control") or "Block",
			"can_edit": bool(set(frappe.get_roles()) & {"HR Manager", "System Manager"})}


@frappe.whitelist(methods=["POST"])
def map_designations(mapping: str | dict):
	"""{designation: profession or ""} — set or clear the standard profession."""
	require_hr_manager()
	for des, prof in (parse_json(mapping) or {}).items():
		if not frappe.db.exists("Designation", des):
			continue
		if prof and not frappe.db.exists(sz.PROFESSION, prof):
			frappe.throw(_("Unknown profession: {0}").format(prof))
		doc = frappe.get_doc("Designation", des)
		doc.alphax_profession = prof or None
		doc.alphax_localization = frappe.db.get_value(sz.PROFESSION, prof, "localization_group") if prof else None
		doc.save()
	return overview()


@frappe.whitelist(methods=["POST"])
def merge(sources: str | list, target: str):
	"""Merge duplicate designations into one: every employee and record pointing to them moves to the target."""
	require_hr_manager()
	sources = [s for s in (parse_json(sources) or []) if s and s != target]
	if not frappe.db.exists("Designation", target):
		frappe.throw(_("Designation {0} not found.").format(target))
	if not sources:
		frappe.throw(_("Choose the designations to merge into {0}.").format(target))
	for s in sources:
		if frappe.db.exists("Designation", s):
			frappe.rename_doc("Designation", s, target, merge=True, force=True)
	return overview()


@frappe.whitelist(methods=["POST"])
def rename(name: str, new_name: str):
	"""Rename a designation to its standard title (all records follow)."""
	require_hr_manager()
	new_name = (new_name or "").strip()
	if not new_name or new_name == name:
		frappe.throw(_("Enter the new name."))
	if frappe.db.exists("Designation", new_name):
		frappe.throw(_("{0} already exists: merge into it instead.").format(new_name))
	frappe.rename_doc("Designation", name, new_name, force=True)
	return overview()


@frappe.whitelist(methods=["POST"])
def create_from_profession(profession: str):
	"""A designation named exactly like the standard profession, already mapped."""
	require_hr_manager()
	if frappe.db.exists("Designation", profession):
		frappe.db.set_value("Designation", profession, "alphax_profession", profession)
	else:
		frappe.get_doc({"doctype": "Designation", "designation_name": profession, "alphax_profession": profession}).insert()
	return overview()


@frappe.whitelist(methods=["POST"])
def save_rule(data: str | dict, name: str | None = None):
	require_hr_manager()
	d = parse_json(data) or {}
	doc = frappe.get_doc(sz.RULE, name) if name else frappe.new_doc(sz.RULE)
	for k in RULE_FIELDS:
		if k in d:
			doc.set(k, d[k] if d[k] != "" else None)
	if doc.kind == sz.SAUDIS_ONLY:
		doc.percent = 100
	elif not 0 < flt(doc.percent) < 100:
		frappe.throw(_("Enter the minimum Saudi % (between 1 and 99)."))
	doc.save() if name else doc.insert()
	frappe.local.alphax_loc_rules = None
	return overview()


@frappe.whitelist(methods=["POST"])
def save_profession(data: str | dict, name: str | None = None):
	require_hr_manager()
	d = parse_json(data) or {}
	doc = frappe.get_doc(sz.PROFESSION, name) if name else frappe.new_doc(sz.PROFESSION)
	for k in PROF_FIELDS:
		if k in d:
			doc.set(k, d[k] if d[k] != "" else None)
	doc.save() if name else doc.insert()
	return overview()


@frappe.whitelist(methods=["POST"])
def delete_profession(name: str):
	require_hr_manager()
	used = frappe.get_all("Designation", filters={"alphax_profession": name}, pluck="name")
	if used:
		frappe.throw(_("{0} is used by: {1}. Map those designations to another profession first.").format(name, ", ".join(used[:10])))
	frappe.delete_doc(sz.PROFESSION, name)
	return overview()


@frappe.whitelist(methods=["POST"])
def save_control(mode: str):
	require_hr_manager()
	if mode not in ("Block", "Warn", "Off"):
		frappe.throw(_("Choose Block, Warn or Off."))
	frappe.db.set_single_value("AlphaX HR Settings", "saudi_only_control", mode)
	return overview()
