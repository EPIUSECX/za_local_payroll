"""Regressions found by the reference-company end-to-end validation.

Each test reproduces a defect observed on the synthetic reference company and
pins the fix: LAB-1, PAY-FB-1, PAY-FB-2, PAY-CONTRIB-1, EMP201-2, SKL-1, EE-ISO-1,
INJ-1, INJ-2, INJ-3.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import frappe
from frappe.tests.classes import IntegrationTestCase

from za_local_payroll.sa_coida.doctype.oid_claim.oid_claim import OIDClaim
from za_local_payroll.sa_coida.doctype.workplace_injury.workplace_injury import WorkplaceInjury
from za_local_payroll.sa_labour import governance
from za_local_payroll.sa_payroll.doctype.emp201_submission.emp201_submission import (
	_looks_like_legacy_statutory_component,
)
from za_local_payroll.sa_payroll.fringe_benefits import service
from za_local_payroll.setup.default_data import DEFAULT_SALARY_COMPONENT_SARS_CODES

APP = Path(__file__).resolve().parents[1]


class TestReferenceCompanyRegressions(IntegrationTestCase):
	def test_fringe_benefit_component_lookup_aliases_abbreviation(self):
		"""PAY-FB-1: get_all selected a non-existent `abbr` column and fringe benefits never reached the slip."""
		with patch("frappe.get_all", return_value=[]) as get_all, self.assertRaises(frappe.ValidationError):
			# No rows: the lookup then reports the component missing; only the query is under test.
			service._get_salary_components({"Company Car Benefit"})
		fields = get_all.call_args_list[0].kwargs["fields"]
		self.assertIn("salary_component_abbr as abbr", fields)
		self.assertNotIn("abbr", fields)

	def test_company_car_paye_adjustment_has_sars_code(self):
		"""PAY-FB-2: the seeded adjustment component had no code, so every payroll with a car failed."""
		self.assertEqual("3802", DEFAULT_SALARY_COMPONENT_SARS_CODES["Company Car PAYE Adjustment"])

	def test_company_contribution_formula_fields_fetch_from_component(self):
		"""PAY-CONTRIB-1: structure rows lost the component's formula, so contributions computed nil."""
		meta = json.loads(
			(APP / "sa_payroll/doctype/company_contribution/company_contribution.json").read_text()
		)
		fields = {field["fieldname"]: field for field in meta["fields"]}
		for fieldname in ("condition", "amount_based_on_formula", "formula"):
			self.assertEqual(1, fields[fieldname].get("fetch_if_empty"), fieldname)

	def test_emp201_legacy_component_tokens_match_whole_words(self):
		"""EMP201-2: "Retirement Annuity" contains "eti" and blocked EMP201 as an unmapped ETI component."""
		self.assertFalse(_looks_like_legacy_statutory_component("Retirement Annuity", {}))
		self.assertFalse(_looks_like_legacy_statutory_component("Medical Aid Employee", {}))
		self.assertTrue(_looks_like_legacy_statutory_component("UIF Employee", {}))
		self.assertTrue(_looks_like_legacy_statutory_component("ETI Claimed", {}))
		self.assertTrue(_looks_like_legacy_statutory_component("Skills Development Levy", {}))

	def test_labour_doctypes_name_per_year_not_per_company_only(self):
		"""SKL-1: several sa_labour doctypes shared one naming series and a second record collided."""
		expected = {
			"skills_development_record": "format:SKI-{YYYY}-{#####}",
			"annual_training_report": "format:ATR-{YYYY}-{#####}",
			"workplace_skills_plan": "format:WSP-{YYYY}-{#####}",
			"employment_equity_movement": "format:EE-MOVE-{YYYY}-{#####}",
			"skills_development_facilitator": "format:SDF-{company}-{#####}",
			"employment_equity_target_plan": "format:EE-PLAN-{company}-{YYYY}-{#####}",
		}
		for doctype, autoname in expected.items():
			meta = json.loads((APP / f"sa_labour/doctype/{doctype}/{doctype}.json").read_text())
			self.assertEqual(autoname, meta["autoname"], doctype)

	def test_labour_records_reject_non_south_african_company(self):
		"""EE-ISO-1: an Employment Equity plan was accepted for a UK company."""
		with (
			patch("frappe.has_permission", return_value=True),
			patch.object(governance, "is_south_african_company", return_value=False),
		):
			with self.assertRaisesRegex(frappe.ValidationError, "Country set to South Africa"):
				governance.validate_company_access("UK Company")
		with (
			patch("frappe.has_permission", return_value=True),
			patch.object(governance, "is_south_african_company", return_value=True),
		):
			governance.validate_company_access("ZA Company")

	def test_injury_leave_application_carries_resolved_leave_approver(self):
		"""INJ-1: submit failed with "Leave Approver is mandatory" when HR Settings requires one."""
		doc = frappe.new_doc("Workplace Injury")
		doc.update(
			{
				"name": "INJ-TEST",
				"employee": "EMP-1",
				"injury_date": "2026-09-14",
				"leave_days": 3,
				"injury_leave_type": "ZA Occupational Injury Leave",
			}
		)
		leave = MagicMock()
		leave.name = "LAP-1"
		with (
			patch.object(WorkplaceInjury, "_validate_injury_leave_type"),
			patch.object(WorkplaceInjury, "db_set"),
			patch("frappe.db.table_exists", return_value=True),
			patch("frappe.new_doc", return_value=leave),
			patch("frappe.msgprint"),
			patch(
				"hrms.hr.doctype.leave_application.leave_application.get_employee_leave_approver",
				return_value="approver@example.test",
			),
		):
			doc.create_leave_application()
		values = leave.update.call_args.args[0]
		self.assertEqual("approver@example.test", values["leave_approver"])
		leave.insert.assert_called_once()

	def test_oid_medical_report_rejects_public_attachment(self):
		"""INJ-2: medical reports (special personal information) accepted public files."""
		doc = frappe.new_doc("OID Claim")
		doc.append(
			"medical_reports",
			{
				"report_date": "2026-09-14",
				"medical_provider": "Clinic",
				"report_type": "Initial Assessment",
				"diagnosis": "Test",
				"attachment": "/files/public-report.pdf",
			},
		)
		with patch(
			"za_local_payroll.sa_coida.doctype.oid_claim.oid_claim.validate_populated_private_attachments",
			side_effect=frappe.ValidationError("must be stored as a private file"),
		) as validator:
			with self.assertRaisesRegex(frappe.ValidationError, "private file"):
				OIDClaim.validate_medical_reports(doc)
		validator.assert_called_once()

	def test_oid_claim_cancel_ignores_injury_back_link(self):
		"""INJ-3: cancelling a submitted claim failed because the injury links back to it."""
		doc = frappe.new_doc("OID Claim")
		doc.before_cancel()
		self.assertIn("Workplace Injury", doc.ignore_linked_doctypes)

	def test_injury_cancel_unlinks_draft_children_before_deleting(self):
		"""INJ-3: cancelling an injury could not delete its own draft leave/claim (its link blocked it)."""
		doc = frappe.new_doc("Workplace Injury")
		doc.leave_application = "LAP-1"
		doc.oid_claim = "OID-1"
		order = []
		draft = MagicMock(docstatus=0)
		draft.delete.side_effect = lambda: order.append("delete")
		with (
			patch("frappe.db.exists", return_value=True),
			patch("frappe.get_doc", return_value=draft),
			patch.object(
				WorkplaceInjury, "db_set", side_effect=lambda field, *a, **k: order.append(f"unlink:{field}")
			),
		):
			doc.on_cancel()
		self.assertEqual(["unlink:leave_application", "delete", "unlink:oid_claim", "delete"], order)


class TestMedicalCertificatePrivacy(IntegrationTestCase):
	def test_leave_medical_certificate_must_be_private(self):
		"""LAB-1: a sick-leave medical certificate was accepted as a public file."""
		from za_local_payroll.overrides.leave_application import ZALeaveApplication

		doc = frappe.new_doc("Leave Application")
		doc.za_medical_certificate = "/files/public-certificate.pdf"
		with (
			patch.object(ZALeaveApplication.__mro__[1], "validate"),
			patch.object(ZALeaveApplication, "_get_governed_leave_type", return_value=None),
			patch.object(ZALeaveApplication, "validate_gender_specific_leave"),
			patch(
				"za_local_payroll.overrides.leave_application.validate_private_evidence",
				side_effect=frappe.ValidationError("must be stored as a private file"),
			) as validator,
		):
			with self.assertRaisesRegex(frappe.ValidationError, "private file"):
				ZALeaveApplication.validate(doc)
		validator.assert_called_once_with(doc, "za_medical_certificate")


class TestPayrollEngineRegressions(IntegrationTestCase):
	"""Second validation round: PAYE, UIF, SDL, ETI and directive defects."""

	def test_uif_ceiling_is_prorated_for_weekly_and_fortnightly_pay(self):
		"""PAY-UIF-1: a weekly slip was capped at the monthly ceiling (R60.00 instead of R40.87)."""
		from za_local_payroll.utils.tax_utils import calculate_uif_contribution

		weekly, _ = calculate_uif_contribution(6_000, "2026-08-31", 52)
		fortnightly, _ = calculate_uif_contribution(12_000, "2026-08-31", 26)
		monthly, _ = calculate_uif_contribution(30_000, "2026-08-31")
		self.assertAlmostEqual(40.87, weekly, places=2)
		self.assertAlmostEqual(81.75, fortnightly, places=2)
		self.assertAlmostEqual(177.12, monthly, places=2)

	def test_sars_tables_use_whole_periods_per_year(self):
		"""PAY-WEEK-1: HRMS's 52.14 weeks overstated weekly PAYE."""
		from types import SimpleNamespace

		from za_local_payroll.overrides.salary_slip import ZASalarySlip, sars_periods_per_year

		self.assertEqual(52, sars_periods_per_year(SimpleNamespace(payroll_frequency="Weekly")))
		self.assertEqual(26, sars_periods_per_year(SimpleNamespace(payroll_frequency="Fortnightly")))
		self.assertEqual(12, sars_periods_per_year(SimpleNamespace()))
		slip = SimpleNamespace(
			payroll_frequency="Weekly",
			payroll_period=frappe._dict(start_date="2026-03-01", end_date="2027-02-28"),
		)
		slip.payroll_period_is_full_tax_year = lambda: ZASalarySlip.payroll_period_is_full_tax_year(slip)
		self.assertEqual(52, ZASalarySlip.get_total_sub_periods(slip))

	@patch("za_local_payroll.utils.tax_utils._get_payroll_period_name", return_value="2026-2027")
	@patch("za_local_payroll.utils.tax_utils.frappe.get_single")
	def test_medical_credit_to_date_counts_only_membership_months_so_far(self, get_single, _period):
		"""PAY-MTC-1: a June joiner was credited 9 months x 4/12 in June (R1,128) instead of R376."""
		from za_local_payroll.utils.tax_utils import get_medical_aid_credit

		get_single.return_value = frappe._dict(
			medical_tax_credit=[
				frappe._dict(
					payroll_period="2026-2027", one_dependant=376, two_dependant=376, additional_dependant=254
				)
			]
		)
		slip = frappe._dict(end_date="2026-06-30")
		self.assertEqual(
			376, get_medical_aid_credit(slip, 0, membership_start_date="2026-06-01", up_to_date="2026-06-30")
		)
		self.assertEqual(
			0, get_medical_aid_credit(slip, 0, membership_start_date="2026-06-01", up_to_date="2026-05-31")
		)
		self.assertEqual(9 * 376, get_medical_aid_credit(slip, 0, membership_start_date="2026-06-01"))

	def test_recurring_additional_salary_projection_is_removed_from_the_average(self):
		"""PAY-RECUR-1: HRMS adds the future months of a recurring Additional Salary to this
		period; the average method then annualised the projection, front-loading the tax."""
		from types import SimpleNamespace

		from za_local_payroll.overrides.salary_slip import ZASalarySlip

		row = frappe._dict(
			is_tax_applicable=1,
			additional_amount=2_000,
			is_recurring_additional_salary=1,
			additional_salary="AS-1",
		)
		slip = SimpleNamespace(tax_slab=frappe._dict(allow_tax_exemption=1))
		slip.get = lambda field: [row] if field == "earnings" else []
		slip.get_future_recurring_additional_amount = Mock(return_value=4_000)
		self.assertEqual(4_000, ZASalarySlip.get_future_recurring_projection(slip))

	def test_paye_exclusion_is_counted_where_paid_not_projected(self):
		"""PAY-INCL-1: a once-off payment below 100% inclusion was annualised in full but only
		the period's exclusion was removed, overstating PAYE."""
		from types import SimpleNamespace

		from za_local_payroll.overrides.salary_slip import ZASalarySlip

		slip = SimpleNamespace(payroll_period=None)
		slip.get = lambda field: (
			[
				frappe._dict(salary_component="Travel", amount=6_000, is_tax_applicable=1),
				frappe._dict(salary_component="Basic", amount=30_000, is_tax_applicable=1),
				frappe._dict(salary_component="Gratuity", amount=10_000, is_tax_applicable=1),
			]
			if field == "earnings"
			else []
		)
		inclusion = {"Travel": 80, "Basic": 100, "Gratuity": 50}
		slip.get_component_paye_inclusion_percentage = lambda component: inclusion[component]
		slip.get_sa_component_metadata = lambda component: frappe._dict(
			za_payroll_treatment="Annual Payment" if component == "Gratuity" else "Regular Remuneration"
		)
		slip.is_once_off_full_tax = lambda metadata: ZASalarySlip.is_once_off_full_tax(slip, metadata)
		self.assertEqual((1_200, 5_000), ZASalarySlip.get_paye_exclusions_to_date(slip))

	def test_annual_equivalent_excludes_the_non_paye_portion_before_averaging(self):
		from types import SimpleNamespace

		from za_local_payroll.overrides.salary_slip import ZASalarySlip

		slip = SimpleNamespace(
			previous_taxable_earnings=0,
			current_structured_taxable_earnings=36_000.0,
			current_additional_earnings=0,
			current_additional_earnings_with_full_tax=0,
			other_incomes=0,
			unclaimed_taxable_benefits=0,
			total_exemption_amount=0,
		)
		slip.get_total_sub_periods = Mock(return_value=12)
		slip.get_periods_employed_to_date = Mock(return_value=1)
		slip.get_previous_annual_payment_earnings = Mock(return_value=0)
		slip.get_paye_exclusions_to_date = Mock(return_value=(1_200, 0))
		slip.get_future_recurring_projection = Mock(return_value=0)
		ZASalarySlip.apply_sars_annual_equivalent(slip)
		self.assertAlmostEqual((36_000 - 1_200) * 12, slip.total_taxable_earnings)

	def test_sdl_uses_paye_inclusion_and_only_the_allowable_retirement_deduction(self):
		"""PAY-BASIS-1/2: SDL was levied on 100% of a travel allowance and deducted retirement
		contributions above the 27.5% / annual cap."""
		from types import SimpleNamespace

		from za_local_payroll.overrides.salary_slip import ZASalarySlip

		slip = SimpleNamespace(za_retirement_allowed_ratio=0.75)
		slip.get_statutory_earning_basis = Mock(return_value=100_000)
		slip.get_current_retirement_fund_contribution = Mock(return_value=40_000)
		self.assertEqual(70_000, ZASalarySlip.get_sdl_leviable_amount(slip))
		slip.get_statutory_earning_basis.assert_called_once_with(
			"za_sdl_applicable", apply_paye_inclusion=True
		)

	def test_lump_sum_without_directive_is_refused(self):
		"""PAY-TERM-1: severance was annualised into normal PAYE and the directive ignored."""
		from types import SimpleNamespace

		from za_local_payroll.overrides.salary_slip import ZASalarySlip

		slip = SimpleNamespace(employee="EMP-1", start_date="2026-11-01", end_date="2026-11-30")
		slip.get_lump_sum_earnings = Mock(return_value=88_615.38)
		slip.get_active_tax_directive = Mock(return_value=None)
		with self.assertRaisesRegex(frappe.ValidationError, "Tax Directive"):
			ZASalarySlip.apply_lump_sum_directive(slip)

	@patch("za_local_payroll.overrides.salary_slip.get_salary_component_data", return_value=frappe._dict())
	def test_lump_sum_directive_tax_is_deducted_as_4115(self, _component_data):
		from types import SimpleNamespace

		from za_local_payroll.overrides.salary_slip import ZASalarySlip

		deductions = []
		slip = SimpleNamespace(employee="EMP-1", start_date="2026-11-01", end_date="2026-11-30")
		slip.get = lambda field: deductions if field == "deductions" else []
		slip.get_lump_sum_earnings = Mock(return_value=88_615.38)
		slip.get_active_tax_directive = Mock(
			return_value=frappe._dict(
				name="TAX-DIR-1", directive_type="Severance / Lump Sum", fixed_amount=6_950.77
			)
		)
		slip.get_configured_statutory_component = Mock(return_value="Tax on Lump Sum")
		slip.update_component_row = lambda data, amount, table, **kw: deductions.append(
			frappe._dict(salary_component="Tax on Lump Sum", amount=amount)
		)
		slip.recalculate_totals_after_statutory_adjustment = Mock()
		ZASalarySlip.apply_lump_sum_directive(slip)
		self.assertEqual(
			[("Tax on Lump Sum", 6_950.77)], [(d.salary_component, d.amount) for d in deductions]
		)
		self.assertEqual("TAX-DIR-1", slip.za_tax_directive)

	def test_severance_never_enters_the_paye_average(self):
		from types import SimpleNamespace

		from za_local_payroll.overrides.salary_slip import ZASalarySlip

		slip = SimpleNamespace(end_date="2026-11-30")
		slip.get_sa_component_metadata = lambda c: frappe._dict(
			za_payroll_treatment="Severance Benefit", za_paye_inclusion_percentage=100
		)
		self.assertEqual(0, ZASalarySlip.get_component_paye_inclusion_percentage(slip, "Severance Benefit"))

	def test_nil_lump_sum_directive_is_accepted_with_the_directive_attached(self):
		"""DIR-1: a nil-tax severance directive could not be captured."""
		doc = frappe.new_doc("Tax Directive")
		doc.directive_type = "Severance / Lump Sum"
		doc.fixed_amount = 0
		with self.assertRaisesRegex(frappe.ValidationError, "Attach"):
			doc.validate_directive_details()
		doc.attachment = "/private/files/directive.pdf"
		doc.validate_directive_details()

	@patch("za_local_payroll.services.statutory_rates.resolve_nmw_rate")
	@patch("za_local_payroll.utils.eti_utils.get_eti_wage_paid", return_value=(5_000.0, ["Basic"]))
	def test_eti_wage_test_falls_back_to_the_governed_nmw(self, _wage_paid, resolve_nmw):
		"""PAY-ETI-1: with no rate captured the ETI wage test failed instead of using the NMW pack."""
		from za_local_payroll.utils.eti_utils import check_eti_minimum_wage

		resolve_nmw.return_value = frappe._dict(value=30.23, source_reference="DEL-NMW")
		employee = frappe._dict(za_eti_minimum_wage_basis="National or Regulated Minimum Wage")
		result = check_eti_minimum_wage(employee, frappe._dict(end_date="2026-08-31"), {}, 5_000, 160)
		self.assertTrue(result.eligible)
		self.assertAlmostEqual(30.23 * 160, result.minimum_wage, places=2)
		self.assertIn("General NMW", result.minimum_wage_source)

	def test_packaged_tax_slabs_have_exact_band_limits(self):
		"""SLAB-1: bands ending at .99 overtaxed every full band by R0.99 under HRMS's (to - from + 1)."""
		from hrms.payroll.doctype.income_tax_slab.income_tax_slab import calculate_base_tax_from_tax_slabs

		data = json.loads((APP / "setup/data/tax_slabs_2027.json").read_text())[0]
		slab = frappe._dict(slabs=[frappe._dict(condition=None, **row) for row in data["slabs"]])
		self.assertAlmostEqual(44_118, calculate_base_tax_from_tax_slabs(245_100, slab, {}, {}), places=2)
		self.assertAlmostEqual(79_998, calculate_base_tax_from_tax_slabs(383_100, slab, {}, {}), places=2)

	def test_severance_component_is_created_with_its_intended_treatment(self):
		"""PAY-SEED-1: Severance Benefit was installed UIF, SDL and COIDA applicable."""
		from za_local_payroll.setup.default_data import DEFAULT_SALARY_COMPONENT_TREATMENTS

		treatment = DEFAULT_SALARY_COMPONENT_TREATMENTS["Severance Benefit"]
		self.assertEqual(0, treatment["za_uif_applicable"])
		self.assertEqual(0, treatment["za_sdl_applicable"])
		self.assertIn("DEFAULT_SALARY_COMPONENT_TREATMENTS.get(name", (APP / "setup/masters.py").read_text())


class TestCertificateAndAccountingRegressions(IntegrationTestCase):
	"""Second validation round: IRP5, SARS codes, references, GL and settlement."""

	def test_employer_fund_contribution_adds_fringe_benefit_and_deemed_deduction(self):
		"""PAY-RET-1: 4472 requires 3817 and 4001 (BRS v25.3.0); the certificate had neither."""
		from collections import defaultdict

		from za_local_payroll.sa_payroll.doctype.irp5_certificate.irp5_certificate import (
			apply_deemed_employee_contributions,
		)

		def table():
			return defaultdict(lambda: {"description": "", "amount": 0.0})

		income, deductions, contributions = table(), table(), table()
		deductions["4001"]["amount"] = 126_000
		contributions["4472"]["amount"] = 168_000
		with patch("frappe.db.get_value", return_value="description"):
			added = apply_deemed_employee_contributions(frappe._dict(), income, deductions, contributions)
		self.assertEqual(168_000, added)
		self.assertEqual(168_000, income["3817"]["amount"])
		self.assertEqual(294_000, deductions["4001"]["amount"])

	def test_employer_medical_benefit_reports_equal_4474_and_counts_in_4005(self):
		"""PAY-MED-1: the medical earning was coded 4474, so certificates failed."""
		from collections import defaultdict

		from za_local_payroll.sa_payroll.doctype.irp5_certificate.irp5_certificate import (
			apply_deemed_employee_contributions,
		)
		from za_local_payroll.setup.default_data import DEFAULT_SALARY_COMPONENT_SARS_CODES

		self.assertEqual("3810", DEFAULT_SALARY_COMPONENT_SARS_CODES["Medical Aid Company Contribution"])

		def table():
			return defaultdict(lambda: {"description": "", "amount": 0.0})

		income, deductions, contributions = table(), table(), table()
		income["3810"]["amount"] = 24_000
		deductions["4005"]["amount"] = 48_000
		with patch("frappe.db.get_value", return_value="description"):
			added = apply_deemed_employee_contributions(frappe._dict(), income, deductions, contributions)
		self.assertEqual(0, added)
		self.assertEqual(24_000, contributions["4474"]["amount"])
		self.assertEqual(72_000, deductions["4005"]["amount"])

	def test_certificate_takes_medical_credit_from_the_slip(self):
		"""IRP5-MTC-1: 4116 was always nil because the credit was never written to the slip."""
		source = (APP / "sa_payroll/doctype/irp5_certificate/irp5_certificate.py").read_text()
		self.assertIn('salary_slip_doc.get("za_medical_tax_credit")', source)
		self.assertIn("za_medical_tax_credit", (APP / "overrides/salary_slip.py").read_text())

	def test_certificate_never_shows_the_vat_number_as_employer_tax_id(self):
		"""COMP-1: the employer's VAT number was printed as its tax ID."""
		source = (APP / "sa_payroll/doctype/irp5_certificate/irp5_certificate.py").read_text()
		self.assertIn('company.get("za_income_tax_reference_number")', source)
		self.assertNotIn("self.employer_tax_id = company.tax_id", source)

	def test_sars_reference_check_digits_follow_brs_appendix_b(self):
		"""BRS-REF-1: references were never checked."""
		from za_local_payroll.utils.sars_references import (
			is_valid_employer_reference,
			is_valid_income_tax_number,
			validate_company_references,
		)

		self.assertTrue(is_valid_income_tax_number("0001339050"))  # BRS 8.1 example 1
		self.assertTrue(is_valid_income_tax_number("0667056642"))  # BRS 8.1 example 2
		self.assertFalse(is_valid_income_tax_number("0667056643"))
		self.assertTrue(is_valid_employer_reference("7900000011", "PAYE"))
		self.assertFalse(is_valid_employer_reference("7900000012", "PAYE"))
		self.assertFalse(is_valid_employer_reference("L900000011", "UIF"))
		with self.assertRaisesRegex(frappe.ValidationError, "check digit"):
			validate_company_references(frappe._dict(za_paye_reference_number="7900000012"))

	def test_reportlab_is_a_declared_dependency(self):
		"""PKG-1: IRP5 PDFs failed on a clean install."""
		self.assertIn('"reportlab', (APP.parent / "pyproject.toml").read_text())

	def test_code_master_follows_brs(self):
		"""SARS-1..13: mislabelled, invalid and missing codes in the shipped master."""
		from za_local_payroll.setup.default_data import (
			DEFAULT_SALARY_COMPONENT_SARS_CODES,
			DEFAULT_SARS_PAYROLL_CODES,
		)

		codes = {row["code"]: row for row in DEFAULT_SARS_PAYROLL_CODES}
		for code in ("3606", "3714", "3722", "3810", "3817", "3825", "3828", "4003", "4473"):
			self.assertEqual(1, codes[code]["active"], code)
		for code in ("4007", "4008", "4010", "4476", "4477", "4497"):
			self.assertEqual(0, codes[code]["active"], code)
		self.assertIn("Reimbursive travel", codes["3702"]["description"])
		self.assertEqual("Non-Taxable", codes["3702"]["tax_treatment"])
		self.assertIn("Other allowances", codes["3713"]["description"])
		self.assertIn("retirement annuity", codes["4475"]["description"].lower())
		self.assertEqual("3606", DEFAULT_SALARY_COMPONENT_SARS_CODES["Commission"])
		self.assertEqual("4003", DEFAULT_SALARY_COMPONENT_SARS_CODES["Provident Fund"])
		self.assertEqual("3713", DEFAULT_SALARY_COMPONENT_SARS_CODES["Cell Phone Allowance"])
		self.assertEqual("3605", DEFAULT_SALARY_COMPONENT_SARS_CODES["Leave Payout"])
		self.assertNotIn("Group Life Insurance", DEFAULT_SALARY_COMPONENT_SARS_CODES)

	def test_irp5_excluded_component_needs_no_sars_code(self):
		"""PAY-CFG-1: union fees had to carry a code (4497) though excluded from the IRP5."""
		from types import SimpleNamespace

		from za_local_payroll.overrides.salary_slip import ZASalarySlip

		slip = SimpleNamespace()
		metadata = frappe._dict(za_exclude_from_irp5=1)
		self.assertEqual("", ZASalarySlip.get_required_sars_code(slip, "Union Subscription", metadata))
		with self.assertRaises(frappe.ValidationError):
			ZASalarySlip.get_required_sars_code(
				slip, "Basic", frappe._dict(za_payroll_treatment="Regular Remuneration")
			)

	def test_employer_fund_contribution_counts_toward_the_retirement_cap(self):
		"""PAY-RET-1: the employer contribution was ignored in the 27.5% / R430,000 test."""
		from types import SimpleNamespace

		from za_local_payroll.overrides.salary_slip import ZASalarySlip

		slip = SimpleNamespace(
			tax_slab=frappe._dict(allow_tax_exemption=1),
			total_taxable_earnings=1_500_000,
			end_date="2026-08-31",
		)
		slip.get_annual_retirement_fund_contribution = Mock(return_value=300_000)
		slip.get_annual_employer_fund_contribution = Mock(return_value=200_000)
		ZASalarySlip.apply_retirement_fund_deduction_cap(slip)
		# 500 000 of contributions against the R430 000 cap: 70 000 is taxable again.
		self.assertAlmostEqual(1_570_000, slip.total_taxable_earnings)
		self.assertAlmostEqual(430_000 / 500_000, slip.za_retirement_allowed_ratio)

	def test_contribution_journal_credits_each_liability(self):
		"""ACC-1: employer UIF, SDL and pension were credited to Payroll Payable."""
		from za_local_payroll.setup.masters import DEFAULT_CONTRIBUTION_LIABILITY_ACCOUNT_NAMES

		self.assertEqual(
			"SDL Payable - SARS", DEFAULT_CONTRIBUTION_LIABILITY_ACCOUNT_NAMES["SDL Contribution"]
		)
		source = (APP / "overrides/payroll_entry.py").read_text()
		self.assertIn("mapping.za_liability_account or self.payroll_payable_account", source)

	def test_bank_settlement_requires_a_submitted_unchanged_batch(self):
		"""PAY-PAY-1: the batch posted nothing; settlement was a manual journal."""
		batch = frappe.new_doc("Payroll Payment Batch")
		batch.docstatus = 0
		with patch.object(type(batch), "check_permission"):
			with self.assertRaisesRegex(frappe.ValidationError, "Submit"):
				batch.record_bank_settlement()
		batch.docstatus = 1
		batch.eft_source_hash = "original"
		with (
			patch.object(type(batch), "check_permission"),
			patch(
				"za_local_payroll.sa_payroll.doctype.payroll_payment_batch.payroll_payment_batch.build_payment_batch_snapshot",
				return_value=frappe._dict(source_hash="changed", recipients=()),
			),
		):
			with self.assertRaisesRegex(frappe.ValidationError, "changed"):
				batch.record_bank_settlement()


class TestCOIDAReturnRegressions(IntegrationTestCase):
	"""COIDA-ROE-1, COIDA-SOD-1, COIDA-ISO-1, INJ-4."""

	def test_monthly_declaration_counts_people_and_capped_earnings(self):
		from za_local_payroll.sa_coida.doctype.coida_annual_return.coida_annual_return import (
			COIDAAnnualReturn,
		)

		rows = [
			{
				"employee": "E1",
				"period_end": "2026-03-31",
				"is_director": 0,
				"capped_assessable_earnings": 100.0,
			},
			{
				"employee": "E1",
				"period_end": "2026-03-31",
				"is_director": 0,
				"capped_assessable_earnings": 50.0,
			},
			{
				"employee": "D1",
				"period_end": "2026-03-31",
				"is_director": 1,
				"capped_assessable_earnings": 300.0,
			},
			{
				"employee": "E2",
				"period_end": "2027-02-28",
				"is_director": 0,
				"capped_assessable_earnings": 70.0,
			},
		]
		months = COIDAAnnualReturn._monthly_declaration(None, rows)
		self.assertEqual(["Mar", "Feb"], [m["month"] for m in months])
		self.assertEqual(
			(1, 150.0, 1, 300.0),
			tuple(months[0][k] for k in ("employees", "employee_earnings", "directors", "director_earnings")),
		)

	def test_assessment_includes_free_food_and_quarters(self):
		doc = frappe.new_doc("COIDA Annual Return")
		doc.update(
			{
				"company": "X",
				"industry_class": "Y",
				"from_date": "2026-03-01",
				"total_annual_earnings": 1000,
				"free_food_and_quarters": 200,
			}
		)
		module = "za_local_payroll.sa_coida.doctype.coida_annual_return.coida_annual_return"
		with (
			patch(
				f"{module}.resolve_coida_industry_rate",
				return_value=frappe._dict(value=1.0, rule_key="r", source_reference="s"),
			),
			patch(
				f"{module}.resolve_coida_minimum_assessment",
				return_value=frappe._dict(value=0, rule_key="m", source_reference="s"),
			),
		):
			doc.calculate_assessment_fee()
		self.assertEqual(1200, doc.grand_total_earnings)
		self.assertEqual(12, doc.assessment_fee)

	def test_return_is_refused_for_a_foreign_company(self):
		doc = frappe.new_doc("COIDA Annual Return")
		doc.company = "Foreign"
		module = "za_local_payroll.sa_coida.doctype.coida_annual_return.coida_annual_return"
		with patch(f"{module}.is_south_african_company", return_value=False):
			with self.assertRaisesRegex(frappe.ValidationError, "South Africa"):
				doc.validate()

	def test_preparer_cannot_review_their_own_return(self):
		source = (APP / "sa_coida/doctype/coida_annual_return/coida_annual_return.py").read_text()
		self.assertIn("additional_excluded_users=(self.prepared_by,)", source)

	def test_hr_manager_can_cancel_and_amend_coida_records(self):
		for doctype in ("coida_annual_return", "workplace_injury", "oid_claim"):
			meta = json.loads((APP / f"sa_coida/doctype/{doctype}/{doctype}.json").read_text())
			hr = [p for p in meta["permissions"] if p["role"] == "HR Manager"]
			self.assertTrue(hr and hr[0].get("cancel") and hr[0].get("amend"), doctype)


class TestPayrollFilingControls(IntegrationTestCase):
	"""EMP201-1: EMP201, IRP5 and EMP501 had no maker-checker and no filing or SARS receipt record."""

	def test_emp201_due_date_is_seven_days_after_month_end_moved_back_over_weekends(self):
		from za_local_payroll.sa_payroll.statutory_filing import emp201_due_date

		self.assertEqual("2026-04-07", str(emp201_due_date("2026-03-31")))
		# 7 June 2026 is a Sunday: due on Friday 5 June.
		self.assertEqual("2026-06-05", str(emp201_due_date("2026-05-31")))

	def test_review_excludes_the_preparer_and_falls_back_to_the_creator(self):
		from za_local_payroll.sa_payroll import statutory_filing

		doc = frappe._dict(owner="maker@example.test", prepared_by=None, reviewed_by="checker@example.test")
		with patch.object(statutory_filing, "validate_accountable_actor") as validate:
			statutory_filing.require_independent_review(doc)
		self.assertEqual("maker@example.test", doc.prepared_by)
		self.assertEqual(
			(doc, "reviewed_by", ("Payroll Manager", "System Manager"), "submit"), validate.call_args.args
		)
		self.assertEqual(("maker@example.test",), validate.call_args.kwargs["additional_excluded_users"])
		self.assertTrue(doc.reviewed_on)

	def test_each_working_paper_requires_independent_review_on_submit(self):
		for module in (
			"emp201_submission.emp201_submission",
			"emp501_reconciliation.emp501_reconciliation",
			"irp5_certificate.irp5_certificate",
		):
			source = (APP / f"sa_payroll/doctype/{module.replace('.', '/')}.py").read_text()
			self.assertIn("require_independent_review(self)", source, module)
			self.assertIn("set_preparer(self)", source, module)

	def test_filing_requires_a_submitted_paper_an_obligation_and_named_controllers(self):
		from za_local_payroll.sa_payroll import statutory_filing

		doc = frappe._dict(doctype="EMP201 Submission", docstatus=0, za_filing=None)
		kwargs = dict(
			obligation_setting="za_emp201_compliance_obligation",
			period_start="2026-03-01",
			period_end="2026-03-31",
			declared_amount=1,
			ledger_amount=1,
			payload={},
		)
		with self.assertRaisesRegex(frappe.ValidationError, "Submit"):
			statutory_filing.create_filing(doc, **kwargs)
		doc.docstatus = 1
		with (
			patch("frappe.has_permission", return_value=True),
			patch("frappe.db.get_single_value", return_value=None),
			self.assertRaisesRegex(frappe.ValidationError, "Payroll Settings"),
		):
			statutory_filing.create_filing(doc, **kwargs)
		doc.meta = frappe.get_meta("EMP201 Submission")
		with (
			patch("frappe.has_permission", return_value=True),
			patch("frappe.db.get_single_value", return_value="EMP201"),
			self.assertRaisesRegex(frappe.ValidationError, "Filing Due Date"),
		):
			statutory_filing.create_filing(doc, **kwargs)

	def test_payroll_manager_runs_certificates_and_emp501_hr_manager_reads(self):
		for doctype in ("irp5_certificate", "emp501_reconciliation"):
			meta = json.loads((APP / f"sa_payroll/doctype/{doctype}/{doctype}.json").read_text())
			roles = {p["role"]: p for p in meta["permissions"]}
			self.assertTrue(roles["Payroll Manager"].get("submit"), doctype)
			self.assertFalse(roles["HR Manager"].get("submit"), doctype)
			self.assertFalse(roles["Payroll User"].get("submit"), doctype)


class TestLeastPrivilegeRoles(IntegrationTestCase):
	"""PERM-1 and EE-PERM-1: a payroll year needed System Manager plus HR Manager plus Payroll Manager."""

	def test_payroll_manager_can_run_payroll_and_tax_directives(self):
		from za_local_payroll.setup.role_grants import grant_payroll_permissions

		grant_payroll_permissions()
		for doctype in ("Payroll Entry", "Salary Slip", "Additional Salary"):
			rule = frappe.db.get_value(
				"Custom DocPerm",
				{"parent": doctype, "role": "Payroll Manager", "permlevel": 0},
				["read", "submit", "cancel"],
				as_dict=True,
			)
			self.assertEqual((1, 1, 1), (rule.read, rule.submit, rule.cancel), doctype)
		directive = json.loads((APP / "sa_payroll/doctype/tax_directive/tax_directive.json").read_text())
		manager = next(p for p in directive["permissions"] if p["role"] == "Payroll Manager")
		self.assertTrue(manager["submit"] and manager["cancel"] and manager["amend"])

	def test_compliance_reviewer_can_read_company(self):
		from za_local_core.role_grants import grant_core_permissions

		grant_core_permissions()
		self.assertTrue(
			frappe.db.get_value(
				"Custom DocPerm",
				{"parent": "Company", "role": "ZA Compliance Reviewer", "permlevel": 0},
				"read",
			)
		)

	def test_existing_rules_are_never_overridden(self):
		from za_local_core import role_grants

		with (
			patch.object(role_grants.frappe.db, "exists", return_value=True),
			patch.object(role_grants, "add_permission") as add,
		):
			self.assertEqual([], role_grants.grant_permissions((("Company", "Payroll Manager", ("read",)),)))
		add.assert_not_called()


class TestGovernedPayrollRates(IntegrationTestCase):
	"""GOV-4: payroll scalars silently fell back to packaged JSON with no approved pack."""

	def _resolve(self, allowed):
		from za_local_payroll.utils import statutory_rates

		with (
			patch.object(statutory_rates, "_get_core_rate", return_value=None),
			patch.dict(frappe.flags, {"in_test": False}),
			patch("frappe.db.get_single_value", return_value=allowed),
		):
			return statutory_rates.get_uif_monthly_cap("2026-06-30")

	def test_packaged_rate_needs_a_recorded_decision(self):
		with self.assertRaisesRegex(frappe.ValidationError, "Allow Packaged Statutory Rates"):
			self._resolve(0)
		self.assertGreater(self._resolve(1), 0)

	def test_approved_pack_is_used_without_any_decision(self):
		from za_local_payroll.utils import statutory_rates

		with (
			patch.object(statutory_rates, "_get_core_rate", return_value=17712),
			patch.dict(frappe.flags, {"in_test": False}),
			patch("frappe.db.get_single_value", side_effect=AssertionError("not consulted")),
		):
			self.assertEqual(17712, statutory_rates.get_uif_monthly_cap("2026-06-30"))
