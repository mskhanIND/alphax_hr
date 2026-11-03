"""App name and logo chosen by HR (white-label): menu, browser tab, phone home screen, sign-in page."""
from __future__ import annotations

import json

import frappe

DEFAULT_NAME = "AlphaX HR"
DEFAULT_LOGO = "/assets/alphax_hr/frontend/logo.svg"
DEFAULT_ICONS = {"192": "/assets/alphax_hr/frontend/icons/icon-192.png", "512": "/assets/alphax_hr/frontend/icons/icon-512.png",
				 "apple": "/assets/alphax_hr/frontend/icons/apple-touch-icon.png"}


def _public(url):
	"""Logos must be readable before sign-in: move a private upload to public files."""
	if not url or not url.startswith("/private/files/"):
		return url
	name = frappe.db.get_value("File", {"file_url": url}, "name")
	if not name:
		return url
	f = frappe.get_doc("File", name)
	f.is_private = 0
	f.flags.ignore_permissions = True
	f.save()
	return f.file_url


def apply(conf):
	changed = {}
	for field in ("app_logo", "app_icon"):
		url = conf.get(field)
		new = _public(url)
		if new != url:
			changed[field] = new
	for field, value in changed.items():
		frappe.db.set_single_value("AlphaX HR Settings", field, value)
		conf.set(field, value)
	if conf.get("brand_login") and frappe.db.exists("DocType", "Website Settings"):
		ws = frappe.get_single("Website Settings")
		values = {"app_name": conf.portal_title or DEFAULT_NAME}
		if conf.get("app_logo"):
			values["app_logo"] = conf.app_logo
		if conf.get("app_icon") or conf.get("app_logo"):
			values["favicon"] = conf.get("app_icon") or conf.app_logo
		for k, v in values.items():
			if ws.meta.has_field(k) and ws.get(k) != v:
				frappe.db.set_single_value("Website Settings", k, v)
		frappe.clear_cache()


def brand():
	conf = frappe.get_cached_doc("AlphaX HR Settings")
	icon = conf.get("app_icon") or conf.get("app_logo")
	return {"title": conf.get("portal_title") or DEFAULT_NAME, "tagline": conf.get("app_tagline") or "",
			"logo": conf.get("app_logo") or DEFAULT_LOGO, "icon": icon or DEFAULT_ICONS["192"],
			"icon_512": icon or DEFAULT_ICONS["512"], "apple_icon": icon or DEFAULT_ICONS["apple"],
			"favicon": icon or DEFAULT_LOGO, "custom": bool(conf.get("app_logo") or conf.get("app_icon"))}


@frappe.whitelist(allow_guest=True)
def manifest():
	"""Web app manifest with the company's own name and icon."""
	b = brand()
	icon_type = "image/svg+xml" if b["icon"].endswith(".svg") else "image/png"
	data = {
		"id": "/alphax/", "name": b["title"], "short_name": b["title"][:24], "description": "Leave, attendance, payslips and HR services",
		"start_url": "/alphax/", "scope": "/alphax", "display": "standalone", "orientation": "portrait",
		"background_color": "#f6f7f4", "theme_color": "#0f5132", "dir": "auto",
		"icons": [{"src": b["icon"], "sizes": "192x192", "type": icon_type, "purpose": "any"},
				  {"src": b["icon_512"], "sizes": "512x512", "type": icon_type, "purpose": "any"},
				  {"src": b["icon_512"] if b["custom"] else "/assets/alphax_hr/frontend/icons/icon-512-maskable.png",
				   "sizes": "512x512", "type": icon_type, "purpose": "maskable"}],
		"shortcuts": [{"name": n, "short_name": n, "url": u, "icons": [{"src": b["icon"], "sizes": "192x192"}]}
					  for n, u in (("Check in", "/alphax/?checkin=1"), ("Apply for leave", "/alphax/me/leave"), ("Services", "/alphax/me/services"))],
	}
	frappe.response.filename = "manifest.webmanifest"
	frappe.response.filecontent = json.dumps(data, ensure_ascii=False)
	frappe.response.type = "binary"
