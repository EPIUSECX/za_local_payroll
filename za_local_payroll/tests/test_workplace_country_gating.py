"""BCEA and COIDA rules must not reach companies in other countries.

Employee Separation enforces South African termination law. Leave Application
is already opt-in through the governed ``za_bcea_compliant`` Leave Type flag;
both behaviours are pinned here so neither can regress into a global rule.
"""

import frappe
from frappe.tests.classes import IntegrationTestCase
from za_local_core.tests.utils import ensure_company

from za_local_payroll.overrides.employee_separation import ZAEmployeeSeparation
from za_local_payroll.overrides.leave_application import ZALeaveApplication


class TestWorkplaceCountryGating(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.suffix = frappe.generate_hash(length=5).upper()
		cls.foreign_company = f"_ZA Workplace Foreign {cls.suffix}"
		cls.sa_company = f"_ZA Workplace Local {cls.suffix}"
		ensure_company(cls.foreign_company, f"W{cls.suffix[:4]}", "Namibia", "NAD")
		ensure_company(cls.sa_company, f"S{cls.suffix[:4]}", "South Africa", "ZAR")

	def test_separation_gate_follows_company_country(self):
		separation = frappe.new_doc("Employee Separation")
		separation.company = self.foreign_company
		self.assertFalse(ZAEmployeeSeparation.za_localisation_applies.fget(separation))
		separation.company = self.sa_company
		self.assertTrue(ZAEmployeeSeparation.za_localisation_applies.fget(separation))

	def test_separation_without_company_is_not_localised(self):
		"""HRMS reports its own missing mandatory company; localisation stays quiet.

		``frappe.new_doc`` applies the session default company, so the blank
		case is asserted explicitly rather than relying on a fresh document.
		"""
		separation = frappe.new_doc("Employee Separation")
		separation.company = None
		separation.employee = None
		self.assertFalse(ZAEmployeeSeparation.za_localisation_applies.fget(separation))

	def test_leave_application_stays_opt_in_through_governed_leave_type(self):
		"""An ungoverned Leave Type must return no BCEA rules for any company."""
		leave_type_name = f"_ZA Ungoverned Leave {self.suffix}"
		if not frappe.db.exists("Leave Type", leave_type_name):
			frappe.get_doc(
				{"doctype": "Leave Type", "leave_type_name": leave_type_name, "za_bcea_compliant": 0}
			).insert(ignore_permissions=True)
		application = frappe.new_doc("Leave Application")
		application.leave_type = leave_type_name
		self.assertIsNone(ZALeaveApplication._get_governed_leave_type(application))
