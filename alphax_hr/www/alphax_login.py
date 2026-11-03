"""AlphaX sign-in and landing page (company name and logo from AlphaX HR Settings)."""
import frappe

no_cache = 1


def get_context(context):
	from alphax_hr.api.branding import brand
	from alphax_hr.portal import landing_path

	target = frappe.form_dict.get("redirect-to") or ""
	if not target.startswith("/") or target.startswith("//"):
		target = ""  # only same-site paths
	if frappe.session.user != "Guest":
		frappe.local.flags.redirect_location = target or landing_path()
		raise frappe.Redirect(302)
	conf = frappe.get_cached_doc("AlphaX HR Settings")
	b = brand()
	context.brand = b
	context.title = b["title"]
	context.redirect_to = target
	context.welcome = conf.get("login_welcome") or ""
	context.welcome_ar = conf.get("login_welcome_ar") or ""
	context.lang = "ar" if (frappe.local.lang or "").startswith("ar") or conf.get("default_language") == "ar" else "en"
	context.no_cache = 1
	return context
