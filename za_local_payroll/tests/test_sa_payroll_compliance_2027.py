import json
from pathlib import Path

import frappe
from frappe.tests.classes import UnitTestCase

from za_local_payroll.setup.custom_fields import get_payroll_custom_fields
from za_local_payroll.utils.lump_sum_tax_utils import calculate_severance_tax
from za_local_payroll.utils.statutory_rates import (
	calculate_eti_from_pack,
	get_coida_annual_earnings_cap,
	get_rate_pack,
	get_reimbursive_travel_rate,
	get_retirement_annual_cap,
	get_uif_monthly_cap,
)
from za_local_payroll.utils.tax_utils import calculate_sdl_contribution, calculate_uif_contribution
from za_local_payroll.utils.travel_allowance_utils import (
	calculate_fixed_allowance,
	calculate_reimbursive_allowance,
)


class TestSAPayrollCompliance2027(UnitTestCase):
	def test_2027_statutory_pack_contains_required_annual_values(self):
		pack = get_rate_pack("2026-03-31")

		self.assertEqual("2026-2027", pack["tax_year"])
		self.assertEqual(17820, pack["paye"]["rebates"]["primary"])
		self.assertEqual(17712, get_uif_monthly_cap("2026-03-31"))
		self.assertEqual(4.95, get_reimbursive_travel_rate("2026-03-31"))
		self.assertEqual(668000, get_coida_annual_earnings_cap("2027-02-28"))
		self.assertEqual(430000, get_retirement_annual_cap("2027-02-28"))

	def test_uif_and_sdl_use_statutory_pack_rates(self):
		self.assertEqual(
			(80, 80),
			tuple(round(v, 2) for v in calculate_uif_contribution(8000, "2026-03-31")),
		)
		self.assertEqual(
			(177.12, 177.12),
			tuple(round(v, 2) for v in calculate_uif_contribution(30000, "2026-03-31")),
		)
		self.assertEqual(300, calculate_sdl_contribution(30000, "2026-03-31"))

	def test_eti_2027_first_and_second_period_amounts(self):
		self.assertEqual(1125, calculate_eti_from_pack(6000, 1, "2026-03-31"))
		self.assertEqual(562.5, calculate_eti_from_pack(6000, 13, "2026-03-31"))
		self.assertEqual(0, calculate_eti_from_pack(7500, 1, "2026-03-31"))

	def test_travel_allowance_helpers_apply_2027_rates(self):
		self.assertEqual(
			{"taxable": 4000, "non_taxable": 1000},
			calculate_fixed_allowance(5000, date_value="2026-03-31"),
		)
		self.assertEqual(
			{
				"total": 1980,
				"taxable": 0,
				"non_taxable": 1980,
				"prescribed_rate": 4.95,
			},
			calculate_reimbursive_allowance(400, date_value="2026-03-31"),
		)
		self.assertEqual(20, calculate_reimbursive_allowance(400, 5.00, "2026-03-31")["taxable"])

	def test_severance_lump_sum_uses_550k_exemption_and_table(self):
		self.assertEqual(0, calculate_severance_tax(550000, "2026-03-31"))
		self.assertEqual(9000, calculate_severance_tax(600000, "2026-03-31"))
		self.assertEqual(39600, calculate_severance_tax(770000, "2026-03-31"))

	def test_salary_component_classification_fields_are_defined(self):
		fieldnames = {
			field["fieldname"]
			for field in get_payroll_custom_fields()["Salary Component"]
		}
		for fieldname in (
			"za_payroll_treatment",
			"za_paye_inclusion_percentage",
			"za_uif_applicable",
			"za_sdl_applicable",
			"za_coida_applicable",
			"za_is_reimbursement",
			"za_variable_pay_treatment",
		):
			self.assertIn(fieldname, fieldnames)

	def test_statutory_rate_pack_json_is_valid(self):
		path = Path(
			frappe.get_app_path(
				"za_local_payroll",
				"setup",
				"data",
				"statutory_rates_2027.json",
			)
		)
		data = json.loads(path.read_text())
		self.assertEqual("2026-2027", data["tax_year"])
		self.assertEqual(7, len(data["paye"]["brackets"]))
		self.assertEqual(4, len(data["eti"]["first_12_months"]))
