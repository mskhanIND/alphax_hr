import frappe
from frappe import _
from frappe.model.document import Document


class AlphaXHRSettings(Document):
	def validate(self):
		if self.gosi_wage_cap and self.gosi_wage_cap < (self.gosi_wage_floor or 0):
			frappe.throw(_("The GOSI wage cap cannot be lower than the floor."))
		if self.nitaqat_partial_weight is not None and not 0 <= self.nitaqat_partial_weight <= 1:
			frappe.throw(_("Nitaqat partial weight must be between 0 and 1."))
		seen = set()
		for row in self.component_map:
			key = (row.salary_component, row.purpose)
			if key in seen:
				frappe.throw(_("Row {0}: {1} is already mapped to {2}.").format(row.idx, *key))
			seen.add(key)

	def components(self, purpose):
		return [r.salary_component for r in self.component_map if r.purpose == purpose]

	def on_update(self):
		from alphax_hr.api.branding import apply
		from alphax_hr.portal import sync_default_app

		apply(self)
		sync_default_app(self)
