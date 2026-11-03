from frappe.model.document import Document


class AlphaXLeaveCountingRule(Document):
	def on_update(self):
		from alphax_hr.leave_engine import sync_leave_type_holidays

		sync_leave_type_holidays(self)
