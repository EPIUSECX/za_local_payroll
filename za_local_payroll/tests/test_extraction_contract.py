"""Static contract for the SA Labour and SA COIDA modules this app absorbed.

These modules arrived from the separate ``za_local_workplace`` app. The checks
here pin what came with them; ``test_extraction_boundaries`` covers the payroll
side and owns the legacy-import check, which it does by parsing imports rather
than searching for a substring.
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path

import frappe
from frappe.tests.classes import UnitTestCase

from za_local_payroll import hooks
from za_local_payroll.setup.workplace import WORKPLACE_FEATURES
from za_local_payroll.setup.workplace_custom_fields import WORKPLACE_CUSTOM_FIELDS
from za_local_payroll.utils.csv_importer import MASTER_DATA_FILES


class TestExtractionContract(UnitTestCase):
	def test_hook_ownership_is_complete(self):
		"""The absorbed hooks must still be registered, alongside payroll's own."""
		self.assertLessEqual(
			{"COIDA Annual Return", "Workplace Injury", "OID Claim"},
			set(hooks.doctype_js),
		)
		self.assertLessEqual(
			{"Leave Application", "Employee Separation"},
			set(hooks.override_doctype_class),
		)
		for path in (
			hooks.after_install,
			hooks.after_migrate,
			hooks.after_uninstall,
			*hooks.override_doctype_class.values(),
			*hooks.scheduler_events["monthly_long"],
		):
			module_name, attribute = path.rsplit(".", 1)
			self.assertTrue(hasattr(importlib.import_module(module_name), attribute), path)
		self.assertFalse(hasattr(hooks, "add_to_apps_screen"))

	def test_capabilities_are_conservatively_classified(self):
		self.assertEqual(5, len(WORKPLACE_FEATURES))
		self.assertNotIn("Production", {feature[3] for feature in WORKPLACE_FEATURES})
		for feature in WORKPLACE_FEATURES:
			self.assertTrue(feature[4].strip(), feature[0])

	def test_required_workplace_fields_are_declared(self):
		self.assertTrue(
			{"za_race", "za_occupational_level", "za_is_disabled"}.issubset(
				{field["fieldname"] for field in WORKPLACE_CUSTOM_FIELDS["Employee"]}
			)
		)
		self.assertTrue(
			{
				"za_bcea_compliant",
				"za_bcea_leave_category",
				"za_applicable_gender",
			}.issubset({field["fieldname"] for field in WORKPLACE_CUSTOM_FIELDS["Leave Type"]})
		)
		self.assertIn(
			"za_medical_certificate",
			{field["fieldname"] for field in WORKPLACE_CUSTOM_FIELDS["Leave Application"]},
		)
		self.assertTrue(
			{
				"za_termination_date",
				"za_bcea_weekly_remuneration",
				"za_bcea_daily_remuneration",
				"za_bcea_remuneration_reviewed",
				"za_leave_payout_days",
			}.issubset({field["fieldname"] for field in WORKPLACE_CUSTOM_FIELDS["Employee Separation"]})
		)

	def test_reference_data_is_allowlisted(self):
		self.assertEqual(
			{
				("Business Trip Region", "business_trip_region.csv"),
				("SETA", "seta_list.csv"),
				("Bargaining Council", "bargaining_council_list.csv"),
			},
			set(MASTER_DATA_FILES),
		)

	def test_standard_records_belong_to_workplace_modules(self):
		root = Path(frappe.get_app_path("za_local_payroll"))
		for module_path, module_name in (("sa_labour", "SA Labour"), ("sa_coida", "SA COIDA")):
			for path in (root / module_path).rglob("*.json"):
				payload = json.loads(path.read_text(encoding="utf-8"))
				if payload.get("module"):
					self.assertEqual(module_name, payload["module"], str(path))
				if payload.get("doctype") == "Workspace":
					self.assertEqual("za_local_payroll", payload.get("app"), str(path))
