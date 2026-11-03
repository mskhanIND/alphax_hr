"""HR help centre: articles employees can search, with feedback; questions go to HR as "Ask HR" conversations."""
from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import cint

from alphax_hr.api._common import login_required, parse_json, require_hr

FIELDS = ["name", "title", "title_ar", "category", "published", "pinned", "views", "helpful", "not_helpful", "body", "body_ar",
		  "attachment", "modified"]


def _out(r, full=False):
	d = {k: r.get(k) for k in FIELDS if full or k not in ("body", "body_ar")}
	d["modified"] = str(r.modified)
	if not full:
		text = frappe.utils.strip_html(r.body or "")
		d["excerpt"] = text[:180] + ("…" if len(text) > 180 else "")
		d["excerpt_ar"] = frappe.utils.strip_html(r.body_ar or "")[:180]
	return d


@frappe.whitelist()
def articles(search=None, category=None):
	login_required()
	if not frappe.db.exists("DocType", "AlphaX Knowledge Article"):
		return {"articles": [], "categories": []}
	filters = {"published": 1}
	if category:
		filters["category"] = category
	or_filters = None
	if search:
		like = f"%{str(search)[:80]}%"
		or_filters = {"title": ["like", like], "title_ar": ["like", like], "body": ["like", like], "body_ar": ["like", like]}
	rows = frappe.get_all("AlphaX Knowledge Article", filters=filters, or_filters=or_filters, fields=FIELDS,
						  order_by="pinned desc, views desc, modified desc", limit_page_length=100)
	cats = frappe.get_all("AlphaX Knowledge Article", filters={"published": 1}, fields=["category", "count(name) as n"], group_by="category")
	return {"articles": [_out(r) for r in rows], "categories": [{"category": c.category, "count": c.n} for c in cats]}


@frappe.whitelist()
def article(name):
	login_required()
	r = frappe.get_all("AlphaX Knowledge Article", filters={"name": name, "published": 1}, fields=FIELDS)
	if not r:
		frappe.throw(_("This article is not available."), frappe.DoesNotExistError)
	frappe.db.set_value("AlphaX Knowledge Article", name, "views", cint(r[0].views) + 1, update_modified=False)
	return _out(r[0], full=True)


@frappe.whitelist(methods=["POST"])
def feedback(name, helpful):
	login_required()
	field = "helpful" if cint(helpful) else "not_helpful"
	cur = cint(frappe.db.get_value("AlphaX Knowledge Article", name, field))
	frappe.db.set_value("AlphaX Knowledge Article", name, field, cur + 1, update_modified=False)
	return {"ok": True}


@frappe.whitelist()
def all_articles():
	require_hr()
	return [_out(r, full=True) for r in frappe.get_all("AlphaX Knowledge Article", fields=FIELDS, order_by="modified desc")]


@frappe.whitelist(methods=["POST"])
def save(data, name=None):
	require_hr()
	d = parse_json(data, {}) or {}
	doc = frappe.get_doc("AlphaX Knowledge Article", name) if name else frappe.new_doc("AlphaX Knowledge Article")
	for k in ("title", "title_ar", "category", "published", "pinned", "body", "body_ar", "attachment"):
		if k in d:
			doc.set(k, d[k] if d[k] != "" else None)
	doc.save()
	return {"name": doc.name}


@frappe.whitelist(methods=["POST"])
def delete(name):
	require_hr()
	frappe.delete_doc("AlphaX Knowledge Article", name)
	return {"ok": True}


@frappe.whitelist(methods=["POST"])
def restore_standard():
	"""Add back any of the standard Saudi Labor Law articles that are missing (edited ones are kept)."""
	from alphax_hr.api._common import require_hr_manager
	from alphax_hr.saudi.articles import seed

	require_hr_manager()
	return {"added": seed()}
