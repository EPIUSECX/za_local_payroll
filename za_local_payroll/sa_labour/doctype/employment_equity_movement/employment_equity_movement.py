from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document
from za_local_core.governance import validate_private_evidence

from za_local_payroll.sa_labour.governance import validate_company_access


class EmploymentEquityMovement(Document):
	def validate(self):
		validate_company_access(self.company)
		employee_company = frappe.db.get_value("Employee", self.employee, "company")
		if employee_company != self.company:
			frappe.throw(_("Employee belongs to a different company."))
		if self.previous_occupational_level == self.new_occupational_level and self.movement_type in {
			"Promotion",
			"Demotion",
			"Transfer",
		}:
			frappe.throw(_("Record distinct previous and new occupational levels for this movement."))
		if not (self.source_document_type and self.source_document_name) and not self.private_evidence:
			frappe.throw(_("A source document or private movement evidence is required."))
		if self.private_evidence:
			validate_private_evidence(self, "private_evidence")

	def before_submit(self):
		self.check_permission("submit")
