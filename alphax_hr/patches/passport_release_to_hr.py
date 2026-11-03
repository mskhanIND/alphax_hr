import frappe


def execute():
	"""Passport release is between the employee and HR: drop the manager step if HR never changed the type."""
	if not frappe.db.exists("AlphaX Request Type", "Passport Release"):
		return
	t = frappe.db.get_value("AlphaX Request Type", "Passport Release", ["creation", "modified", "needs_manager"], as_dict=True)
	if t.needs_manager and abs((t.modified - t.creation).total_seconds()) < 5:
		frappe.db.set_value("AlphaX Request Type", "Passport Release", "needs_manager", 0, update_modified=False)
