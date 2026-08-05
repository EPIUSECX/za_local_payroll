from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, today

from za_local_payroll.sa_labour.governance import (
	set_preparer,
	validate_company_access,
	validate_external_filing_evidence,
	validate_governed_link,
	validate_independent_review,
)


class WorkplaceSkillsPlan(Document):
	def before_insert(self):
		set_preparer(self)

	def validate(self):
		validate_company_access(self.company)
		self._validate_governed_references()
		self._calculate_and_validate_budget()
		validate_external_filing_evidence(self)

	def before_submit(self):
		if not self.training_details:
			frappe.throw(_("At least one planned training intervention is required."))
		validate_independent_review(self)
		self.submission_date = today()

	def on_cancel(self):
		self.db_set("status", "Cancelled", update_modified=False)

	def generate_wsp_report(self):
		"""Return an internal working-paper summary; this does not file with a SETA."""
		return {
			"company": self.company,
			"fiscal_year": self.fiscal_year,
			"seta": self.seta,
			"training_interventions": len(self.training_details or []),
			"total_training_budget": flt(self.total_training_budget),
			"filing_mode": "Controlled Manual",
		}

	def _validate_governed_references(self):
		validate_governed_link("Fiscal Year", self.fiscal_year, require_submitted=False)
		validate_governed_link("SETA", self.seta, require_submitted=False)
		if not frappe.get_cached_value("SETA", self.seta, "source_reference"):
			frappe.throw(_("The selected SETA requires a current authority/source reference."))
		validate_governed_link(
			"Skills Development Facilitator", self.skills_development_facilitator, company=self.company
		)
		company_seta = frappe.get_cached_value("Company", self.company, "za_seta")
		if company_seta and company_seta != self.seta:
			frappe.throw(_("The WSP SETA must match the governed SETA on Company."))
		for row in self.training_details or []:
			validate_governed_link("OFO Occupation", row.ofo_occupation, require_submitted=False)
			validate_governed_link("Training Provider", row.training_provider, require_submitted=False)

	def _calculate_and_validate_budget(self):
		self.total_training_budget = sum(flt(row.estimated_cost) for row in self.training_details or [])
		for row in self.training_details or []:
			if flt(row.number_of_employees) < 0:
				frappe.throw(_("Number of employees cannot be negative."))
			if flt(row.estimated_cost) < 0:
				frappe.throw(_("Estimated training cost cannot be negative."))
