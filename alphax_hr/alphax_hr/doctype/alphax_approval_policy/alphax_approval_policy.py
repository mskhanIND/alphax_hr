import frappe
from frappe import _
from frappe.model.document import Document


class AlphaXApprovalPolicy(Document):
	def validate(self):
		for row in self.levels or []:
			if row.approver_type == "Specific user" and not row.user:
				frappe.throw(_("Level {0}: choose the user who approves.").format(row.idx))
		if self.multi_level and not self.levels:
			frappe.throw(_("Add at least one approval level, or switch off multi-level approval."))
		for f in ("escalate_after_days", "remind_after_days", "reject_after_days"):
			if (self.get(f) or 0) < 0:
				frappe.throw(_("Waiting times cannot be negative."))
		if self.auto_reject and not (self.escalate_after_days or self.reject_after_days):
			frappe.throw(_("Set how many working days to wait before rejecting automatically."))
