from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, today
from za_local_core.governance import validate_private_evidence

from za_local_payroll.sa_labour.governance import (
	set_preparer,
	validate_company_access,
	validate_external_filing_evidence,
	validate_governed_link,
	validate_independent_review,
)


class AnnualTrainingReport(Document):
	def before_insert(self):
		set_preparer(self)

	def validate(self):
		validate_company_access(self.company)
		self._validate_governed_references()
		self._calculate_and_validate_spend()
		validate_external_filing_evidence(self)

	def before_submit(self):
		if not self.training_completed:
			frappe.throw(_("At least one completed training intervention is required."))
		validate_independent_review(self)
		self.submission_date = today()

	def on_cancel(self):
		self.db_set("status", "Cancelled", update_modified=False)

	def generate_atr_report(self):
		"""Return an internal working-paper summary; this does not file with a SETA."""
		return {
			"company": self.company,
			"fiscal_year": self.fiscal_year,
			"seta": self.seta,
			"completed_interventions": len(self.training_completed or []),
			"actual_training_spend": flt(self.actual_training_spend),
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
		validate_governed_link("Workplace Skills Plan", self.workplace_skills_plan, company=self.company)
		wsp = frappe.db.get_value(
			"Workplace Skills Plan", self.workplace_skills_plan, ["fiscal_year", "seta"], as_dict=True
		)
		if wsp and (wsp.fiscal_year != self.fiscal_year or wsp.seta != self.seta):
			frappe.throw(_("ATR Fiscal Year and SETA must match the approved Workplace Skills Plan."))
		for row in self.training_completed or []:
			validate_governed_link("OFO Occupation", row.ofo_occupation, require_submitted=False)
			provider = validate_governed_link(
				"Training Provider", row.training_provider, require_submitted=False
			)
			if row.completion_evidence:
				validate_private_evidence(row, "completion_evidence")
			if not row.completion_evidence:
				frappe.throw(_("Each ATR row requires private completion evidence."))
			if not provider:
				frappe.throw(_("Each ATR row requires a governed Training Provider."))

	def _calculate_and_validate_spend(self):
		self.actual_training_spend = sum(flt(row.actual_cost) for row in self.training_completed or [])
		for row in self.training_completed or []:
			if flt(row.number_trained) < 0:
				frappe.throw(_("Number trained cannot be negative."))
			if flt(row.actual_cost) < 0:
				frappe.throw(_("Actual training cost cannot be negative."))
