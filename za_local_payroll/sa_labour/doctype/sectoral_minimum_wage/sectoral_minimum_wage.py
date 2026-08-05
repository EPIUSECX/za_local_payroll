from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt
from za_local_core.governance import validate_private_evidence

from za_local_payroll.sa_labour.governance import (
	set_preparer,
	validate_date_range,
	validate_independent_review,
)

RATE_CATEGORIES = {"General NMW", "EPWP", "Sector-specific"}


class SectoralMinimumWage(Document):
	def before_insert(self):
		set_preparer(self)

	def validate(self):
		validate_date_range(self)
		self._validate_category()
		if not self.source_reference:
			frappe.throw(_("Gazette / Source Reference is required."))
		if self.source_evidence:
			validate_private_evidence(self, "source_evidence")
		self.automation_status = "Controlled Manual - No Automatic Employee Assignment"

	def before_submit(self):
		validate_private_evidence(self, "source_evidence", required=True)
		validate_independent_review(self, status_field="governance_status")

	def on_cancel(self):
		self.db_set("governance_status", "Cancelled", update_modified=False)

	def validate_employee_salary(self):
		"""Return a manual-review payload; never auto-assign the general rate."""
		return {
			"worker_category": self.worker_category,
			"sector": self.sector,
			"position_category": self.position_category,
			"hourly_rate": flt(self.hourly_rate),
			"monthly_rate": flt(self.monthly_rate),
			"schedule_reference": self.schedule_reference,
			"automation_status": self.automation_status,
		}

	def _validate_category(self):
		if self.worker_category in RATE_CATEGORIES:
			if flt(self.hourly_rate) <= 0 and flt(self.monthly_rate) <= 0:
				frappe.throw(_("Set an hourly or monthly rate for this exact worker category."))
		elif self.worker_category == "Learnership Schedule 2":
			if not self.schedule_reference:
				frappe.throw(_("Schedule 2 Reference is required for learnership allowances."))
			if flt(self.hourly_rate) or flt(self.monthly_rate):
				frappe.throw(_("Do not reduce Schedule 2 learnership allowances to one general wage rate."))
		elif self.worker_category == "Special or Excluded Category":
			if not self.special_category_reason:
				frappe.throw(_("Record the governed basis for the special or excluded category."))
			if flt(self.hourly_rate) or flt(self.monthly_rate):
				frappe.throw(
					_("Special or excluded categories require a separate governed rule, not a general rate.")
				)
		if flt(self.hourly_rate) < 0 or flt(self.monthly_rate) < 0:
			frappe.throw(_("Minimum wage rates cannot be negative."))
