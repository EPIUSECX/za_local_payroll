"""Real ERPNext/HRMS lifecycle coverage for the South African payroll controls."""

from calendar import monthrange

import frappe
from frappe.tests.classes import IntegrationTestCase
from frappe.utils import flt, getdate
from hrms.payroll.doctype.salary_slip.salary_slip import make_salary_slip_from_timesheet
from za_local_core.tests.utils import ensure_gender

from za_local_payroll.setup.masters import repair_salary_component_accounts, seed_payroll_masters
from za_local_payroll.setup.statutory import ensure_company_tax_configuration


class TestSouthAfricanPayrollLifecycle(IntegrationTestCase):
	"""Exercise payroll without replacing the HRMS calculation or persistence path."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.suffix = frappe.generate_hash(length=5).upper()
		cls.company = f"_ZA Payroll Lifecycle {cls.suffix}"
		cls.abbr = f"Z{cls.suffix[:4]}"
		cls.payroll_payable = None
		cls.bank_gl_account = None
		cls.company_bank_account = None
		cls.cost_center = None
		cls.employees = {}
		cls._stage_erpnext_wizard_fixtures()
		cls._stage_company_and_statutory_masters()
		cls._stage_salary_components()
		cls._stage_employees_and_bank_accounts()
		cls.monthly_structure = cls._make_monthly_structure()
		cls.timesheet_structure = cls._make_timesheet_structure()
		cls._make_assignments()
		cls._make_additional_salaries()

	@classmethod
	def _stage_erpnext_wizard_fixtures(cls):
		"""Records the ERPNext setup wizard creates that a bare CI site lacks.

		Staging an employee address needs a default Address Template, and no app in
		this suite owns one, so on a site that never ran a wizard the class fails to
		set up for a reason unrelated to payroll.
		"""
		if not frappe.db.exists("Address Template", {"is_default": 1}):
			frappe.get_doc(
				{
					"doctype": "Address Template",
					"country": "South Africa",
					"is_default": 1,
					"template": "{{ address_line1 }}<br>{{ city }}<br>{{ country }}",
				}
			).insert(ignore_permissions=True)

	@classmethod
	def _stage_company_and_statutory_masters(cls):
		template_company = frappe.db.get_value("Company", {}, "name", order_by="creation asc")
		if not template_company:
			# Importing the HRMS test utilities provisions ERPNext's supported test company.
			# Only do this on a genuinely empty CI site: its generic fiscal-year fixture can
			# overlap a customer's already-configured South African fiscal year.
			from hrms.tests.utils import BootStrapTestData

			BootStrapTestData()
			template_company = "_Test Company"

		company = frappe.new_doc("Company")
		company.company_name = cls.company
		company.abbr = cls.abbr
		company.default_currency = "ZAR"
		company.country = "South Africa"
		company.create_chart_of_accounts_based_on = "Existing Company"
		company.existing_company = template_company
		company.insert(ignore_permissions=True)

		if not frappe.db.exists("Fiscal Year", "2026-2027"):
			# Scope to this company: a CI site bootstrapped by HRMS already holds a
			# generic January-December fiscal year that overlaps the South African one.
			frappe.get_doc(
				{
					"doctype": "Fiscal Year",
					"year": "2026-2027",
					"year_start_date": "2026-03-01",
					"year_end_date": "2027-02-28",
					"companies": [{"company": cls.company}],
				}
			).insert(ignore_permissions=True)

		cls._make_account("Salaries and Wages", "Expense")
		cls._make_account("UIF Employer Expense", "Expense")
		cls._make_account("SDL Expense", "Expense")
		cls._make_account("PAYE Payable - SARS", "Liability")
		cls._make_account("UIF Employee Contribution", "Liability")
		cls.payroll_payable = cls._make_account("Payroll Payable", "Liability", account_type="Payable")
		cls.bank_gl_account = cls._make_account("Payroll Bank", "Asset", account_type="Bank")
		cls.cost_center = frappe.db.get_value(
			"Cost Center", {"company": cls.company, "is_group": 0}, "name", order_by="lft asc"
		)
		frappe.db.set_value(
			"Company",
			cls.company,
			{
				"default_payroll_payable_account": cls.payroll_payable,
				"za_paye_reference_number": "7123456789",
				"za_sdl_reference_number": "L123456789",
				"za_uif_reference_number": "U123456789",
			},
			update_modified=False,
		)
		cls._make_holiday_list()
		ensure_company_tax_configuration(cls.company)
		seed_payroll_masters()
		repair_salary_component_accounts(cls.company)
		frappe.db.set_single_value("Payroll Settings", "payroll_based_on", "Leave")
		frappe.db.set_single_value("Payroll Settings", "email_salary_slip_to_employee", 0)
		frappe.db.set_single_value(
			"Payroll Settings", "process_payroll_accounting_entry_based_on_employee", 0
		)
		frappe.db.set_single_value("Payroll Settings", "za_eti_unregulated_minimum_monthly_wage", 2500)

	@classmethod
	def _make_account(cls, account_name, root_type, account_type=None):
		existing = frappe.db.get_value(
			"Account",
			{"company": cls.company, "account_name": account_name, "is_group": 0},
			"name",
		)
		if existing:
			# ERPNext's standard chart already ships names such as "Payroll Payable"
			# without an account type; HRMS rejects those for payroll.
			if account_type and frappe.db.get_value("Account", existing, "account_type") != account_type:
				frappe.db.set_value("Account", existing, "account_type", account_type)
			return existing
		parent = frappe.db.get_value(
			"Account",
			{"company": cls.company, "root_type": root_type, "is_group": 1},
			"name",
			order_by="lft desc",
		)
		doc = frappe.get_doc(
			{
				"doctype": "Account",
				"account_name": account_name,
				"company": cls.company,
				"parent_account": parent,
				"is_group": 0,
				"account_type": account_type,
			}
		)
		doc.insert(ignore_permissions=True)
		return doc.name

	@classmethod
	def _make_holiday_list(cls):
		name = f"ZA Payroll Lifecycle Calendar {cls.suffix}"
		doc = frappe.get_doc(
			{
				"doctype": "Holiday List",
				"holiday_list_name": name,
				"from_date": "2026-03-01",
				"to_date": "2027-02-28",
			}
		)
		doc.insert(ignore_permissions=True)
		frappe.db.set_value("Company", cls.company, "default_holiday_list", doc.name)
		assignment = frappe.get_doc(
			{
				"doctype": "Holiday List Assignment",
				"applicable_for": "Company",
				"assigned_to": cls.company,
				"holiday_list": doc.name,
				"from_date": doc.from_date,
			}
		)
		assignment.insert(ignore_permissions=True)
		assignment.submit()
		cls.holiday_list = doc.name

	@classmethod
	def _stage_salary_components(cls):
		expense = frappe.db.get_value(
			"Account", {"company": cls.company, "account_name": "Salaries and Wages"}, "name"
		)
		for component, updates in {
			"Basic": {
				"za_sars_payroll_code": "3601",
				"za_payroll_treatment": "Regular Remuneration",
				"za_paye_inclusion_percentage": 100,
				"za_uif_applicable": 1,
				"za_sdl_applicable": 1,
				"za_coida_applicable": 1,
				"za_eti_wage_component": 1,
			},
			"PAYE": {"za_sars_payroll_code": "4102"},
			"UIF Employee Contribution": {"za_sars_payroll_code": "4141"},
			"UIF Employer Contribution": {"za_sars_payroll_code": "4141"},
			"SDL Contribution": {"za_sars_payroll_code": "4142"},
		}.items():
			frappe.db.set_value("Salary Component", component, updates, update_modified=False)

		cls.allowance_component = cls._make_component(
			f"ZA Recurring Allowance {cls.suffix}", "ZARA", "3702", expense
		)
		cls.timesheet_component = cls._make_component(
			f"ZA Timesheet Pay {cls.suffix}", "ZATP", "3601", expense, eti_wage=True
		)
		repair_salary_component_accounts(cls.company)
		for component in (cls.allowance_component, cls.timesheet_component):
			doc = frappe.get_doc("Salary Component", component)
			doc.append("accounts", {"company": cls.company, "account": expense})
			doc.save(ignore_permissions=True)

	@classmethod
	def _make_component(cls, name, abbreviation, code, account, eti_wage=False):
		doc = frappe.get_doc(
			{
				"doctype": "Salary Component",
				"salary_component": name,
				"salary_component_abbr": f"{abbreviation}{cls.suffix[:2]}",
				"type": "Earning",
				"is_tax_applicable": 1,
				"depends_on_payment_days": 0,
				"za_sars_payroll_code": code,
				"za_payroll_treatment": "Regular Remuneration",
				"za_paye_inclusion_percentage": 100,
				"za_uif_applicable": 1,
				"za_sdl_applicable": 1,
				"za_coida_applicable": 1,
				"za_eti_wage_component": int(eti_wage),
				"accounts": [{"company": cls.company, "account": account}],
			}
		)
		doc.insert(ignore_permissions=True)
		return doc.name

	@classmethod
	def _stage_employees_and_bank_accounts(cls):
		if not frappe.db.exists("Bank Account Type", "Current"):
			frappe.get_doc({"doctype": "Bank Account Type", "account_type": "Current"}).insert(
				ignore_permissions=True
			)
		bank_name = f"ZA Payroll Test Bank {cls.suffix}"
		frappe.get_doc({"doctype": "Bank", "bank_name": bank_name}).insert(ignore_permissions=True)
		cls.company_bank_account = (
			frappe.get_doc(
				{
					"doctype": "Bank Account",
					"account_name": f"ZA Company Payroll {cls.suffix}",
					"bank": bank_name,
					"account_type": "Current",
					"is_company_account": 1,
					"company": cls.company,
					"account": cls.bank_gl_account,
					"bank_account_no": "62000031451",
					"branch_code": "250655",
				}
			)
			.insert(ignore_permissions=True)
			.name
		)

		employee_type = f"ZA Full Time {cls.suffix}"
		frappe.get_doc(
			{
				"doctype": "Employee Type",
				"employee_type": employee_type,
				"payroll_payable_account": cls.payroll_payable,
			}
		).insert(ignore_permissions=True)

		for key, dob, joining_date, hours, sequence in (
			("ordinary", "1980-01-15", "2020-01-01", 160, 5101),
			("eti", "2002-05-10", "2026-08-01", 160, 5102),
			("timesheet", "1985-07-20", "2020-01-01", 80, 5103),
		):
			employee = frappe.get_doc(
				{
					"doctype": "Employee",
					"first_name": "ZA",
					"last_name": f"{key.title()} {cls.suffix}",
					"gender": ensure_gender("Male"),
					"date_of_birth": dob,
					"date_of_joining": joining_date,
					"company": cls.company,
					"status": "Active",
					"personal_email": f"za.{key}.{cls.suffix.lower()}@example.test",
					"holiday_list": cls.holiday_list,
					"za_employee_type": employee_type,
					"za_id_number": cls._make_sa_id(dob, sequence),
					"za_income_tax_reference_number": f"9{sequence:09d}"[-10:],
					"za_hours_per_month": hours,
					"za_eti_minimum_wage_basis": "No Regulating Measure or NMW Exempt",
				}
			).insert(ignore_permissions=True)
			address = frappe.get_doc(
				{
					"doctype": "Address",
					"address_title": employee.employee_name,
					"address_type": "Personal",
					"address_line1": f"{sequence} Compliance Street",
					"city": "Johannesburg",
					"state": "Gauteng",
					"pincode": "2001",
					"country": "South Africa",
					"links": [{"link_doctype": "Employee", "link_name": employee.name}],
				}
			).insert(ignore_permissions=True)
			account = frappe.get_doc(
				{
					"doctype": "Bank Account",
					"account_name": f"ZA {key.title()} Payroll {cls.suffix}",
					"bank": bank_name,
					"account_type": "Current",
					"party_type": "Employee",
					"party": employee.name,
					"bank_account_no": f"62{sequence:09d}"[-11:],
					"branch_code": "250655",
				}
			).insert(ignore_permissions=True)
			frappe.db.set_value(
				"Employee",
				employee.name,
				{
					"za_residential_address": address.name,
					"za_payroll_payable_bank_account": account.name,
					"za_bank_account_type": "Cheque",
					"za_bank_account_holder_name": employee.employee_name,
					"za_bank_account_holder_relationship": "Employee",
					"za_not_paid_electronically": 0,
				},
				update_modified=False,
			)
			cls.employees[key] = employee.name

	@staticmethod
	def _make_sa_id(date_of_birth, sequence):
		dob = getdate(date_of_birth)
		prefix = f"{dob:%y%m%d}{sequence:04d}08"
		total = 0
		for index, digit in enumerate(prefix):
			number = int(digit)
			if index % 2:
				number *= 2
				number = number if number <= 9 else number - 9
			total += number
		return f"{prefix}{(10 - total % 10) % 10}"

	@classmethod
	def _make_monthly_structure(cls):
		doc = frappe.get_doc(
			{
				"doctype": "Salary Structure",
				"name": f"ZA Monthly Lifecycle {cls.suffix}",
				"company": cls.company,
				"currency": "ZAR",
				"payroll_frequency": "Monthly",
				"payment_account": cls.payroll_payable,
				"earnings": [
					{
						"salary_component": "Basic",
						"amount_based_on_formula": 1,
						"formula": "base",
					}
				],
				"deductions": [{"salary_component": "PAYE"}],
			}
		)
		doc.insert(ignore_permissions=True)
		doc.submit()
		return doc.name

	@classmethod
	def _make_timesheet_structure(cls):
		doc = frappe.get_doc(
			{
				"doctype": "Salary Structure",
				"name": f"ZA Timesheet Lifecycle {cls.suffix}",
				"company": cls.company,
				"currency": "ZAR",
				"payroll_frequency": "Monthly",
				"payment_account": cls.payroll_payable,
				"salary_slip_based_on_timesheet": 1,
				"salary_component": cls.timesheet_component,
				"hour_rate": 500,
				"deductions": [{"salary_component": "PAYE"}],
			}
		)
		doc.insert(ignore_permissions=True)
		doc.submit()
		return doc.name

	@classmethod
	def _make_assignments(cls):
		period = frappe.db.get_value(
			"Payroll Period",
			{
				"company": cls.company,
				"start_date": ["<=", "2026-08-31"],
				"end_date": [">=", "2026-08-31"],
			},
			"name",
		)
		slab = frappe.db.get_value(
			"Income Tax Slab",
			{
				"company": cls.company,
				"effective_from": ["<=", "2026-08-31"],
				"docstatus": 1,
			},
			"name",
			order_by="effective_from desc",
		)
		for employee, structure, base in (
			(cls.employees["ordinary"], cls.monthly_structure, 30000),
			(cls.employees["eti"], cls.monthly_structure, 6000),
			(cls.employees["timesheet"], cls.timesheet_structure, 0),
		):
			doc = frappe.get_doc(
				{
					"doctype": "Salary Structure Assignment",
					"employee": employee,
					"salary_structure": structure,
					"from_date": "2026-08-01",
					"company": cls.company,
					"base": base,
					"income_tax_slab": slab,
					"payroll_payable_account": cls.payroll_payable,
					"payroll_period": period,
				}
			)
			doc.insert(ignore_permissions=True)
			doc.submit()

	@classmethod
	def _make_additional_salaries(cls):
		for values in (
			{
				"salary_component": cls.allowance_component,
				"amount": 1500,
				"is_recurring": 1,
				"from_date": "2026-08-01",
				"to_date": "2027-02-28",
			},
			{
				"salary_component": "Basic",
				"amount": 35000,
				"payroll_date": "2026-08-31",
				"overwrite_salary_structure_amount": 1,
			},
		):
			doc = frappe.get_doc(
				{
					"doctype": "Additional Salary",
					"employee": cls.employees["ordinary"],
					"company": cls.company,
					**values,
				}
			)
			doc.insert(ignore_permissions=True)
			doc.submit()

	def test_full_payroll_reporting_payment_and_amendment_lifecycle(self):
		payroll_entry = self._run_monthly_payroll()
		slips = {
			row.employee: frappe.get_doc("Salary Slip", row.name)
			for row in frappe.get_all(
				"Salary Slip",
				filters={"payroll_entry": payroll_entry.name, "docstatus": 1},
				fields=["name", "employee"],
			)
		}
		ordinary = slips[self.employees["ordinary"]]
		eti = slips[self.employees["eti"]]

		basic_rows = [row for row in ordinary.earnings if row.salary_component == "Basic"]
		self.assertEqual(1, len(basic_rows))
		self.assertEqual(35000, flt(basic_rows[0].amount, 2))
		self.assertEqual(
			1500,
			flt(
				next(
					row.amount
					for row in ordinary.earnings
					if row.salary_component == self.allowance_component
				),
				2,
			),
		)
		self.assertEqual(177.12, self._component_amount(ordinary, "deductions", "4141"))
		self.assertEqual(177.12, self._component_amount(ordinary, "company_contribution", "4141"))
		self.assertEqual(365, self._component_amount(ordinary, "company_contribution", "4142"))
		self.assertEqual(60, self._component_amount(eti, "deductions", "4141"))
		self.assertEqual(60, self._component_amount(eti, "company_contribution", "4141"))
		self.assertEqual(1125, flt(eti.za_monthly_eti, 2))

		contribution_je = self._get_company_contribution_je(payroll_entry.name)
		self.assertTrue(contribution_je)
		self.assertEqual(
			contribution_je,
			payroll_entry._ensure_company_contribution_entry(),
			"The retry must reuse the submitted employer-contribution accrual",
		)
		self.assertEqual(
			662.12,
			flt(frappe.db.get_value("Journal Entry", contribution_je, "total_debit"), 2),
		)

		timesheet_slip = self._run_timesheet_payroll()
		timesheet_rows = [
			row for row in timesheet_slip.earnings if row.salary_component == self.timesheet_component
		]
		self.assertTrue(timesheet_slip.salary_slip_based_on_timesheet)
		self.assertEqual(8, flt(timesheet_slip.total_working_hours, 2))
		self.assertEqual(500, flt(timesheet_slip.hour_rate, 2))
		self.assertEqual(1, len(timesheet_rows))
		self.assertEqual(4000, flt(timesheet_rows[0].amount, 2))
		self.assertEqual(4000, flt(timesheet_slip.gross_pay, 2))
		self.assertEqual(40, self._component_amount(timesheet_slip, "deductions", "4141"))

		emp201 = self._submit_emp201()
		self.assertEqual(554.24, flt(emp201.uif_payable, 2))
		self.assertEqual(465, flt(emp201.sdl_payable, 2))
		self.assertEqual(1125, flt(emp201.eti_generated_current_month, 2))

		certificate = self._generate_company_scoped_irp5()
		self.assertEqual(self.company, certificate.company)
		self.assertEqual(
			[ordinary.name],
			[
				row.name
				for row in certificate._get_salary_slips(
					self.employees["ordinary"], "2026-03-01", "2026-08-31"
				)
			],
		)
		wrong_company = frappe.new_doc("IRP5 Certificate")
		wrong_company.company = "_Test Company"
		self.assertEqual(
			[],
			wrong_company._get_salary_slips(self.employees["ordinary"], "2026-03-01", "2026-08-31"),
		)

		batch = self._submit_payment_batch(payroll_entry.name)
		with self.assertRaises((frappe.ValidationError, frappe.DuplicateEntryError)):
			self._new_payment_batch(payroll_entry.name).insert(ignore_permissions=True)
		batch.cancel()
		amended_batch = frappe.copy_doc(batch)
		amended_batch.docstatus = 0
		amended_batch.amended_from = batch.name
		amended_batch.insert(ignore_permissions=True)
		amended_batch.submit()

		with self.assertRaises(frappe.ValidationError):
			payroll_entry.cancel()
		payroll_entry.reload()
		amended_batch.cancel()
		payroll_entry.cancel()
		self.assertEqual(2, frappe.db.get_value("Journal Entry", contribution_je, "docstatus"))

		amended_payroll = frappe.copy_doc(payroll_entry)
		amended_payroll.docstatus = 0
		amended_payroll.amended_from = payroll_entry.name
		amended_payroll.insert(ignore_permissions=True)
		amended_payroll.submit()
		amended_payroll.submit_salary_slips()
		amended_payroll.reload()
		self.assertEqual(1, amended_payroll.docstatus)
		amended_contribution_je = self._get_company_contribution_je(amended_payroll.name)
		self.assertTrue(amended_contribution_je)
		self.assertNotEqual(contribution_je, amended_contribution_je)

		self.assertNotIn(
			"lending",
			frappe.get_installed_apps(),
			"Loan lifecycle coverage belongs in the optional Lending-enabled test matrix",
		)

	def _run_monthly_payroll(self):
		doc = frappe.get_doc(
			{
				"doctype": "Payroll Entry",
				"company": self.company,
				"posting_date": "2026-08-31",
				"start_date": "2026-08-01",
				"end_date": "2026-08-31",
				"payroll_frequency": "Monthly",
				"payroll_payable_account": self.payroll_payable,
				"payment_account": self.bank_gl_account,
				"currency": "ZAR",
				"exchange_rate": 1,
				"cost_center": self.cost_center,
				"employees": [
					{"employee": self.employees["ordinary"]},
					{"employee": self.employees["eti"]},
				],
			}
		)
		doc.insert(ignore_permissions=True)
		doc.submit()
		doc.submit_salary_slips()
		doc.reload()
		self.assertFalse(doc.error_message, doc.error_message)
		return doc

	def _run_timesheet_payroll(self):
		activity_type = f"ZA Payroll Work {self.suffix}"
		frappe.get_doc(
			{
				"doctype": "Activity Type",
				"activity_type": activity_type,
				"costing_rate": 0,
				"billing_rate": 0,
			}
		).insert(ignore_permissions=True)
		timesheet = frappe.get_doc(
			{
				"doctype": "Timesheet",
				"employee": self.employees["timesheet"],
				"company": self.company,
				"time_logs": [
					{
						"activity_type": activity_type,
						"from_time": "2026-08-15 08:00:00",
						"to_time": "2026-08-15 16:00:00",
						"hours": 8,
					}
				],
			}
		)
		timesheet.insert(ignore_permissions=True)
		timesheet.submit()
		slip = make_salary_slip_from_timesheet(timesheet.name)
		slip.insert(ignore_permissions=True)
		slip.submit()
		return slip

	def _submit_emp201(self):
		doc = frappe.get_doc(
			{
				"doctype": "EMP201 Submission",
				"company": self.company,
				"fiscal_year": "2026-2027",
				"month": "August",
				"posting_date": "2026-08-31",
			}
		)
		self.assertEqual(
			"za_local_payroll.sa_payroll.doctype.emp201_submission.emp201_submission",
			doc.__class__.__module__,
		)
		doc.insert(ignore_permissions=True)
		values = doc.fetch_emp201_data()
		self.assertTrue(values)
		doc.update(values)
		doc.save(ignore_permissions=True)
		doc.uif_payable = 1
		doc.sdl_payable = 1
		doc.eti_generated_current_month = 1
		doc.submit()
		doc.reload()
		return doc

	def _generate_company_scoped_irp5(self):
		doc = frappe.get_doc(
			{
				"doctype": "IRP5 Certificate",
				"employee": self.employees["ordinary"],
				"company": self.company,
				"tax_year": "2026-2027",
				"from_date": "2026-03-01",
				"to_date": "2026-08-31",
				"reconciliation_period": "Interim",
				"certificate_type": "IRP5",
			}
		)
		doc.generate_certificate_data()
		doc.insert(ignore_permissions=True)
		return doc

	def _new_payment_batch(self, payroll_entry):
		return frappe.get_doc(
			{
				"doctype": "Payroll Payment Batch",
				"payroll_entry": payroll_entry,
				"payment_date": "2026-08-31",
				"bank_account": self.company_bank_account,
				"bank_format": "FNB OBE CSV",
			}
		)

	def _submit_payment_batch(self, payroll_entry):
		doc = self._new_payment_batch(payroll_entry)
		doc.insert(ignore_permissions=True)
		doc.submit()
		return doc

	@staticmethod
	def _component_amount(slip, table_name, code):
		return flt(
			sum(
				flt(row.amount)
				for row in slip.get(table_name) or []
				if frappe.db.get_value("Salary Component", row.salary_component, "za_sars_payroll_code")
				== code
			),
			2,
		)

	@staticmethod
	def _get_company_contribution_je(payroll_entry):
		return frappe.db.get_value(
			"Journal Entry Account",
			{
				"reference_type": "Payroll Entry",
				"reference_name": payroll_entry,
				"docstatus": 1,
				"parent": [
					"in",
					frappe.get_all(
						"Journal Entry",
						filters={"za_is_company_contribution": 1, "docstatus": 1},
						pluck="name",
					),
				],
			},
			"parent",
		)
