import frappe
from frappe import _
from frappe.model.document import Document

PROTECTED = ("status", "approver", "decided_by", "decided_on", "hr_note", "letter", "due_on", "legacy_ref")


class AlphaXRequest(Document):
	def validate(self):
		from alphax_hr.api._common import is_hr

		if is_hr() or self.flags.alphax_engine:
			return
		# Employees work through AlphaX's request flow; the REST API cannot be used to approve or re-route.
		own = frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "name")
		if self.employee != own:
			frappe.throw(_("You can only raise requests for yourself."), frappe.PermissionError)
		before = self.get_doc_before_save()
		for f in PROTECTED:
			if (before.get(f) if before else None) != self.get(f) and not (self.is_new() and f in ("status", "approver", "due_on")):
				frappe.throw(_("Only the approval flow can change {0}.").format(_(self.meta.get_label(f))), frappe.PermissionError)
		if self.is_new():
			self.status = "Pending Manager"
