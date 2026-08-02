"""Security regressions for RPC verbs and statutory print formats."""

import ast
import json
from pathlib import Path

import frappe
from frappe.tests.classes import UnitTestCase

GET_ENDPOINTS = {
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
}

POST_ENDPOINTS = {
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
