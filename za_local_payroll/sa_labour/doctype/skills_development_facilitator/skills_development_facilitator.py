from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document
from za_local_core.governance import validate_private_evidence

from za_local_payroll.sa_labour.governance import (
	set_preparer,
	validate_company_access,
	validate_date_range,
	validate_independent_review,
)


class SkillsDevelopmentFacilitator(Document):
	def before_insert(self):
		set_preparer(self)

	def validate(self):
		validate_company_access(self.company)
		validate_date_range(self)
		if self.employee and frappe.db.get_value("Employee", self.employee, "company") != self.company:
			frappe.throw(_("The facilitator Employee belongs to a different company."))
		validate_private_evidence(self, "appointment_evidence", required=True)

	def before_submit(self):
		validate_independent_review(self)
