"""Scheduled jobs."""
import frappe
from frappe.utils import add_days, nowdate


def notify_expiring_documents():
	"""Daily: one in-app notification per HR Manager listing documents expiring soon."""
	if not frappe.db.exists("DocType", "AlphaX HR Settings"):
		return
	conf = frappe.get_cached_doc("AlphaX HR Settings")
	days = conf.document_alert_days or 60
	horizon = add_days(nowdate(), days)
	fields = [f for f in ("alphax_iqama_expiry", "alphax_work_permit_expiry") if frappe.get_meta("Employee").has_field(f)]
	if not fields:
		return
	count = 0
	for field in fields:
		count += frappe.db.count("Employee", {"status": "Active", field: ["between", [nowdate(), horizon]]})
	if not count:
		return
	managers = frappe.get_all("Has Role", filters={"role": "HR Manager", "parenttype": "User"}, pluck="parent")
	for user in set(managers):
		if user in ("Administrator", "Guest") or not frappe.db.get_value("User", user, "enabled"):
			continue
		frappe.get_doc({
			"doctype": "Notification Log",
			"for_user": user,
			"type": "Alert",
			"subject": f"AlphaX HR: {count} employee document(s) expire within {days} days",
			"email_content": "Open AlphaX HR → Compliance to review.",
		}).insert(ignore_permissions=True)
