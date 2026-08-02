from unittest.mock import Mock, patch

import frappe
from frappe.tests.classes import UnitTestCase


class TestPayrollEntryValidation(UnitTestCase):
	def test_accrual_posts_stock_and_company_contributions_once(self):
		from za_local_payroll.overrides.payroll_entry import PayrollEntry, ZAPayrollEntry

		doc = object.__new__(ZAPayrollEntry)
		doc._ensure_company_contribution_entry = Mock()
		slips = [frappe._dict(name="SAL-0001")]
		with patch.object(PayrollEntry, "make_accrual_jv_entry") as parent:
			ZAPayrollEntry.make_accrual_jv_entry(doc, slips)

		parent.assert_called_once_with(slips)
		doc._ensure_company_contribution_entry.assert_called_once_with()

	def test_legacy_direct_bank_journal_entry_is_retired(self):
		from za_local_payroll.overrides.payroll_entry import ZAPayrollEntry

		doc = object.__new__(ZAPayrollEntry)
		doc.check_permission = Mock()
		with self.assertRaises(frappe.ValidationError):
			ZAPayrollEntry.make_payment_entry(doc, {})
		doc.check_permission.assert_called_once_with("write")

	@patch("za_local_payroll.overrides.payroll_entry.validate_current_tax_configuration")
	def test_salary_slip_creation_validates_statutory_setup_first(self, validate_setup):
		from za_local_payroll.overrides.payroll_entry import ZAPayrollEntry

		doc = object.__new__(ZAPayrollEntry)
		doc.company = "_Test Company"
		doc.end_date = "2026-08-31"
		doc.check_permission = Mock()
		doc.validate_mandatory_fields = Mock(side_effect=frappe.MandatoryError("stop"))
		with self.assertRaises(frappe.MandatoryError):
			ZAPayrollEntry.create_salary_slips(doc)
		validate_setup.assert_called_once_with("_Test Company", "2026-08-31")

	def test_existing_payroll_entry_still_runs_parent_and_sa_validation(self):
		from za_local_payroll.overrides.payroll_entry import PayrollEntry, ZAPayrollEntry

		doc = ZAPayrollEntry({"doctype": "Payroll Entry"})
		doc.name = "PAY-TEST"
		doc.flags.ignore_validate = False
		with (
			patch("za_local_payroll.overrides.payroll_entry.require_hrms"),
			patch.object(PayrollEntry, "validate") as parent_validate,
			patch.object(ZAPayrollEntry, "validate_employee_requirements") as sa_validate,
		):
			doc.validate()

		parent_validate.assert_called_once_with()
		sa_validate.assert_called_once_with()

	def test_employee_requirements_are_loaded_in_one_query(self):
		from za_local_payroll.overrides.payroll_entry import ZAPayrollEntry

		doc = frappe._dict(
			name="PAY-TEST",
			employees=[
				frappe._dict(employee="EMP-0001", employee_name="One"),
				frappe._dict(employee="EMP-0002", employee_name="Two"),
			],
		)
		metadata = [
			frappe._dict(
				name="EMP-0001",
				employee_name="One",
				za_employee_type="Normal Employee",
				za_payroll_payable_bank_account="BANK-1",
			),
			frappe._dict(
				name="EMP-0002",
				employee_name="Two",
				za_employee_type="Normal Employee",
				za_payroll_payable_bank_account="BANK-2",
			),
		]
		with (
			patch(
				"za_local_payroll.overrides.payroll_entry.frappe.get_all", return_value=metadata
			) as get_all,
			patch("za_local_payroll.overrides.payroll_entry.frappe.db.get_value") as get_value,
		):
			ZAPayrollEntry.validate_employee_requirements(doc)

		get_all.assert_called_once()
		get_value.assert_not_called()

	def test_missing_employee_type_message_escapes_employee_name(self):
		from za_local_payroll.overrides.payroll_entry import ZAPayrollEntry

		doc = frappe._dict(
			name="PAY-TEST",
			employees=[frappe._dict(employee="EMP-0001", employee_name="Unsafe")],
		)
		metadata = [
			frappe._dict(
				name="EMP-0001",
				employee_name='<img src=x onerror="alert(1)">',
				za_employee_type=None,
				za_payroll_payable_bank_account="BANK-1",
			),
		]
		with patch("za_local_payroll.overrides.payroll_entry.frappe.get_all", return_value=metadata):
			with self.assertRaises(frappe.ValidationError) as error:
				ZAPayrollEntry.validate_employee_requirements(doc)

		self.assertNotIn("<img", str(error.exception))
		self.assertIn("&lt;img", str(error.exception))
