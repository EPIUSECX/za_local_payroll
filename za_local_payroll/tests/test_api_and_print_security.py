"""Security regressions for RPC verbs and statutory print formats."""

import ast
import json
import re
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import frappe
from frappe.tests.classes import UnitTestCase

GET_ENDPOINTS = {
	"utils.extension_points.registered_bank_format_names",
	"sa_payroll.doctype.emp501_reconciliation.emp501_reconciliation.get_company_tax_details",
	"sa_payroll.doctype.emp501_reconciliation.emp501_reconciliation.get_period_dates",
	"sa_payroll.doctype.fringe_benefit.fringe_benefit.get_active_fringe_benefits",
	"sa_payroll.doctype.irp5_certificate.irp5_certificate.IRP5Certificate.get_it3_pdf",
	"sa_payroll.doctype.irp5_certificate.irp5_certificate.IRP5Certificate.get_official_pdf",
	"sa_payroll.doctype.irp5_certificate.irp5_certificate.IRP5Certificate.validate_statutory_readiness",
	"sa_payroll.doctype.irp5_certificate.irp5_certificate.get_it3_pdf",
	"sa_payroll.doctype.irp5_certificate.irp5_certificate.get_official_pdf",
	"sa_payroll.doctype.low_interest_loan_benefit.low_interest_loan_benefit.get_current_official_rate",
	"sa_payroll.doctype.tax_directive.tax_directive.get_active_directive",
	"utils.hrms.is_hrms_installed",
	# Absorbed with the SA Labour and SA COIDA modules; verbs unchanged.
	"sa_labour.doctype.business_trip_region.business_trip_region.get_active_regions",
	"sa_labour.doctype.business_trip_settings.business_trip_settings.get_expense_claim_types",
	"sa_labour.doctype.business_trip_settings.business_trip_settings.get_mileage_rate",
}

POST_ENDPOINTS = {
	# Absorbed with the SA Labour and SA COIDA modules; verbs unchanged.
	"overrides.employee_separation.ZAEmployeeSeparation.create_final_settlement",
	"sa_coida.doctype.coida_annual_return.coida_annual_return.COIDAAnnualReturn.fetch_employee_data",
	"sa_coida.doctype.coida_settings.coida_settings.COIDASettings.approve_legacy_rate_fallback",
	"sa_coida.doctype.oid_claim.oid_claim.OIDClaim.add_medical_report",
	"sa_coida.doctype.oid_claim.oid_claim.OIDClaim.update_claim_status",
	"sa_coida.doctype.workplace_injury.workplace_injury.WorkplaceInjury.create_leave_application_after_submit",
	"sa_coida.doctype.workplace_injury.workplace_injury.WorkplaceInjury.create_oid_claim_after_submit",
	"sa_labour.doctype.bargaining_council.bargaining_council.import_common_councils",
	"sa_labour.doctype.business_trip.business_trip.create_expense_claim_from_trip",
	"sa_labour.doctype.business_trip.business_trip.generate_allowances_for_date_range",
	# BCEA leave standards; reviewed POST-only, as the decorators declare.
	"setup.leave_standards.allocate_sick_leave_by_cycle",
	"setup.leave_standards.assign_leave_policy_by_cycle",
	"setup.leave_standards.create_company_leave_policies",
	"overrides.journal_entry.force_delete_all_cancelled_payroll_journal_entries",
	"overrides.journal_entry.force_delete_cancelled_payroll_journal_entry",
	"overrides.payroll_entry.ZAPayrollEntry.create_salary_slips",
	"overrides.payroll_entry.ZAPayrollEntry.fill_employee_details",
	"overrides.payroll_entry.ZAPayrollEntry.make_company_contribution_entry",
	"overrides.payroll_entry.ZAPayrollEntry.make_payment_entry",
	"overrides.payroll_entry.make_payment_entry_for_payroll",
	"sa_payroll.doctype.company_car_benefit.company_car_benefit.CompanyCarBenefit.calculate_monthly_benefit",
	"sa_payroll.doctype.emp201_submission.emp201_submission.EMP201Submission.fetch_emp201_data",
	"sa_payroll.doctype.emp201_submission.emp201_submission.EMP201Submission.set_submission_period_dates",
	"sa_payroll.doctype.emp501_reconciliation.emp501_reconciliation.EMP501Reconciliation.fetch_emp201_submissions",
	"sa_payroll.doctype.emp501_reconciliation.emp501_reconciliation.EMP501Reconciliation.generate_irp5_certificates",
	"sa_payroll.doctype.emp501_reconciliation.emp501_reconciliation.EMP501Reconciliation.submit_to_sars",
	"sa_payroll.doctype.employee_final_settlement.employee_final_settlement.EmployeeFinalSettlement.create_final_irp5",
	"sa_payroll.doctype.employee_final_settlement.employee_final_settlement.EmployeeFinalSettlement.generate_final_payslip",
	"sa_payroll.doctype.fringe_benefit.fringe_benefit.FringeBenefit.calculate_taxable_value",
	"sa_payroll.doctype.fringe_benefit.fringe_benefit.FringeBenefit.generate_monthly_breakdown",
	"sa_payroll.doctype.housing_benefit.housing_benefit.HousingBenefit.calculate_monthly_benefit",
	"sa_payroll.doctype.irp5_certificate.irp5_certificate.IRP5Certificate.export_pdf",
	"sa_payroll.doctype.irp5_certificate.irp5_certificate.IRP5Certificate.generate_certificate_data",
	"sa_payroll.doctype.irp5_certificate.irp5_certificate.bulk_generate_certificates",
	"sa_payroll.doctype.payroll_payment_batch.payroll_payment_batch.PayrollPaymentBatch.record_bank_settlement",
	"sa_payroll.doctype.emp201_submission.emp201_submission.EMP201Submission.create_za_filing",
	"sa_payroll.doctype.emp201_submission.emp201_submission.EMP201Submission.record_submission_receipt",
	"sa_payroll.doctype.emp501_reconciliation.emp501_reconciliation.EMP501Reconciliation.create_za_filing",
	"sa_payroll.doctype.emp501_reconciliation.emp501_reconciliation.EMP501Reconciliation.record_submission_receipt",
	"sa_payroll.doctype.emp501_reconciliation.emp501_reconciliation.EMP501Reconciliation.submit_reviewed_certificates",
	"sa_payroll.doctype.low_interest_loan_benefit.low_interest_loan_benefit.LowInterestLoanBenefit.calculate_interest_benefit",
	"sa_payroll.doctype.low_interest_loan_benefit.low_interest_loan_benefit.LowInterestLoanBenefit.get_official_rate",
	"sa_payroll.doctype.uif_u19_declaration.uif_u19_declaration.UifU19Declaration.export_pdf",
	"sa_payroll.doctype.uif_u19_declaration.uif_u19_declaration.UifU19Declaration.generate_u19_form",
	"utils.emp501_utils.generate_emp501_csv",
	"utils.integrations.eft_file_generator.generate_eft_file",
	"utils.integrations.sars_xml_generator.generate_emp501_xml",
}


class _WhitelistVisitor(ast.NodeVisitor):
	def __init__(self, module_name):
		self.module_name = module_name
		self.class_names = []
		self.endpoints = {}

	def visit_ClassDef(self, node):
		self.class_names.append(node.name)
		self.generic_visit(node)
		self.class_names.pop()

	def visit_FunctionDef(self, node):
		for decorator in node.decorator_list:
			target = decorator.func if isinstance(decorator, ast.Call) else decorator
			if not (
				isinstance(target, ast.Attribute)
				and isinstance(target.value, ast.Name)
				and target.value.id == "frappe"
				and target.attr == "whitelist"
			):
				continue

			methods = None
			if isinstance(decorator, ast.Call):
				for keyword in decorator.keywords:
					if keyword.arg == "methods":
						methods = ast.literal_eval(keyword.value)
			qualified_name = ".".join([self.module_name, *self.class_names, node.name])
			self.endpoints[qualified_name] = methods
		self.generic_visit(node)


class TestPayrollAPISecurity(UnitTestCase):
	def test_every_whitelisted_endpoint_has_an_explicit_reviewed_http_method(self):
		app_path = Path(frappe.get_app_path("za_local_payroll"))
		endpoints = {}
		for path in sorted(app_path.rglob("*.py")):
			if "tests" in path.parts:
				continue
			module_name = ".".join(path.relative_to(app_path).with_suffix("").parts)
			visitor = _WhitelistVisitor(module_name)
			visitor.visit(ast.parse(path.read_text(encoding="utf-8"), filename=str(path)))
			endpoints.update(visitor.endpoints)

		expected = GET_ENDPOINTS | POST_ENDPOINTS
		self.assertEqual(expected, set(endpoints), "A payroll endpoint was added or removed without review")
		for endpoint in GET_ENDPOINTS:
			self.assertEqual(["GET"], endpoints[endpoint], endpoint)
		for endpoint in POST_ENDPOINTS:
			self.assertEqual(["POST"], endpoints[endpoint], endpoint)


class TestPayrollPrintSecurity(UnitTestCase):
	def setUp(self):
		self.app_path = Path(frappe.get_app_path("za_local_payroll"))
		self.payload = '<img src=x onerror="alert(1)">'

	def _assert_escaped(self, template_name, doc):
		template = (self.app_path / "templates" / "print_format" / f"{template_name}.html").read_text(
			encoding="utf-8"
		)
		rendered = frappe.render_template(template, {"doc": doc})
		self.assertNotIn(self.payload, rendered)
		self.assertNotIn("<img src=x", rendered)
		self.assertIn("&lt;img", rendered)

	def test_print_format_json_is_synchronized_with_canonical_source(self):
		for template_name in (
			"sa_salary_slip",
			"sa_emp201_submission",
			"sa_emp501_reconciliation",
		):
			source = (
				(self.app_path / "templates" / "print_format" / f"{template_name}.html")
				.read_text(encoding="utf-8")
				.rstrip("\n")
			)
			print_format = (
				self.app_path / "sa_payroll" / "print_format" / template_name / f"{template_name}.json"
			)
			self.assertEqual(source, json.loads(print_format.read_text(encoding="utf-8"))["html"])

	def test_salary_slip_escapes_document_and_component_text(self):
		doc = frappe._dict(
			company=self.payload,
			name=self.payload,
			currency="ZAR",
			docstatus=0,
			employee=self.payload,
			employee_name=self.payload,
			earnings=[frappe._dict(salary_component=self.payload, amount=1, year_to_date=1)],
			deductions=[frappe._dict(salary_component=self.payload, amount=1, year_to_date=1)],
			company_contribution=[frappe._dict(salary_component=self.payload, amount=1)],
		)
		self._assert_escaped("sa_salary_slip", doc)

	def test_emp201_escapes_document_text(self):
		doc = frappe._dict(
			company=self.payload,
			company_name=self.payload,
			name=self.payload,
			status=self.payload,
			docstatus=0,
		)
		self._assert_escaped("sa_emp201_submission", doc)

	def test_emp501_escapes_document_and_child_row_text(self):
		doc = frappe._dict(
			company=self.payload,
			company_name=self.payload,
			name=self.payload,
			status=self.payload,
			docstatus=0,
			emp201_submissions=[frappe._dict(emp201_submission=self.payload)],
			irp5_certificates=[
				frappe._dict(
					irp5_certificate=self.payload,
					employee=self.payload,
					employee_name=self.payload,
					status=self.payload,
				)
			],
		)
		self._assert_escaped("sa_emp501_reconciliation", doc)


def _call_blocks(source):
	"""Yield the text of each ``frappe.call({ ... })`` argument, found by brace matching."""
	for match in re.finditer(r"frappe\.call\(\s*\{", source):
		depth = 0
		for index in range(match.end() - 1, len(source)):
			if source[index] == "{":
				depth += 1
			elif source[index] == "}":
				depth -= 1
				if depth == 0:
					yield source[match.end() - 1 : index + 1]
					break


class TestClientCallVerbs(UnitTestCase):
	"""``frappe.call`` sends POST unless told otherwise, and the server refuses a verb it did not allow.

	A GET-only endpoint called without ``type: "GET"`` fails with "Not permitted", which is how the
	EMP501 form stopped filling its dates and reference numbers.
	"""

	def _client_files(self):
		app_path = Path(frappe.get_app_path("za_local_payroll"))
		return [p for p in app_path.rglob("*.js") if "node_modules" not in p.parts and "dist" not in p.parts]

	def test_get_only_endpoints_are_called_with_type_get(self):
		get_paths = {f"za_local_payroll.{name}" for name in GET_ENDPOINTS if not _is_class_method(name)}
		offenders = []
		for path in self._client_files():
			for block in _call_blocks(path.read_text(encoding="utf-8")):
				method = re.search(r"method\s*:\s*['\"]([\w.]+)['\"]", block)
				if not method or method.group(1) not in get_paths:
					continue
				if not re.search(r"type\s*:\s*['\"]GET['\"]", block):
					offenders.append(f"{path.name}: {method.group(1)}")
		self.assertEqual([], offenders, "GET-only endpoints are called with the default POST")

	def test_post_endpoints_are_not_called_with_type_get(self):
		post_paths = {f"za_local_payroll.{name}" for name in POST_ENDPOINTS if not _is_class_method(name)}
		offenders = []
		for path in self._client_files():
			for block in _call_blocks(path.read_text(encoding="utf-8")):
				method = re.search(r"method\s*:\s*['\"]([\w.]+)['\"]", block)
				if method and method.group(1) in post_paths and re.search(r"type\s*:\s*['\"]GET['\"]", block):
					offenders.append(f"{path.name}: {method.group(1)}")
		self.assertEqual([], offenders)

	def test_get_only_document_methods_are_not_called_through_frm_call(self):
		"""``frm.call`` posts, so a GET-only document method behind it can never succeed."""
		names = {name.rsplit(".", 1)[1] for name in GET_ENDPOINTS if _is_class_method(name)}
		offenders = []
		for path in self._client_files():
			source = path.read_text(encoding="utf-8")
			for name in names:
				if re.search(rf"frm\.call\(\s*['\"]{name}['\"]", source):
					offenders.append(f"{path.name}: {name}")
		self.assertEqual([], offenders)


def _is_class_method(qualified_name):
	"""A dotted endpoint name whose second-to-last segment is a class (CamelCase)."""
	return qualified_name.rsplit(".", 2)[-2][:1].isupper()


class TestEMP501FormEndpoints(UnitTestCase):
	"""The EMP501 form fills its dates and SARS reference numbers through two GET endpoints."""

	module = "za_local_payroll.sa_payroll.doctype.emp501_reconciliation.emp501_reconciliation"

	def _fiscal_year(self, start="2026-03-01", end="2027-02-28"):
		return frappe._dict(year_start_date=start, year_end_date=end)

	def test_the_server_allows_get_and_refuses_the_default_post(self):
		from frappe.handler import is_valid_http_method

		from za_local_payroll.sa_payroll.doctype.emp501_reconciliation import emp501_reconciliation as module

		for function in (module.get_period_dates, module.get_company_tax_details):
			with patch.object(frappe.local, "request", SimpleNamespace(method="GET"), create=True):
				is_valid_http_method(function)
			with patch.object(frappe.local, "request", SimpleNamespace(method="POST"), create=True):
				with self.assertRaises(frappe.PermissionError):
					is_valid_http_method(function)

	def test_interim_period_is_the_first_six_months_of_the_tax_year(self):
		from za_local_payroll.sa_payroll.doctype.emp501_reconciliation.emp501_reconciliation import (
			get_period_dates,
		)

		with patch("frappe.get_doc", return_value=self._fiscal_year()):
			dates = get_period_dates("2026-27", "Interim")
		self.assertEqual("2026-03-01", str(dates["from_date"]))
		self.assertEqual("2026-08-31", str(dates["to_date"]))

	def test_final_period_runs_to_the_end_of_february(self):
		from za_local_payroll.sa_payroll.doctype.emp501_reconciliation.emp501_reconciliation import (
			get_period_dates,
		)

		with patch("frappe.get_doc", return_value=self._fiscal_year()):
			dates = get_period_dates("2026-27", "Final")
		self.assertEqual("2026-03-01", str(dates["from_date"]))
		self.assertEqual("2027-02-28", str(dates["to_date"]))

	def test_a_calendar_year_is_not_a_sars_tax_year(self):
		from za_local_payroll.sa_payroll.doctype.emp501_reconciliation.emp501_reconciliation import (
			get_period_dates,
		)

		with patch("frappe.get_doc", return_value=self._fiscal_year("2026-01-01", "2026-12-31")):
			with self.assertRaises(frappe.ValidationError):
				get_period_dates("2026", "Interim")

	def test_company_tax_details_return_the_three_reference_numbers(self):
		from za_local_payroll.sa_payroll.doctype.emp501_reconciliation.emp501_reconciliation import (
			get_company_tax_details,
		)

		details = frappe._dict(
			za_paye_reference_number="7123456789",
			za_sdl_reference_number="L123456789",
			za_uif_reference_number="U123456789",
		)
		with (
			patch("frappe.has_permission", return_value=True),
			patch("frappe.db.get_value", return_value=details),
		):
			result = get_company_tax_details("Test Company")
		self.assertEqual(
			{"za_paye_reference_number", "za_sdl_reference_number", "za_uif_reference_number"}, set(result)
		)

	def test_company_tax_details_need_read_permission_on_the_company(self):
		from za_local_payroll.sa_payroll.doctype.emp501_reconciliation.emp501_reconciliation import (
			get_company_tax_details,
		)

		with patch("frappe.has_permission", return_value=False), patch("frappe.db.get_value") as get_value:
			with self.assertRaises(frappe.PermissionError):
				get_company_tax_details("Test Company")
		get_value.assert_not_called()
