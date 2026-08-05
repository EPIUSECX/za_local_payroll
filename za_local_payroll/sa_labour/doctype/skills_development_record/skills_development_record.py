from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate
from za_local_core.governance import validate_private_evidence

from za_local_payroll.sa_labour.governance import (
	validate_company_access,
	validate_governed_link,
)


class SkillsDevelopmentRecord(Document):
	def validate(self):
		validate_company_access(self.company)
		self._validate_dates_and_amounts()
		self._validate_governed_references()
		self.bec_points = 0
		self.bbbee_scoring_status = "Controlled Manual - Not Calculated"
		if self.completion_evidence:
			validate_private_evidence(self, "completion_evidence")

	def before_submit(self):
		validate_private_evidence(self, "completion_evidence", required=True)

	def _validate_dates_and_amounts(self):
		if self.start_date and self.end_date and getdate(self.end_date) < getdate(self.start_date):
			frappe.throw(_("Training End Date cannot be before Start Date."))
		if flt(self.training_cost) < 0 or flt(self.bursary_amount) < 0:
			frappe.throw(_("Training cost and bursary amount cannot be negative."))

	def _validate_governed_references(self):
		if frappe.db.get_value("Employee", self.employee, "company") != self.company:
			frappe.throw(_("Employee belongs to a different company."))
		validate_governed_link("Fiscal Year", self.fiscal_year, require_submitted=False)
		validate_governed_link("SETA", self.seta, require_submitted=False)
		validate_governed_link("OFO Occupation", self.ofo_occupation, require_submitted=False)
		validate_governed_link("Workplace Skills Plan", self.workplace_skills_plan, company=self.company)
		provider = validate_governed_link(
			"Training Provider", self.training_provider, require_submitted=False
		)
		if self.annual_training_report:
			validate_governed_link(
				"Annual Training Report", self.annual_training_report, company=self.company
			)
		company_seta = frappe.get_cached_value("Company", self.company, "za_seta")
		if company_seta and company_seta != self.seta:
			frappe.throw(_("Skills record SETA must match the governed SETA on Company."))
		wsp = frappe.db.get_value(
			"Workplace Skills Plan", self.workplace_skills_plan, ["fiscal_year", "seta"], as_dict=True
		)
		if wsp and (wsp.fiscal_year != self.fiscal_year or wsp.seta != self.seta):
			frappe.throw(_("Skills record Fiscal Year and SETA must match the approved WSP."))
		if self.provider_accreditation_required:
			provider_details = frappe.db.get_value(
				"Training Provider",
				provider.name,
				["accredited", "accreditation_from", "accreditation_to"],
				as_dict=True,
			)
			if not provider_details or not provider_details.accredited:
				frappe.throw(_("The selected Training Provider is not recorded as accredited."))
			if provider_details.accreditation_from and getdate(self.start_date) < getdate(
				provider_details.accreditation_from
			):
				frappe.throw(_("Training starts before the provider accreditation period."))
			if provider_details.accreditation_to and getdate(self.end_date) > getdate(
				provider_details.accreditation_to
			):
				frappe.throw(_("Training ends after the provider accreditation period."))
