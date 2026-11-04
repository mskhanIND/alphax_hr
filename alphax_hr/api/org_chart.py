"""Organisation chart exports: PDF (chart, tree or by department), Word (.docx) and Excel/CSV.

The reporting tree comes from Employee.reports_to. Managers outside the filter (inactive, other department) make
their reports top-level, the same way the on-screen chart does.
"""
from __future__ import annotations

import io
import zipfile
from xml.sax.saxutils import escape

import frappe
from frappe import _
from frappe.utils import nowdate

LAYOUTS = ("chart", "tree", "department")
FORMATS = ("pdf", "docx", "xlsx", "csv")


class Tree:
	def __init__(self, rows):
		self.rows = rows
		self.by_id = {r.name: r for r in rows}
		self.children = {}
		for r in rows:
			parent = r.reports_to if r.reports_to in self.by_id and r.reports_to != r.name else None
			self.children.setdefault(parent, []).append(r)
		for kids in self.children.values():
			kids.sort(key=lambda r: (r.employee_name or "").lower())
		self._size = {}
		self.roots = sorted(self.children.get(None, []), key=lambda r: (-self.size(r.name), (r.employee_name or "").lower()))
		# people caught in a reporting loop are never reached from a root: show them at the top
		reached = set()
		for r in self.walk():
			reached.add(r[0].name)
		self.roots += [r for r in rows if r.name not in reached]

	def size(self, name, seen=None):
		if name in self._size:
			return self._size[name]
		seen = seen or set()
		if name in seen:
			return 0
		seen.add(name)
		n = sum(1 + self.size(c.name, seen) for c in self.children.get(name, []))
		self._size[name] = n
		return n

	def kids(self, name):
		return self.children.get(name, [])

	def walk(self, roots=None):
		"""Depth-first (node, level) pairs."""
		seen = set()
		stack = [(r, 1) for r in reversed(roots if roots is not None else self.roots)]
		while stack:
			node, lvl = stack.pop()
			if node.name in seen:
				continue
			seen.add(node.name)
			yield node, lvl
			stack += [(c, lvl + 1) for c in reversed(self.kids(node.name))]


def _rows(company=None, department=None):
	from alphax_hr.api.hr import org_chart

	return org_chart(company, department)["rows"]


def _title(department=None, company=None):
	from alphax_hr.api.branding import brand

	parts = [_("Organisation chart")]
	if department or company:
		parts.append(department or company)
	return " — ".join(parts), brand().get("name") or "AlphaX HR"


def export(department=None, company=None, file_format="pdf", layout="chart"):
	file_format = file_format if file_format in FORMATS else "pdf"
	layout = layout if layout in LAYOUTS else "chart"
	rows = _rows(company, department)
	tree = Tree(rows)
	title, app = _title(department, company)
	stamp = f"org-chart-{layout}-{nowdate()}"
	if file_format == "pdf":
		content, name = pdf(tree, layout, title, app), f"{stamp}.pdf"
	elif file_format == "docx":
		content, name = docx(tree, layout, title, app), f"{stamp}.docx"
	else:
		table = _table(tree)
		if file_format == "csv":
			from frappe.utils.csvutils import to_csv

			content, name = to_csv(table).encode("utf-8-sig"), f"org-chart-{nowdate()}.csv"
		else:
			from frappe.utils.xlsxutils import make_xlsx

			content, name = make_xlsx(table, "Org chart").getvalue(), f"org-chart-{nowdate()}.xlsx"
	frappe.response["filecontent"] = content
	frappe.response["filename"] = name
	frappe.response["type"] = "binary"


def _note(tree, r):
	if not r.reports_to:
		return _("No reporting manager")
	if r.reports_to not in tree.by_id:
		return _("Manager not in this list (inactive or other department)")
	return ""


def _table(tree):
	table = [[_("Employee ID"), _("Employee"), _("Designation"), _("Department"), _("Reports to (ID)"), _("Reports to"),
			  _("Level"), _("Team size"), _("Note")]]
	for r, lvl in tree.walk():
		mgr = tree.by_id.get(r.reports_to)
		table.append([r.name, r.employee_name, r.designation or "", r.department or "", r.reports_to or "",
					  mgr.employee_name if mgr else "", lvl, tree.size(r.name), _note(tree, r)])
	return table


def _departments(tree):
	"""[(department, [(employee, level within the whole tree)])] — managers first inside each department."""
	levels = {r.name: lvl for r, lvl in tree.walk()}
	groups = {}
	for r in tree.rows:
		groups.setdefault(r.department or _("No department"), []).append(r)
	out = []
	for dept in sorted(groups, key=lambda d: d.lower()):
		people = sorted(groups[dept], key=lambda r: (levels.get(r.name, 99), -tree.size(r.name), (r.employee_name or "").lower()))
		out.append((dept, [(r, levels.get(r.name, 1)) for r in people]))
	return out


# ---------------------------------------------------------------- PDF (wkhtmltopdf: tables only, no flex/grid)

CSS = """
body { font-family: 'Noto Sans', 'Noto Sans Arabic', Arial, sans-serif; color: #1f2937; font-size: 10px; }
h1 { font-size: 18px; margin: 0 0 2px; color: #0f5132; } .sub { color: #6b7280; margin-bottom: 14px; }
table.oc { border-collapse: collapse; margin: 0 auto 18px; page-break-inside: auto; }
table.oc td { padding: 0; vertical-align: top; text-align: center; }
.box { display: inline-block; border: 1px solid #0f5132; border-top: 4px solid #0f5132; border-radius: 6px; padding: 6px 9px;
       margin: 0 5px; min-width: 110px; max-width: 170px; background: #fff; }
.box b { display: block; font-size: 12px; } .box i { display: block; font-style: normal; color: #4b5563; font-size: 10px; }
.box s { display: block; text-decoration: none; color: #9ca3af; font-size: 9px; }
tr.line td { height: 1px; font-size: 1px; line-height: 1px; } td.h { border-top: 1px solid #0f5132; }
.loose { font-size: 12px; color: #b45309; margin: 18px 0 6px; text-align: center; }
table.list { width: 100%; border-collapse: collapse; } table.list th { text-align: left; background: #f3f4f6; padding: 5px 6px; font-size: 9px; color: #374151; }
table.list td { border-bottom: 1px solid #e5e7eb; padding: 4px 6px; }
.dept { font-size: 13px; color: #0f5132; margin: 14px 0 6px; padding-bottom: 3px; border-bottom: 2px solid #0f5132; }
.muted { color: #6b7280; } .warn { color: #b45309; }
"""


def _box(tree, r):
	team = tree.size(r.name)
	extra = f"<s>{escape(str(team))} {escape(_('in team'))}</s>" if team else ""
	return (f"<div class='box'><b>{escape(r.employee_name or r.name)}</b><i>{escape(r.designation or '')}</i>"
			f"<s>{escape(r.department or '')}</s>{extra}</div>")


STEM = "<div style='width:1px;height:12px;background:#0f5132;margin:0 auto'></div>"


def _chart_html(tree, node, seen):
	"""Classic top-down chart as nested tables (wkhtmltopdf has no flexbox). Each child gets two half-cells so the
	horizontal connector runs from the first child's centre to the last child's centre."""
	seen.add(node.name)
	kids = [k for k in tree.kids(node.name) if k.name not in seen]
	n = len(kids)
	if not n:
		return f"<table class='oc'><tr><td>{_box(tree, node)}</td></tr></table>"
	cols = n * 2
	html = [f"<table class='oc'><tr><td colspan='{cols}'>{_box(tree, node)}</td></tr>",
			f"<tr><td colspan='{cols}'>{STEM}</td></tr>"]
	if n > 1:
		line = []
		for i in range(n):
			left = "" if i == 0 else "h"
			right = "" if i == n - 1 else "h"
			line.append(f"<td class='{left}'></td><td class='{right}'></td>")
		html.append("<tr class='line'>" + "".join(line) + "</tr>")
		html.append("<tr>" + "".join(f"<td colspan='2'>{STEM}</td>" for _k in kids) + "</tr>")
	html.append("<tr>" + "".join(f"<td colspan='2'>{_chart_html(tree, k, seen)}</td>" for k in kids) + "</tr></table>")
	return "".join(html)


def _loose_grid(tree, people, per_row=6):
	cells = [f"<td style='padding:4px'>{_box(tree, r)}</td>" for r in people]
	rows = ["<tr>" + "".join(cells[i:i + per_row]) + "</tr>" for i in range(0, len(cells), per_row)]
	return f"<table class='oc'>{''.join(rows)}</table>"


def pdf(tree, layout, title, app):
	from frappe.utils.pdf import get_pdf

	body = [f"<h1>{escape(title)}</h1><div class='sub'>{escape(app)} · {escape(frappe.utils.formatdate(nowdate()))} · "
			f"{len(tree.rows)} {escape(_('employees'))}</div>"]
	if not tree.rows:
		body.append(f"<p class='muted'>{escape(_('No employees found'))}</p>")
	elif layout == "chart":
		seen, first = set(), True
		heads = [r for r in tree.roots if tree.kids(r.name)]
		loose = [r for r in tree.roots if not tree.kids(r.name)]
		for root in heads:
			if root.name in seen:
				continue
			if not first:
				body.append("<div style='page-break-before: always'></div>")
			body.append(_chart_html(tree, root, seen))
			first = False
		if loose:
			body.append(f"<div class='loose'>{escape(_('Without a reporting manager'))} ({len(loose)})</div>")
			body.append(_loose_grid(tree, loose))
	elif layout == "tree":
		body.append("<table class='list'><tr>" + "".join(f"<th>{escape(h)}</th>" for h in
					(_("Employee"), _("Designation"), _("Department"), _("Team size"), _("Note"))) + "</tr>")
		for r, lvl in tree.walk():
			indent = (lvl - 1) * 16
			mark = "└ " if lvl > 1 else ""
			body.append(f"<tr><td style='padding-left:{indent + 6}px'>{mark}<b>{escape(r.employee_name or r.name)}</b> "
						f"<span class='muted'>{escape(r.name)}</span></td><td>{escape(r.designation or '')}</td>"
						f"<td>{escape(r.department or '')}</td><td>{tree.size(r.name) or ''}</td>"
						f"<td class='warn'>{escape(_note(tree, r))}</td></tr>")
		body.append("</table>")
	else:
		for dept, people in _departments(tree):
			body.append(f"<div class='dept'>{escape(dept)} <span class='muted'>({len(people)})</span></div>")
			body.append("<table class='list'><tr>" + "".join(f"<th>{escape(h)}</th>" for h in
						(_("Employee"), _("Designation"), _("Reports to"), _("Level"), _("Team size"))) + "</tr>")
			for r, lvl in people:
				mgr = tree.by_id.get(r.reports_to)
				body.append(f"<tr><td><b>{escape(r.employee_name or r.name)}</b> <span class='muted'>{escape(r.name)}</span></td>"
							f"<td>{escape(r.designation or '')}</td><td>{escape(mgr.employee_name if mgr else (r.reports_to or '—'))}</td>"
							f"<td>{lvl}</td><td>{tree.size(r.name) or ''}</td></tr>")
			body.append("</table>")
	html = f"<html><head><meta charset='utf-8'><style>{CSS}</style></head><body>{''.join(body)}</body></html>"
	wide = layout == "chart"
	return get_pdf(html, {"page-size": "A3" if wide else "A4", "orientation": "Landscape" if wide else "Portrait",
						  "margin-top": "10mm", "margin-bottom": "10mm", "margin-left": "8mm", "margin-right": "8mm"})


# ---------------------------------------------------------------- Word (.docx written directly, no extra library)

W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'


def _run(text, bold=False, size=None, color=None):
	props = ("<w:b/>" if bold else "") + (f'<w:color w:val="{color}"/>' if color else "") + \
		(f'<w:sz w:val="{size}"/><w:szCs w:val="{size}"/>' if size else "")
	props = f"<w:rPr><w:rFonts w:ascii='Arial' w:hAnsi='Arial' w:cs='Arial'/>{props}</w:rPr>"
	return f'<w:r>{props}<w:t xml:space="preserve">{escape(str(text))}</w:t></w:r>'


def _para(*runs, indent=0, space_after=60, keep_next=False):
	ppr = f'<w:spacing w:after="{space_after}"/>' + (f'<w:ind w:left="{indent}"/>' if indent else "") + \
		("<w:keepNext/>" if keep_next else "")
	return f"<w:p><w:pPr>{ppr}</w:pPr>{''.join(runs)}</w:p>"


def _cell(text, bold=False, fill=None, width=2000):
	shade = f'<w:shd w:val="clear" w:color="auto" w:fill="{fill}"/>' if fill else ""
	return (f'<w:tc><w:tcPr><w:tcW w:w="{width}" w:type="dxa"/>{shade}</w:tcPr>'
			f"{_para(_run(text, bold=bold, size=18), space_after=0)}</w:tc>")


def _docx_table(head, rows, widths):
	border = "".join(f'<w:{s} w:val="single" w:sz="4" w:space="0" w:color="D1D5DB"/>'
					 for s in ("top", "left", "bottom", "right", "insideH", "insideV"))
	out = [f'<w:tbl><w:tblPr><w:tblW w:w="0" w:type="auto"/><w:tblBorders>{border}</w:tblBorders></w:tblPr>',
		   "<w:tblGrid>" + "".join(f'<w:gridCol w:w="{w}"/>' for w in widths) + "</w:tblGrid>",
		   '<w:tr><w:trPr><w:tblHeader/></w:trPr>' + "".join(_cell(h, True, "E8F0EC", w) for h, w in zip(head, widths)) + "</w:tr>"]
	for row in rows:
		out.append("<w:tr>" + "".join(_cell(v, False, None, w) for v, w in zip(row, widths)) + "</w:tr>")
	out.append("</w:tbl>")
	return "".join(out) + _para(space_after=120)


def docx(tree, layout, title, app):
	body = [_para(_run(title, bold=True, size=36, color="0F5132")),
			_para(_run(f"{app} · {frappe.utils.formatdate(nowdate())} · {len(tree.rows)} {_('employees')}", size=18, color="6B7280"),
				  space_after=240)]
	if layout == "department":
		for dept, people in _departments(tree):
			body.append(_para(_run(f"{dept} ({len(people)})", bold=True, size=26, color="0F5132"), keep_next=True))
			rows = []
			for r, lvl in people:
				mgr = tree.by_id.get(r.reports_to)
				rows.append([r.employee_name or r.name, r.name, r.designation or "",
							 mgr.employee_name if mgr else (r.reports_to or "—"), lvl, tree.size(r.name) or ""])
			body.append(_docx_table([_("Employee"), _("ID"), _("Designation"), _("Reports to"), _("Level"), _("Team size")],
									rows, [2600, 1500, 2200, 2400, 700, 900]))
	else:
		# Chart and tree both become an indented outline in Word: one line per person under their manager.
		for r, lvl in tree.walk():
			team = tree.size(r.name)
			runs = [_run(("└ " if lvl > 1 else "") + (r.employee_name or r.name), bold=lvl == 1 or bool(team), size=21)]
			detail = " · ".join(x for x in (r.designation, r.department) if x)
			if detail:
				runs.append(_run(f"  {detail}", size=18, color="4B5563"))
			if team:
				runs.append(_run(f"  ({team} {_('in team')})", size=16, color="6B7280"))
			note = _note(tree, r)
			if note and lvl == 1 and not team:
				runs.append(_run(f"  — {note}", size=16, color="B45309"))
			body.append(_para(*runs, indent=(lvl - 1) * 440, space_after=40))
	sect = ('<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'
			'<w:pgMar w:top="1000" w:right="900" w:bottom="1000" w:left="900" w:header="500" w:footer="500" w:gutter="0"/></w:sectPr>')
	document = f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document {W}><w:body>{"".join(body)}{sect}</w:body></w:document>'
	content_types = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
					 '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
					 '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
					 '<Default Extension="xml" ContentType="application/xml"/>'
					 '<Override PartName="/word/document.xml" '
					 'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>')
	rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
			'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
			'<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
			'Target="word/document.xml"/></Relationships>')
	buf = io.BytesIO()
	with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
		z.writestr("[Content_Types].xml", content_types)
		z.writestr("_rels/.rels", rels)
		z.writestr("word/document.xml", document)
	return buf.getvalue()
