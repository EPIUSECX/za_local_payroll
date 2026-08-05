from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import frappe
from frappe.tests.classes import UnitTestCase

from za_local_payroll.sa_coida.doctype.oid_claim.oid_claim import OIDClaim
from za_local_payroll.sa_labour.doctype.bargaining_council.bargaining_council import (
	import_common_councils,
)
from za_local_payroll.sa_labour.doctype.business_trip.business_trip import (
	create_expense_claim_from_trip,
	generate_allowances_for_date_range,
)
from za_local_payroll.sa_labour.doctype.business_trip_region.business_trip_region import (
	get_active_regions,
)
from za_local_payroll.sa_labour.doctype.business_trip_settings.business_trip_settings import (
	get_expense_claim_types,
	get_mileage_rate,
)
from za_local_payroll.sa_labour.doctype.sectoral_minimum_wage.sectoral_minimum_wage import (
	SectoralMinimumWage,
)
from za_local_payroll.sa_labour.doctype.workplace_skills_plan.workplace_skills_plan import (
	WorkplaceSkillsPlan,
)
from za_local_payroll.sa_labour.report_utils import suppress_count
from za_local_payroll.services.statutory_rates import OFFICIAL_2026_REFERENCE_VALUES


class TestWorkplaceProductionControls(UnitTestCase):
	def test_every_workplace_whitelist_declares_one_http_method(self):
		expected = {
			get_active_regions: ["GET"],
			get_mileage_rate: ["GET"],
			get_expense_claim_types: ["GET"],
			create_expense_claim_from_trip: ["POST"],
			generate_allowances_for_date_range: ["POST"],
			import_common_councils: ["POST"],
			OIDClaim.update_claim_status: ["POST"],
			OIDClaim.add_medical_report: ["POST"],
		}
		for method, allowed in expected.items():
			self.assertEqual(allowed, frappe.allowed_http_methods_for_whitelisted_func[method])

		root = Path(frappe.get_app_path("za_local_payroll"))
		unrestricted = [
			str(path.relative_to(root))
			for path in root.rglob("*.py")
			if "tests" not in path.parts
			if "@frappe.whitelist()" in path.read_text(encoding="utf-8")
		]
		self.assertEqual([], unrestricted)

	def test_oid_medical_report_mutation_requires_claim_admin_role(self):
		doc = frappe.new_doc("OID Claim")
		doc.docstatus = 1
		with (
			patch.object(doc, "check_permission"),
			patch("frappe.only_for", side_effect=frappe.PermissionError),
			self.assertRaises(frappe.PermissionError),
		):
			OIDClaim.add_medical_report(
				doc,
				"2026-06-01",
				"Provider",
				"Progress Report",
				"Diagnosis",
			)

	def test_official_2026_reference_anchors_are_exact_and_category_specific(self):
		self.assertEqual(668000, OFFICIAL_2026_REFERENCE_VALUES["coida.annual_earnings_cap"]["value"])
		self.assertEqual(1621, OFFICIAL_2026_REFERENCE_VALUES["coida.minimum_assessment"]["value"])
		self.assertEqual(560, OFFICIAL_2026_REFERENCE_VALUES["coida.domestic_minimum_assessment"]["value"])
		self.assertEqual(269900.90, OFFICIAL_2026_REFERENCE_VALUES["bcea.earnings_threshold.annual"]["value"])
		self.assertEqual(30.23, OFFICIAL_2026_REFERENCE_VALUES["nmw.general.hourly"]["value"])
		self.assertEqual(16.62, OFFICIAL_2026_REFERENCE_VALUES["nmw.epwp.hourly"]["value"])
		self.assertEqual(
			"Schedule 2 allowances",
			OFFICIAL_2026_REFERENCE_VALUES["nmw.learnership.schedule_2_reference"]["value"],
		)

	def test_general_nmw_is_not_applied_to_learnerships(self):
		doc = frappe.new_doc("Sectoral Minimum Wage")
		doc.worker_category = "Learnership Schedule 2"
		doc.schedule_reference = "Schedule 2"
		doc.hourly_rate = 30.23
		with self.assertRaises(frappe.ValidationError):
			SectoralMinimumWage._validate_category(doc)

		doc.hourly_rate = 0
		SectoralMinimumWage._validate_category(doc)

	def test_small_cell_suppression_preserves_zero_and_masks_positive_small_cells(self):
		self.assertEqual(0, suppress_count(0, 5, False))
		self.assertEqual("<5", suppress_count(4, 5, False))
		self.assertEqual(5, suppress_count(5, 5, False))
		self.assertEqual(4, suppress_count(4, 5, True))

	def test_wsp_zero_budget_does_not_retain_a_stale_total(self):
		doc = frappe.new_doc("Workplace Skills Plan")
		doc.total_training_budget = 9000
		doc.training_details = []
		WorkplaceSkillsPlan._calculate_and_validate_budget(doc)
		self.assertEqual(0, doc.total_training_budget)

	def test_governed_skills_and_ee_schema_is_installed(self):
		for doctype in (
			"Employment Equity Target Plan",
			"Employment Equity Movement",
			"Skills Development Facilitator",
			"OFO Occupation",
			"Training Provider",
		):
			self.assertTrue(frappe.db.exists("DocType", doctype), doctype)
		self.assertEqual("Link", frappe.get_meta("Workplace Skills Plan").get_field("fiscal_year").fieldtype)
		self.assertEqual("SETA", frappe.get_meta("Annual Training Report").get_field("seta").options)
		self.assertEqual(
			"Training Provider",
			frappe.get_meta("Skills Development Record").get_field("training_provider").options,
		)

	def test_active_workplace_print_formats_escape_untrusted_text(self):
		root = Path(frappe.get_app_path("za_local_payroll"))
		paths = (
			root / "sa_coida/print_format/sa_coida_annual_return/sa_coida_annual_return.json",
			root / "sa_coida/print_format/sa_oid_claim/sa_oid_claim.json",
			root / "sa_labour/print_format/sa_business_trip/sa_business_trip.json",
			root / "sa_labour/print_format/sa_workplace_skills_plan/sa_workplace_skills_plan.json",
			root / "sa_labour/print_format/sa_annual_training_report/sa_annual_training_report.json",
		)
		for path in paths:
			html = json.loads(path.read_text(encoding="utf-8"))["html"]
			self.assertIn("{{ label | e }}", html, path.name)
			self.assertIn('{{ (value if value is not none else "") | e }}', html, path.name)
			self.assertIn("{{ doc.name | e }}", html, path.name)
			for unsafe in (
				"{{ row.medical_provider }}",
				"{{ row.diagnosis }}",
				"{{ row.description }}",
				"{{ row.occupational_level }}",
				"{{ row.training_provider }}",
			):
				self.assertNotIn(unsafe, html, f"{path.name}: {unsafe}")
