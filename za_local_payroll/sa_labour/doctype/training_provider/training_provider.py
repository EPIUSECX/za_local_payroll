from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document
from za_local_core.governance import validate_private_evidence

from za_local_payroll.sa_labour.governance import validate_date_range


class TrainingProvider(Document):
	def validate(self):
		validate_date_range(self, "accreditation_from", "accreditation_to")
		if self.accredited:
			if not self.accreditation_body or not self.accreditation_number:
				frappe.throw(_("Accreditation Body and Accreditation Number are required."))
			validate_private_evidence(self, "accreditation_evidence", required=True)
