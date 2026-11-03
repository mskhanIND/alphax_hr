"""Serves the AlphaX HR single-page app at /alphax (and /alphax/<anything>).

Not /hr: Frappe HRMS already routes /hr/<path> to its Roster screen."""
import json
import os

import frappe
from frappe.sessions import get_csrf_token

import alphax_hr

no_cache = 1
ASSET_URL = "/assets/alphax_hr/frontend/"


def frontend_entry():
	"""Hashed entry file names from the Vite build manifest."""
	path = os.path.join(frappe.get_app_path("alphax_hr"), "public", "frontend", ".vite", "manifest.json")
	try:
		with open(path) as f:
			manifest = json.load(f)
	except FileNotFoundError:
		frappe.throw("AlphaX HR frontend is not built. Run `npm run build` in apps/alphax_hr/frontend.")
	entry = next(v for v in manifest.values() if v.get("isEntry"))
	return ASSET_URL + entry["file"], [ASSET_URL + c for c in entry.get("css", [])]


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login?redirect-to=" + frappe.utils.quote(frappe.request.path)
		raise frappe.Redirect(302)  # not 301: browsers cache permanent redirects

	settings = frappe.get_cached_doc("AlphaX HR Settings")
	from alphax_hr.api.branding import brand

	b = brand()
	lang = frappe.db.get_value("User", frappe.session.user, "language") or settings.default_language or "en"
	boot = {
		"user": frappe.session.user,
		"csrf_token": get_csrf_token(),
		"lang": "ar" if str(lang).startswith("ar") else "en",
		"title": b["title"],
		"version": alphax_hr.__version__,
		"site": frappe.local.site,
	}
	# Escape to keep the inline JSON safe inside <script>.
	context.boot_json = (
		frappe.as_json(boot).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
	)
	context.entry_js, context.entry_css = frontend_entry()
	context.version = alphax_hr.__version__
	context.title = boot["title"]
	context.brand = b
	context.lang = boot["lang"]
	context.no_cache = 1
	return context
