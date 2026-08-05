from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt, getdate
from za_local_core.governance import validate_private_evidence

from za_local_payroll.sa_labour.governance import (
	set_preparer,
	validate_company_access,
	validate_date_range,
	validate_independent_review,
)


class EmploymentEquityTargetPlan(Document):
	def before_insert(self):
		set_preparer(self)

	def validate(self):
		validate_company_access(self.company)
		validate_date_range(self, "plan_start_date", "plan_end_date")
		self.small_cell_threshold = max(cint(self.small_cell_threshold), 1)
		self._validate_source()
		self._validate_targets()

	def before_submit(self):
		if not self.targets:
			frappe.throw(_("At least one effective Employment Equity target is required."))
		validate_independent_review(self)

	def _validate_source(self):
		if not self.source_basis or not self.source_reference:
			frappe.throw(_("Target Source Basis and Source Reference are required."))
		if self.source_basis in {"Sector Numerical Targets", "EAP Statistics"} and not self.statutory_source:
			frappe.throw(_("A governed ZA Statutory Source is required for the selected target basis."))
		if self.source_evidence:
			validate_private_evidence(self, "source_evidence")
		if self.source_basis == "Sector Numerical Targets":
			if getdate(self.plan_start_date) < getdate("2025-04-15"):
				frappe.throw(_("Sector numerical targets cannot be effective before 15 April 2025."))
			if getdate(self.plan_end_date) > getdate("2030-08-31"):
				frappe.throw(_("The current regulated sector-target period ends on 31 August 2030."))

	def _validate_targets(self):
		seen = set()
		for row in self.targets or []:
			key = (
				str(row.effective_date),
				row.occupational_level,
				row.race,
				row.gender,
				row.disability_status,
			)
			if key in seen:
				frappe.throw(_("Employment Equity target dimensions must be unique per effective date."))
			seen.add(key)
			if row.effective_date and not (self.plan_start_date <= row.effective_date <= self.plan_end_date):
				frappe.throw(_("Target effective dates must fall within the plan period."))
			if flt(row.target_percentage) < 0 or flt(row.target_percentage) > 100:
				frappe.throw(_("Target Percentage must be between 0 and 100."))
			if cint(row.target_headcount) < 0:
				frappe.throw(_("Target Headcount cannot be negative."))
