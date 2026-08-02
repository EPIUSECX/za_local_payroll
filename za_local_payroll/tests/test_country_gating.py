"""South African payroll rules must not reach companies in other countries.

A single Frappe site can hold companies in several countries. Installing this
app must never change payroll behaviour for a company outside South Africa, and
must never block it on South African statutory setup it can never complete.
"""

import frappe
from frappe.tests.classes import IntegrationTestCase, UnitTestCase
from za_local_core.localisation import is_south_african_company
from za_local_core.tests.utils import ensure_company

from za_local_payroll.overrides.payroll_entry import ZAPayrollEntry
from za_local_payroll.overrides.salary_slip import ZASalarySlip
from za_local_payroll.setup.statutory import get_missing_current_tax_configuration


class TestCountryHelperSemantics(UnitTestCase):
	def test_blank_company_is_not_south_african(self):
		"""An unsaved document must not be judged by localisation rules."""
		self.assertFalse(is_south_african_company(None))
		self.assertFalse(is_south_african_company(""))

	def test_unknown_company_is_not_south_african(self):
		self.assertFalse(is_south_african_company("_ZA Company That Does Not Exist"))


class TestPayrollCountryGating(IntegrationTestCase):
	"""Exercise the real controllers against a company outside South Africa."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.suffix = frappe.generate_hash(length=5).upper()
		cls.foreign_company = f"_ZA Gating Foreign {cls.suffix}"
		cls.sa_company = f"_ZA Gating Local {cls.suffix}"
		ensure_company(cls.foreign_company, f"F{cls.suffix[:4]}", "Namibia", "NAD")
		ensure_company(cls.sa_company, f"L{cls.suffix[:4]}", "South Africa", "ZAR")

	def test_helper_distinguishes_the_two_companies(self):
		self.assertFalse(is_south_african_company(self.foreign_company))
		self.assertTrue(is_south_african_company(self.sa_company))

	def test_foreign_company_reports_no_south_african_setup_gaps(self):
		"""The setup gate must be silent for a company it can never apply to."""
		self.assertEqual([], get_missing_current_tax_configuration(self.foreign_company, "2026-08-31"))

	def test_south_african_company_is_configured_on_insert(self):
		"""configure_new_south_african_company seeds the shipped statutory years."""
		self.assertEqual([], get_missing_current_tax_configuration(self.sa_company, "2026-08-31"))

	def test_gate_still_blocks_south_african_payroll_beyond_shipped_years(self):
		"""The gate must keep protecting South African payroll, and only it.

		A date past the shipped rate packs has no statutory masters for either
		company. Only the South African company may be blocked.
		"""
		unshipped_date = "2030-08-31"
		self.assertTrue(
			get_missing_current_tax_configuration(self.sa_company, unshipped_date),
			"An unconfigured South African payroll period must still be blocked",
		)
		self.assertEqual(
			[],
			get_missing_current_tax_configuration(self.foreign_company, unshipped_date),
			"A company outside South Africa must never be blocked by this app",
		)

	def test_salary_slip_validate_does_not_raise_for_foreign_company(self):
		"""Stock HRMS validation must run without South African statutory errors."""
		slip = frappe.new_doc("Salary Slip")
		slip.company = self.foreign_company
		slip.end_date = "2026-08-31"
		self.assertFalse(ZASalarySlip.za_localisation_applies.fget(slip))

	def test_salary_slip_applies_localisation_for_south_african_company(self):
		slip = frappe.new_doc("Salary Slip")
		slip.company = self.sa_company
		slip.end_date = "2026-08-31"
		self.assertTrue(ZASalarySlip.za_localisation_applies.fget(slip))

	def test_payroll_entry_gate_follows_company_country(self):
		entry = frappe.new_doc("Payroll Entry")
		entry.company = self.foreign_company
		self.assertFalse(ZAPayrollEntry.za_localisation_applies.fget(entry))
		entry.company = self.sa_company
		self.assertTrue(ZAPayrollEntry.za_localisation_applies.fget(entry))

	def test_blank_company_document_does_not_claim_localisation(self):
		"""A document with no company must defer to HRMS mandatory-field validation.

		``frappe.new_doc`` applies the session default company, so the blank
		case is asserted explicitly rather than relying on a fresh document.
		"""
		slip = frappe.new_doc("Salary Slip")
		slip.company = None
		self.assertFalse(ZASalarySlip.za_localisation_applies.fget(slip))
