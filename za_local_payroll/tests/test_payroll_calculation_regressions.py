from types import SimpleNamespace
from unittest.mock import Mock, patch

import frappe
from frappe.tests.classes import UnitTestCase

from za_local_payroll.overrides.salary_slip import SalarySlip, ZASalarySlip


class TestSalarySlipTaxRegressions(UnitTestCase):
	@patch("za_local_payroll.overrides.salary_slip.calculate_uif_contribution", return_value=(100, 100))
	@patch("za_local_payroll.overrides.salary_slip.get_salary_component_data")
	def test_employee_uif_row_is_materialized_when_hrms_removed_it(self, get_component_data, _calculate_uif):
		get_component_data.return_value = frappe._dict(
			salary_component="UIF Employee Contribution",
			abbr="UIF_EE",
		)
		deductions = []

		class Slip:
			end_date = "2026-08-31"

			def get(self, fieldname, default=None):
				return deductions if fieldname == "deductions" else default

			def get_statutory_earning_basis(self, _fieldname):
				return 10_000

			def get_configured_statutory_component(self, *_args):
				return "UIF Employee Contribution"

			def is_component_in_codes(self, component, _codes):
				return component == "UIF Employee Contribution"

			def update_component_row(self, component_data, amount, _component_type, **_kwargs):
				deductions.append(
					frappe._dict(
						salary_component=component_data.salary_component,
						amount=amount,
					)
				)

			recalculate_totals_after_statutory_adjustment = Mock()

		slip = Slip()
		ZASalarySlip.apply_statutory_deduction_amounts(slip)

		self.assertEqual(len(deductions), 1)
		self.assertEqual(deductions[0].amount, 100)
		self.assertEqual(deductions[0].default_amount, 100)
		slip.recalculate_totals_after_statutory_adjustment.assert_called_once_with()

	@patch("za_local_payroll.overrides.salary_slip.get_sdl_rate", return_value=0.01)
	@patch("za_local_payroll.overrides.salary_slip.calculate_uif_contribution", return_value=(100, 100))
	def test_employer_uif_and_sdl_rows_are_materialized(self, _calculate_uif, _get_sdl_rate):
		contributions = []

		class Slip:
			end_date = "2026-08-31"

			def get(self, fieldname, default=None):
				return contributions if fieldname == "company_contribution" else default

			def get_statutory_earning_basis(self, _fieldname):
				return 10_000

			def get_configured_statutory_component(self, settings_field, *_args):
				return {
					"za_uif_employer_salary_component": "UIF Employer Contribution",
					"za_sdl_salary_component": "SDL Contribution",
				}[settings_field]

			def is_component_in_codes(self, component, codes):
				return (component == "UIF Employer Contribution" and "4141" in codes) or (
					component == "SDL Contribution" and "4142" in codes
				)

			def append(self, _fieldname, values):
				row = frappe._dict(values)
				contributions.append(row)
				return row

		slip = Slip()
		ZASalarySlip.apply_statutory_company_contribution_amounts(slip)

		self.assertEqual(
			[(row.salary_component, row.amount) for row in contributions],
			[("UIF Employer Contribution", 100), ("SDL Contribution", 100)],
		)

	@patch.object(ZASalarySlip, "za_localisation_applies", True)
	@patch("za_local_payroll.overrides.salary_slip.submit_eti_log")
	@patch.object(SalarySlip, "on_submit")
	def test_submit_delegates_loan_lifecycle_only_to_hrms(self, parent_submit, submit_eti):
		slip = object.__new__(ZASalarySlip)
		slip.employee = "EMP-0001"
		ZASalarySlip.on_submit(slip)
		parent_submit.assert_called_once_with()
		submit_eti.assert_called_once_with("EMP-0001", slip)

	@patch.object(ZASalarySlip, "za_localisation_applies", True)
	@patch("za_local_payroll.overrides.salary_slip.cancel_eti_log")
	@patch.object(SalarySlip, "on_cancel")
	def test_cancel_delegates_loan_lifecycle_only_to_hrms(self, parent_cancel, cancel_eti):
		slip = object.__new__(ZASalarySlip)
		slip.employee = "EMP-0001"
		ZASalarySlip.on_cancel(slip)
		parent_cancel.assert_called_once_with()
		cancel_eti.assert_called_once_with("EMP-0001", slip)

	@patch("za_local_payroll.overrides.salary_slip.is_payroll_processed", return_value=True)
	@patch("za_local_payroll.overrides.salary_slip.get_current_block_period")
	@patch("za_local_payroll.overrides.salary_slip.get_employee_frequency_map")
	def test_duplicate_frequency_period_is_not_swallowed(
		self,
		get_frequency_map,
		get_block_period,
		_is_processed,
	):
		period = frappe._dict(start_date="2026-08-01", end_date="2026-08-31")
		get_frequency_map.return_value = {"EMP-0001": "Monthly"}
		get_block_period.return_value = {"Monthly": period}
		slip = SimpleNamespace(employee="EMP-0001", company="Test Company")

		with self.assertRaises(frappe.ValidationError):
			ZASalarySlip.validate_payroll_frequency(slip)

	@patch("za_local_payroll.overrides.salary_slip.is_payroll_processed")
	@patch("za_local_payroll.overrides.salary_slip.get_current_block_period", return_value={})
	@patch(
		"za_local_payroll.overrides.salary_slip.get_employee_frequency_map",
		return_value={"EMP-0001": "Monthly"},
	)
	def test_missing_frequency_period_fails_closed(
		self,
		_get_frequency_map,
		_get_block_period,
		is_processed,
	):
		with self.assertRaises(frappe.ValidationError):
			ZASalarySlip.validate_payroll_frequency(SimpleNamespace(employee="EMP-0001"))
		is_processed.assert_not_called()

	def test_full_tax_additional_earning_survives_rebate_adjustment(self):
		slip = SimpleNamespace(
			za_localisation_applies=True,
			payroll_period=frappe._dict(name="2026-2027"),
			remaining_sub_periods=9,
			_component_based_variable_tax={
				"PAYE": {
					"total_structured_tax_amount": 12_000,
					"previous_total_paid_taxes": 1_000,
					"full_tax_on_additional_earnings": 500,
				}
			},
		)
		slip.calculate_variable_tax = Mock()
		slip.get_tax_rebates = Mock(return_value=2_000)
		slip.get_medical_aid_credits = Mock(return_value=1_000)

		ZASalarySlip.calculate_variable_based_on_taxable_salary(slip, "PAYE")

		self.assertAlmostEqual(slip.current_structured_tax_amount, 888.8888889)
		self.assertAlmostEqual(slip.current_tax_amount, 1_388.8888889)
		self.assertEqual(
			slip._component_based_variable_tax["PAYE"]["full_tax_on_additional_earnings"],
			500,
		)

	def test_rebate_adjustment_handles_zero_remaining_periods(self):
		slip = SimpleNamespace(
			za_localisation_applies=True,
			payroll_period=frappe._dict(name="2026-2027"),
			remaining_sub_periods=0,
			_component_based_variable_tax={
				"PAYE": {
					"total_structured_tax_amount": 12_000,
					"previous_total_paid_taxes": 1_000,
					"full_tax_on_additional_earnings": 500,
				}
			},
		)
		slip.calculate_variable_tax = Mock()
		slip.get_tax_rebates = Mock(return_value=2_000)
		slip.get_medical_aid_credits = Mock(return_value=1_000)

		ZASalarySlip.calculate_variable_based_on_taxable_salary(slip, "PAYE")

		self.assertEqual(slip.current_structured_tax_amount, 0)
		self.assertEqual(slip.current_tax_amount, 500)

	@patch(
		"hrms.payroll.doctype.salary_slip.salary_slip.calculate_tax_by_tax_slab",
		return_value=(12_000, None),
	)
	def test_variable_tax_handles_zero_remaining_periods(self, _calculate_tax):
		slip = SimpleNamespace(
			za_localisation_applies=True,
			payroll_period=frappe._dict(start_date="2026-03-01"),
			start_date="2027-02-01",
			remaining_sub_periods=0,
			total_taxable_earnings_without_full_tax_addl_components=100_000,
			total_taxable_earnings=100_000,
			tax_slab=frappe._dict(),
			whitelisted_globals={},
			current_additional_earnings_with_full_tax=0,
			_component_based_variable_tax={"PAYE": {}},
		)
		slip.get_tax_paid_in_period = Mock(return_value=5_000)
		slip.get_data_for_eval = Mock(return_value=({}, {}))

		ZASalarySlip.calculate_variable_tax(slip, "PAYE")

		self.assertEqual(slip.current_structured_tax_amount, 0)
		self.assertEqual(slip.current_tax_amount, 0)

	def test_statutory_recalculation_delegates_to_hrms_net_pay(self):
		slip = SimpleNamespace(set_net_pay=Mock())

		ZASalarySlip.recalculate_totals_after_statutory_adjustment(slip)

		slip.set_net_pay.assert_called_once_with()

	def test_component_matching_requires_exact_sars_code(self):
		slip = SimpleNamespace()
		slip.get_sa_component_metadata = Mock(return_value=frappe._dict(za_sars_payroll_code="9999"))
		slip.get_required_sars_code = lambda component, metadata=None: ZASalarySlip.get_required_sars_code(
			slip, component, metadata
		)

		self.assertFalse(ZASalarySlip.is_component_in_codes(slip, "UIF-looking Component", {"4141"}))

		slip.get_sa_component_metadata.return_value = frappe._dict()
		with self.assertRaises(frappe.ValidationError):
			ZASalarySlip.is_component_in_codes(slip, "UIF-looking Component", {"4141"})

	def test_applicability_flag_is_authoritative_without_treatment(self):
		earnings = [
			frappe._dict(
				salary_component="Excluded Commission",
				amount=1_000,
				is_tax_applicable=1,
			),
			frappe._dict(
				salary_component="Included Non-Taxable Earning",
				amount=2_000,
				is_tax_applicable=0,
			),
		]
		metadata = {
			"Excluded Commission": frappe._dict(
				za_sars_payroll_code="3606", za_payroll_treatment=None, za_uif_applicable=0
			),
			"Included Non-Taxable Earning": frappe._dict(
				za_sars_payroll_code="3601", za_payroll_treatment=None, za_uif_applicable=1
			),
		}
		slip = SimpleNamespace()
		slip.get = lambda field: earnings if field == "earnings" else []
		slip.get_sa_component_metadata = lambda component: metadata[component]
		slip.get_required_sars_code = lambda component, values=None: ZASalarySlip.get_required_sars_code(
			slip, component, values
		)

		basis = ZASalarySlip.get_statutory_earning_basis(slip, "za_uif_applicable")

		self.assertEqual(basis, 2_000)

	@patch.object(ZASalarySlip, "za_localisation_applies", True)
	@patch.object(SalarySlip, "add_tax_components")
	def test_classification_runs_after_deductions_exist_and_before_tax(self, parent_add_tax):
		events = []
		slip = object.__new__(ZASalarySlip)
		slip.apply_sa_component_classification_defaults = lambda: events.append("classify")
		parent_add_tax.side_effect = lambda: events.append("tax")

		ZASalarySlip.add_tax_components(slip)

		self.assertEqual(events, ["classify", "tax"])


class TestSalarySlipBenefitsAndEti(UnitTestCase):
	@patch("za_local_payroll.overrides.salary_slip.get_medical_aid_credit")
	@patch.object(frappe, "get_all")
	def test_medical_credit_uses_active_paid_membership_dates(self, get_all, get_credit):
		get_all.return_value = [
			frappe._dict(
				private_medical_aid=0,
				medical_aid_dependant=0,
				effective_from="2025-03-01",
				to=None,
			),
			frappe._dict(
				private_medical_aid=2_500,
				medical_aid_dependant=2,
				effective_from="2026-09-01",
				to="2027-01-31",
			),
		]
		get_credit.return_value = 4_000
		slip = SimpleNamespace(
			employee="EMP-1",
			start_date="2026-09-01",
			end_date="2026-09-30",
		)
		# No employer contribution on this slip, so the unpaid membership row stays
		# skipped and the paid one is used.
		slip.get = lambda field: []
		slip.get_sa_component_metadata = lambda component: frappe._dict()
		slip.has_employer_medical_aid_contribution = lambda: (
			ZASalarySlip.has_employer_medical_aid_contribution(slip)
		)

		result = ZASalarySlip.get_medical_aid_credits(slip)

		self.assertEqual(result, 4_000)
		get_credit.assert_called_once_with(
			slip,
			2,
			membership_start_date="2026-09-01",
			membership_end_date="2027-01-31",
		)

	@patch("za_local_payroll.overrides.salary_slip.get_medical_aid_credit")
	@patch("za_local_payroll.overrides.salary_slip.frappe.get_all")
	def test_employer_funded_membership_earns_the_credit(self, get_all, get_credit):
		"""A member who pays nothing privately is still entitled under section 6A."""
		get_all.return_value = [
			frappe._dict(private_medical_aid=0, medical_aid_dependant=1, effective_from="2023-03-01", to=None)
		]
		get_credit.return_value = 728
		slip = SimpleNamespace(employee="EMP-1", start_date="2023-03-01", end_date="2023-03-31")
		slip.get = lambda field: (
			[frappe._dict(salary_component="Medical Aid Company Contribution", amount=2_000)]
			if field == "earnings"
			else []
		)
		slip.get_sa_component_metadata = lambda component: frappe._dict(za_payroll_treatment="Medical Aid")
		slip.has_employer_medical_aid_contribution = lambda: (
			ZASalarySlip.has_employer_medical_aid_contribution(slip)
		)

		self.assertEqual(728, ZASalarySlip.get_medical_aid_credits(slip))
		get_credit.assert_called_once_with(
			slip, 1, membership_start_date="2023-03-01", membership_end_date=None
		)

	@patch("za_local_payroll.overrides.salary_slip.frappe.get_cached_value", return_value=0)
	@patch("za_local_payroll.overrides.salary_slip.get_salary_component_data")
	@patch("za_local_payroll.overrides.salary_slip.get_additional_salaries")
	def test_additional_benefit_claim_is_recorded_in_ledger(
		self, get_salaries, get_component_data, _get_remove_if_zero
	):
		get_salaries.return_value = [
			frappe._dict(
				name="AS-1",
				component="Flexible Benefit",
				amount=750,
				is_recurring=0,
				ref_doctype="Employee Benefit Claim",
				ref_docname="EBC-1",
			)
		]
		get_component_data.return_value = frappe._dict(
			is_flexible_benefit=1,
			accrual_component=0,
		)
		slip = SimpleNamespace(
			employee="EMP-1",
			start_date="2026-03-01",
			end_date="2026-03-31",
			benefit_ledger_components=[],
			update_component_row=Mock(),
		)

		ZASalarySlip.add_additional_salary_components(slip, "earnings")

		self.assertEqual(len(slip.benefit_ledger_components), 1)
		self.assertEqual(
			slip.benefit_ledger_components[0]["remarks"],
			"Payout against Employee Benefit Claim EBC-1",
		)

	@patch("za_local_payroll.overrides.salary_slip.log_eti_calculation")
	@patch("za_local_payroll.overrides.salary_slip.calculate_eti_amount")
	@patch("za_local_payroll.overrides.salary_slip.check_eti_eligibility")
	def test_apply_eti_reuses_single_eligibility_result_without_logging_unsaved_slip(
		self, check_eligibility, calculate, log
	):
		eligibility = {
			"eligible": True,
			"months_employed": 4,
			"hours_per_month": 160,
		}
		check_eligibility.return_value = eligibility
		calculate.return_value = 1_500
		slip = SimpleNamespace(
			employee="EMP-1",
			gross_pay=5_000,
			is_new=Mock(return_value=True),
			get_statutory_earning_basis=Mock(return_value=5_000),
		)

		ZASalarySlip.apply_eti(slip)

		check_eligibility.assert_called_once_with("EMP-1", slip, 5_000)
		calculate.assert_called_once_with("EMP-1", slip, 5_000, eligibility=eligibility)
		log.assert_not_called()


class TestStatutoryLeviableAmount(UnitTestCase):
	"""SDL and UIF are levied on remuneration, which includes fringe benefits."""

	def _slip(self, earnings, metadata):
		slip = SimpleNamespace()
		slip.get = lambda field: earnings if field == "earnings" else []
		slip.get_sa_component_metadata = lambda component: metadata[component]
		slip.get_required_sars_code = lambda component, values=None: ZASalarySlip.get_required_sars_code(
			slip, component, values
		)
		return slip

	def test_fringe_benefit_kept_out_of_gross_is_still_leviable(self):
		"""``do_not_include_in_total`` must not silently override the SDL flag.

		A taxable benefit is excluded from gross and net pay but is remuneration
		under paragraph 1 of the Fourth Schedule, so the levy applies to it.
		"""
		earnings = [
			frappe._dict(salary_component="Basic", amount=10_000, do_not_include_in_total=0),
			frappe._dict(
				salary_component="Medical Aid Company Contribution",
				amount=2_000,
				do_not_include_in_total=1,
			),
		]
		metadata = {
			"Basic": frappe._dict(
				za_sars_payroll_code="3601", za_payroll_treatment=None, za_sdl_applicable=1
			),
			"Medical Aid Company Contribution": frappe._dict(
				za_sars_payroll_code="4474", za_payroll_treatment="Medical Aid", za_sdl_applicable=1
			),
		}
		basis = ZASalarySlip.get_statutory_earning_basis(self._slip(earnings, metadata), "za_sdl_applicable")
		self.assertEqual(12_000, basis)

	def test_the_flag_still_excludes_what_it_should(self):
		"""An earning-side tax adjustment carries the levy flag off, and is excluded."""
		earnings = [
			frappe._dict(salary_component="Basic", amount=10_000, do_not_include_in_total=0),
			frappe._dict(
				salary_component="Retirement Annuity Private", amount=-3_000, do_not_include_in_total=1
			),
		]
		metadata = {
			"Basic": frappe._dict(
				za_sars_payroll_code="3601", za_payroll_treatment=None, za_sdl_applicable=1
			),
			"Retirement Annuity Private": frappe._dict(
				za_sars_payroll_code="4006", za_payroll_treatment=None, za_sdl_applicable=0
			),
		}
		basis = ZASalarySlip.get_statutory_earning_basis(self._slip(earnings, metadata), "za_sdl_applicable")
		self.assertEqual(10_000, basis)


class TestMedicalTaxCreditEntitlement(UnitTestCase):
	def test_employer_funded_membership_is_recognised(self):
		"""Section 6A does not turn on who pays the medical scheme contribution."""
		slip = object.__new__(ZASalarySlip)
		slip.get = lambda field: (
			[frappe._dict(salary_component="Medical Aid Company Contribution", amount=2_000)]
			if field == "earnings"
			else []
		)
		slip.get_sa_component_metadata = lambda component: frappe._dict(za_payroll_treatment="Medical Aid")
		self.assertTrue(ZASalarySlip.has_employer_medical_aid_contribution(slip))

	def test_no_medical_component_is_not_treated_as_membership(self):
		slip = object.__new__(ZASalarySlip)
		slip.get = lambda field: (
			[frappe._dict(salary_component="Basic", amount=10_000)] if field == "earnings" else []
		)
		slip.get_sa_component_metadata = lambda component: frappe._dict(
			za_payroll_treatment="Regular Remuneration"
		)
		self.assertFalse(ZASalarySlip.has_employer_medical_aid_contribution(slip))
