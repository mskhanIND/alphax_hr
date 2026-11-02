"""Read any HR record inside AlphaX (no Frappe desk): every field the user may see, in the record's own layout."""
from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import cint, strip_html

from alphax_hr.api._common import login_required
from alphax_hr.api.activity import AUDITED

LAYOUT = {"Section Break", "Tab Break", "Column Break"}
SKIP_TYPES = {"HTML", "Button", "Fold", "Heading", "Image", "Geolocation", "Signature", "Barcode"}
SKIP_FIELDS = {"naming_series", "amended_from", "workflow_state", "lft", "rgt", "old_parent"}


def _display(df, value, doc):
	if value in (None, ""):
		return None
	if df.fieldtype == "Check":
		return _("Yes") if cint(value) else _("No")
	if df.fieldtype in ("Text Editor", "HTML Editor", "Markdown Editor"):
		return strip_html(str(value))[:5000]
	if df.fieldtype in ("Link", "Dynamic Link", "Data", "Select", "Small Text", "Text", "Long Text", "Phone", "Attach", "Attach Image"):
		return str(value)
	try:
		return strip_html(frappe.format_value(value, df, doc=doc))
	except Exception:
		return str(value)


def _field(df, doc):
	value = doc.get(df.fieldname)
	out = {"fieldname": df.fieldname, "label": _(df.label or df.fieldname), "fieldtype": df.fieldtype,
		   "value": value if df.fieldtype in ("Link", "Dynamic Link", "Date", "Attach", "Attach Image") else None,
		   "display": _display(df, value, doc)}
	if df.fieldtype == "Link":
		out["link_doctype"] = df.options
	elif df.fieldtype == "Dynamic Link":
		out["link_doctype"] = doc.get(df.options)
	return out


def _table(df, doc):
	child = frappe.get_meta(df.options)
	cols = [c for c in child.fields if c.in_list_view and c.fieldtype not in LAYOUT | SKIP_TYPES] or \
		   [c for c in child.fields if c.fieldtype not in LAYOUT | SKIP_TYPES][:5]
	rows = [[_display(c, r.get(c.fieldname), r) for c in cols] for r in doc.get(df.fieldname) or []]
	return {"fieldname": df.fieldname, "label": _(df.label or df.fieldname), "fieldtype": "Table",
			"columns": [_(c.label or c.fieldname) for c in cols], "rows": rows}


@frappe.whitelist()
def get(doctype, name):
	user = login_required()
	if doctype not in AUDITED or not frappe.db.exists("DocType", doctype):
		frappe.throw(_("This record type cannot be opened here."), frappe.PermissionError)
	doc = frappe.get_doc(doctype, name)
	doc.check_permission("read")
	doc.apply_fieldlevel_read_permissions()
	sections, current = [], {"label": "", "fields": []}
	for df in doc.meta.fields:
		if df.fieldtype in ("Section Break", "Tab Break"):
			if current["fields"]:
				sections.append(current)
			current = {"label": _(df.label) if df.label else "", "fields": []}
			continue
		if df.fieldtype in LAYOUT or df.fieldtype in SKIP_TYPES or df.fieldname in SKIP_FIELDS or cint(df.hidden):
			continue
		if df.fieldtype in ("Table", "Table MultiSelect"):
			t = _table(df, doc)
			if t["rows"]:
				current["fields"].append(t)
			continue
		current["fields"].append(_field(df, doc))
	if current["fields"]:
		sections.append(current)
	from alphax_hr.api import approvals
	from frappe.model.workflow import get_workflow_name

	actions = []
	if doctype in approvals.SOURCES:
		try:
			actions = approvals._actions_for(doc, user, get_workflow_name(doctype))
		except Exception:
			actions = []
	meta = doc.meta
	files = frappe.get_all("File", filters={"attached_to_doctype": doctype, "attached_to_name": name},
						   fields=["file_name", "file_url"], order_by="creation asc")
	return {
		"doctype": doctype, "name": doc.name, "title": doc.get("employee_name") or doc.get("title") or doc.name,
		"employee": doc.get("employee") if meta.has_field("employee") else (doc.name if doctype == "Employee" else None),
		"status": doc.get(meta.get("workflow_state_field") or "workflow_state") or doc.get("status") or doc.get("approval_status")
				  or {0: "Draft", 1: "Submitted", 2: "Cancelled"}[doc.docstatus],
		"docstatus": doc.docstatus, "sections": sections, "actions": actions, "files": files,
		"openable": sorted(AUDITED),
		"desk_url": f"/app/{frappe.scrub(doctype).replace('_', '-')}/{name}" if "System Manager" in frappe.get_roles() else None,
	}
