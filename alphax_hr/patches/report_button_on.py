import frappe


def execute():
	"""Switch the Report a problem button on for existing sites (new Check fields start empty on Single doctypes)."""
	if frappe.db.get_single_value("AlphaX HR Settings", "report_button") in (None, ""):
		frappe.db.set_single_value("AlphaX HR Settings", "report_button", 1)
