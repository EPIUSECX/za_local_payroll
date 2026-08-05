from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document
from za_local_core.governance import validate_private_evidence

from za_local_payroll.sa_labour.governance import validate_date_range


class OFOOccupation(Document):
	def validate(self):
		validate_date_range(self)
		if not self.source_reference:
			frappe.throw(_("OFO Source Reference is required."))
		if self.source_evidence:
			validate_private_evidence(self, "source_evidence")
