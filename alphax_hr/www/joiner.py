"""New joiner's onboarding form, opened from the private link HR shares (no account needed)."""
import frappe

no_cache = 1


def get_context(context):
	from alphax_hr.api.branding import brand

	b = brand()
	conf = frappe.get_cached_doc("AlphaX HR Settings")
	context.brand = b
	context.title = b["title"]
	context.key = frappe.utils.escape_html(str(frappe.form_dict.get("key") or ""))[:40]
	context.lang = "en" if frappe.form_dict.get("lang") == "en" else ("ar" if conf.get("default_language") == "ar"
																	  or frappe.form_dict.get("lang") == "ar" else "en")
	context.no_cache = 1
	return context
