import frappe
from frappe import _
from frappe.model.document import Document


class GOSIContributionRate(Document):
	def validate(self):
		for field in ("employee_pension", "employer_pension", "employee_saned", "employer_saned", "employer_hazard"):
			value = self.get(field) or 0
			if value < 0 or value > 30:
				frappe.throw(_("{0} must be between 0 and 30%.").format(self.meta.get_label(field)))
		duplicate = frappe.db.exists(
			"GOSI Contribution Rate",
			{"system": self.system, "effective_from": self.effective_from, "name": ["!=", self.name]},
		)
		if duplicate:
			frappe.throw(_("A {0} rate already starts on {1}.").format(self.system, self.effective_from))
