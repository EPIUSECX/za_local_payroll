"""What a practitioner meets between a finished setup wizard and the first pay run."""

import frappe
from frappe.tests.classes import IntegrationTestCase, UnitTestCase

from za_local_payroll.setup.preflight import get_missing_company_payroll_setup


class TestMedicalAidComponentIsShipped(UnitTestCase):
	def test_employer_medical_aid_component_exists(self):
		"""The suite grants a medical tax credit, so it must ship the component.

		Without it a practitioner hand-builds one, and the credit is only granted
		when they happen to set the right treatment.
		"""
		self.assertTrue(frappe.db.exists("Salary Component", "Medical Aid Company Contribution"))

	def test_component_treatment_is_what_the_credit_actually_reads(self):
		"""has_employer_medical_aid_contribution matches on treatment, not on name.

		A component named for medical aid but treated as regular remuneration is
		silently ignored by the credit, so the shipped treatment is the whole point.
		"""
		self.assertEqual(
			"Medical Aid",
			frappe.db.get_value(
				"Salary Component", "Medical Aid Company Contribution", "za_payroll_treatment"
			),
		)

	def test_component_carries_the_employer_sars_code_not_the_deduction_one(self):
		"""4474 is the employer's contribution; 4005 is the employee's deduction."""
		code = frappe.db.get_value(
			"Salary Component", "Medical Aid Company Contribution", "za_sars_payroll_code"
		)
		self.assertEqual("4474", frappe.db.get_value("SARS Payroll Code", code, "code"))

	def test_benefit_stays_out_of_gross_and_off_the_ledger(self):
		"""It is a taxable benefit value, not cash paid to the employee."""
		values = frappe.db.get_value(
			"Salary Component",
			"Medical Aid Company Contribution",
			["do_not_include_in_total", "do_not_include_in_accounts", "is_tax_applicable"],
			as_dict=True,
		)
		self.assertTrue(values.do_not_include_in_total)
		self.assertTrue(values.do_not_include_in_accounts)
		self.assertTrue(values.is_tax_applicable)


class TestCompanyPayrollPreflight(IntegrationTestCase):
	def test_a_company_outside_south_africa_is_never_blocked(self):
		"""Localisation must not be the reason a foreign company cannot run payroll."""
		company = frappe.db.get_value("Company", {"country": ["!=", "South Africa"]}, "name")
		if not company:
			self.skipTest("site has no company outside South Africa")
		self.assertEqual([], get_missing_company_payroll_setup(company))

	def test_an_unknown_company_reports_nothing(self):
		self.assertEqual([], get_missing_company_payroll_setup("No Such Company"))

	def test_an_untyped_payroll_payable_account_is_reported(self):
		"""ERPNext's standard chart ships Payroll Payable with no account type."""
		company = frappe.db.get_value("Company", {"country": "South Africa"}, "name")
		if not company:
			self.skipTest("site has no South African company")
		account = frappe.db.get_value("Company", company, "default_payroll_payable_account")
		if not account:
			self.skipTest("company has no payroll payable account")

		original = frappe.db.get_value("Account", account, "account_type")
		frappe.db.set_value("Account", account, "account_type", "")
		try:
			reported = get_missing_company_payroll_setup(company)
			self.assertTrue(
				any("Payable" in item and account in item for item in reported),
				f"untyped payroll payable account was not reported: {reported}",
			)
		finally:
			frappe.db.set_value("Account", account, "account_type", original)

	def test_a_correctly_typed_account_is_not_reported(self):
		company = frappe.db.get_value("Company", {"country": "South Africa"}, "name")
		if not company:
			self.skipTest("site has no South African company")
		account = frappe.db.get_value("Company", company, "default_payroll_payable_account")
		if not account or frappe.db.get_value("Account", account, "account_type") != "Payable":
			self.skipTest("company payable account is not in the configured state")
		self.assertFalse(
			any(account in item for item in get_missing_company_payroll_setup(company)),
		)


class TestComponentsCreatedWithTheCompany(IntegrationTestCase):
	"""HRMS creates its default components from its own Company on_update hook.

	Install-time seeding runs before any company exists, so those components would
	otherwise carry no SARS payroll code and the engine refuses to calculate.
	"""

	def test_hrms_default_components_are_classified(self):
		company = frappe.db.get_value("Company", {"country": "South Africa"}, "name")
		if not company:
			self.skipTest("site has no South African company")
		for component in ("Basic", "PAYE"):
			if not frappe.db.exists("Salary Component", component):
				continue
			self.assertTrue(
				frappe.db.get_value("Salary Component", component, "za_sars_payroll_code"),
				f"{component} has no SARS payroll code, so payroll cannot be calculated",
			)

	def test_the_company_hook_that_classifies_them_is_registered(self):
		from za_local_payroll import hooks

		self.assertEqual(
			"za_local_payroll.setup.statutory.classify_company_salary_components",
			hooks.doc_events["Company"]["on_update"],
		)


class TestAccountRepairDoesNotWipeAMapping(IntegrationTestCase):
	def test_correcting_a_mapped_account_sets_it_rather_than_clearing_it(self):
		"""frappe.db.set_value takes the value positionally after the fieldname.

		Omitting it silently wrote NULL, so a component already mapped to another
		account lost its mapping and still counted as repaired.
		"""
		from za_local_payroll.setup.masters import repair_salary_component_accounts

		company = frappe.db.get_value("Company", {"country": "South Africa"}, "name")
		if not company:
			self.skipTest("site has no South African company")
		row = frappe.db.get_value(
			"Salary Component Account", {"company": company}, ["name", "account"], as_dict=True
		)
		if not row or not row.account:
			self.skipTest("no mapped salary component account on this site")

		wrong = frappe.db.get_value(
			"Account", {"company": company, "is_group": 0, "name": ["!=", row.account]}, "name"
		)
		if not wrong:
			self.skipTest("company has no second account to mis-map to")

		frappe.db.set_value("Salary Component Account", row.name, "account", wrong)
		try:
			repair_salary_component_accounts(company)
			self.assertIsNotNone(
				frappe.db.get_value("Salary Component Account", row.name, "account"),
				"repair cleared the account instead of correcting it",
			)
		finally:
			frappe.db.set_value("Salary Component Account", row.name, "account", row.account)
