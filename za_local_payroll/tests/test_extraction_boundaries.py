"""Static regression tests for the payroll application boundary."""

import ast
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import frappe
from frappe.tests.classes import UnitTestCase

from za_local_payroll.setup.custom_fields import get_payroll_custom_fields
from za_local_payroll.setup.statutory import _ensure_company_record


class TestPayrollExtractionBoundaries(UnitTestCase):
	def setUp(self):
		self.app_path = Path(frappe.get_app_path("za_local_payroll"))

	def test_python_imports_do_not_depend_on_legacy_app(self):
		legacy_imports = []
		for path in self.app_path.rglob("*.py"):
			if path.name == "compat.py":
				continue
			tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
			for node in ast.walk(tree):
				if isinstance(node, ast.ImportFrom) and node.module and (
					node.module == "za_local" or node.module.startswith("za_local.")
				):
					legacy_imports.append(str(path.relative_to(self.app_path)))
				if isinstance(node, ast.Import):
					legacy_imports.extend(
						str(path.relative_to(self.app_path))
						for alias in node.names
						if alias.name == "za_local" or alias.name.startswith("za_local.")
					)
		self.assertEqual(legacy_imports, [])

	def test_flexible_benefit_css_never_hides_a_form_section(self):
		css = (self.app_path / "public" / "css" / "payroll.css").read_text(encoding="utf-8")
		self.assertNotIn(".form-section", css)
		self.assertIn('[data-fieldname="max_benefits"]', css)

	def test_custom_field_ownership_excludes_other_localisation_domains(self):
		fields = {
			field["fieldname"]
			for definitions in get_payroll_custom_fields().values()
			for field in definitions
		}
		self.assertFalse(
			fields.intersection(
				{
					"za_coida_registration_number",
					"za_seta",
					"za_bargaining_council",
					"za_vat_registration_number",
					"za_bcea_compliant",
					"business_trip",
					"is_capital_goods",
				}
			)
		)

	def test_required_runtime_apps_are_declared(self):
		from za_local_payroll import hooks

		self.assertEqual(
			set(hooks.required_apps),
			{"frappe", "erpnext", "hrms", "za_local_core"},
		)

	def test_statutory_records_are_company_scoped_and_submitted(self):
		doc = SimpleNamespace(
			name="2026-2027 - TEST",
			meta=SimpleNamespace(is_submittable=True),
			docstatus=0,
			insert=Mock(),
			submit=Mock(),
		)
		source = {"doctype": "Payroll Period", "name": "2026-2027"}
		with (
			patch("za_local_payroll.setup.statutory._get_company_scoped_name", return_value=doc.name),
			patch("za_local_payroll.setup.statutory.frappe.db.exists", return_value=False),
			patch("za_local_payroll.setup.statutory.frappe.get_doc", return_value=doc) as get_doc,
		):
			name, created = _ensure_company_record(source, "Test Company")

		self.assertTrue(created)
		self.assertEqual(name, doc.name)
		self.assertEqual(get_doc.call_args.args[0]["company"], "Test Company")
		doc.insert.assert_called_once_with(ignore_permissions=True)
		doc.submit.assert_called_once_with()
