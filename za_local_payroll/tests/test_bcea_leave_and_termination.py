"""Regression tests for governed BCEA leave and termination calculations."""

from __future__ import annotations

from unittest.mock import patch

import frappe
from frappe.tests.classes import IntegrationTestCase, UnitTestCase
from frappe.utils import getdate
from za_local_core.tests.utils import ensure_gender

from za_local_payroll.overrides.employee_separation import ZAEmployeeSeparation
from za_local_payroll.overrides.leave_application import (
	SICK_LEAVE_CATEGORY,
	ZALeaveApplication,
	count_distinct_leave_occasions,
)
from za_local_payroll.utils.termination_utils import (
	OPERATIONAL_DISMISSAL,
	calculate_bcea_notice_period,
	calculate_completed_service_years,
	calculate_leave_payout_on_termination,
	calculate_severance_pay,
)


class TestBCEATermination(UnitTestCase):
	def test_completed_service_years_use_anniversary_boundaries(self):
		self.assertEqual(4, calculate_completed_service_years("2020-03-15", "2025-03-14"))
		self.assertEqual(5, calculate_completed_service_years("2020-03-15", "2025-03-15"))

	def test_notice_period_uses_exact_six_and_twelve_month_boundaries(self):
		employee = frappe._dict(name="EMP-001", date_of_joining="2025-01-31")
		self.assertEqual(7, calculate_bcea_notice_period(employee, "2025-07-30"))
		self.assertEqual(14, calculate_bcea_notice_period(employee, "2025-07-31"))
		self.assertEqual(28, calculate_bcea_notice_period(employee, "2026-01-31"))

	def test_severance_fails_closed_without_reviewed_weekly_remuneration(self):
		employee = frappe._dict(name="EMP-001", date_of_joining="2020-03-15")
		with self.assertRaises(frappe.ValidationError):
			calculate_severance_pay(
				employee,
				"2025-03-15",
				OPERATIONAL_DISMISSAL,
				weekly_remuneration=2500,
				remuneration_reviewed=False,
			)

		with patch("za_local_payroll.utils.termination_utils.frappe.get_all") as get_all:
			self.assertEqual(
				12500,
				calculate_severance_pay(
					employee,
					"2025-03-15",
					OPERATIONAL_DISMISSAL,
					weekly_remuneration=2500,
					remuneration_reviewed=True,
				),
			)
		get_all.assert_not_called()

	def test_leave_payout_uses_hrms_ledger_at_actual_termination_date(self):
		with (
			patch(
				"za_local_payroll.utils.termination_utils.frappe.get_all",
				return_value=["Annual Leave", "Annual Carry Forward"],
			) as get_all,
			patch(
				"za_local_payroll.utils.termination_utils.get_leave_balance_on",
				side_effect=[5.5, -2],
			) as get_balance,
		):
			result = calculate_leave_payout_on_termination(
				"EMP-001",
				"2026-04-30",
				daily_remuneration=1200,
				remuneration_reviewed=True,
			)

		self.assertEqual(5.5, result["days"])
		self.assertEqual(6600, result["amount"])
		get_all.assert_called_once_with(
			"Leave Type",
			filters={
				"za_bcea_compliant": 1,
				"za_bcea_leave_category": "Annual Leave",
				"is_lwp": 0,
			},
			pluck="name",
		)
		for call in get_balance.call_args_list:
			self.assertEqual(getdate("2026-04-30"), call.args[2])
			self.assertEqual(getdate("2026-04-30"), call.kwargs["to_date"])

	def test_positive_leave_balance_requires_reviewed_daily_remuneration(self):
		with (
			patch(
				"za_local_payroll.utils.termination_utils.frappe.get_all",
				return_value=["Annual Leave"],
			),
			patch(
				"za_local_payroll.utils.termination_utils.get_leave_balance_on",
				return_value=3,
			),
			self.assertRaises(frappe.ValidationError),
		):
			calculate_leave_payout_on_termination(
				"EMP-001",
				"2026-04-30",
				daily_remuneration=0,
				remuneration_reviewed=False,
			)

	def test_separation_uses_actual_date_not_resignation_letter_date(self):
		doc = frappe.new_doc("Employee Separation")
		doc.resignation_letter_date = "2026-01-01"
		doc.za_termination_date = "2026-04-30"
		termination_date = ZAEmployeeSeparation._set_actual_termination_date(
			doc, frappe._dict(relieving_date="2026-05-31")
		)
		self.assertEqual(getdate("2026-04-30"), termination_date)


class TestBCEALeaveLedgerIntegration(IntegrationTestCase):
	def test_submitted_hrms_allocation_drives_termination_payout(self):
		company = self._get_or_create_company()
		employee = frappe.get_doc(
			{
				"doctype": "Employee",
				"first_name": "_Test BCEA Ledger Employee",
				"company": company,
				"status": "Active",
				"gender": ensure_gender("Female"),
				"date_of_birth": "1990-01-01",
				"date_of_joining": "2020-01-01",
			}
		).insert()
		leave_type = frappe.get_doc(
			{
				"doctype": "Leave Type",
				"leave_type_name": "_Test Governed Annual Leave",
				"za_bcea_compliant": 1,
				"za_bcea_leave_category": "Annual Leave",
			}
		).insert()
		allocation = frappe.get_doc(
			{
				"doctype": "Leave Allocation",
				"employee": employee.name,
				"leave_type": leave_type.name,
				"from_date": "2026-01-01",
				"to_date": "2026-12-31",
				"new_leaves_allocated": 10,
				"total_leaves_allocated": 10,
			}
		).insert()
		allocation.submit()

		result = calculate_leave_payout_on_termination(
			employee,
			"2026-06-30",
			daily_remuneration=1000,
			remuneration_reviewed=True,
		)

		self.assertEqual(10, result["days"])
		self.assertEqual(10000, result["amount"])
		self.assertTrue(
			frappe.db.exists(
				"Leave Ledger Entry",
				{"transaction_name": allocation.name, "docstatus": 1},
			)
		)

	def _get_or_create_company(self):
		company = frappe.db.get_value("Company", {}, "name")
		if company:
			return company

		# ERPNext's Company.on_update builds the default warehouses, and "Goods In
		# Transit" links to Warehouse Type "Transit". That record comes from the setup
		# wizard, which never runs in CI, so inserting a company on a bare site fails
		# on a missing link rather than anything this test is about.
		if not frappe.db.exists("Warehouse Type", "Transit"):
			frappe.get_doc({"doctype": "Warehouse Type", "name": "Transit"}).insert(ignore_permissions=True)

		return (
			frappe.get_doc(
				{
					"doctype": "Company",
					"company_name": "_Test ZA BCEA Ledger Company",
					"abbr": "TZBLC",
					"default_currency": "ZAR",
					"country": "South Africa",
				}
			)
			.insert()
			.name
		)


class TestBCEASickLeave(UnitTestCase):
	def test_touching_applications_are_one_absence_occasion(self):
		applications = [
			frappe._dict(from_date="2026-01-01", to_date="2026-01-02"),
			frappe._dict(from_date="2026-01-03", to_date="2026-01-04"),
			frappe._dict(from_date="2026-02-01", to_date="2026-02-01"),
		]
		self.assertEqual(2, count_distinct_leave_occasions(applications))

	def test_third_sick_leave_occasion_requires_medical_evidence(self):
		doc = frappe.new_doc("Leave Application")
		doc.employee = "EMP-001"
		doc.leave_type = "Medical Absence"
		doc.from_date = "2026-02-20"
		doc.to_date = "2026-02-20"
		doc.total_leave_days = 1
		doc.za_medical_certificate = None
		leave_type = frappe._dict(
			za_bcea_leave_category=SICK_LEAVE_CATEGORY,
			za_medical_certificate_required_after=2,
		)
		prior_applications = [
			frappe._dict(from_date="2026-01-10", to_date="2026-01-10"),
			frappe._dict(from_date="2026-02-01", to_date="2026-02-01"),
		]

		with (
			patch(
				"za_local_payroll.overrides.leave_application.frappe.get_all",
				side_effect=[["Medical Absence"], prior_applications],
			),
			self.assertRaises(frappe.ValidationError),
		):
			ZALeaveApplication.validate_medical_certificate(doc, leave_type)

	def test_calendar_span_and_statutory_threshold_cannot_be_weakened(self):
		doc = frappe.new_doc("Leave Application")
		doc.employee = "EMP-001"
		doc.leave_type = "Medical Absence"
		doc.from_date = "2026-04-03"
		doc.to_date = "2026-04-06"
		doc.total_leave_days = 2
		doc.za_medical_certificate = None
		leave_type = frappe._dict(
			za_bcea_leave_category=SICK_LEAVE_CATEGORY,
			za_medical_certificate_required_after=5,
		)

		with (
			patch(
				"za_local_payroll.overrides.leave_application.frappe.get_all",
				side_effect=[["Medical Absence"], []],
			),
			self.assertRaises(frappe.ValidationError),
		):
			ZALeaveApplication.validate_medical_certificate(doc, leave_type)

	def test_dedicated_medical_evidence_satisfies_control(self):
		doc = frappe.new_doc("Leave Application")
		doc.employee = "EMP-001"
		doc.leave_type = "Medical Absence"
		doc.from_date = "2026-04-01"
		doc.to_date = "2026-04-04"
		doc.total_leave_days = 4
		doc.za_medical_certificate = "/private/files/medical-certificate.pdf"
		leave_type = frappe._dict(
			za_bcea_leave_category=SICK_LEAVE_CATEGORY,
			za_medical_certificate_required_after=2,
		)

		with patch(
			"za_local_payroll.overrides.leave_application.frappe.get_all",
			side_effect=[["Medical Absence"], []],
		):
			ZALeaveApplication.validate_medical_certificate(doc, leave_type)

	def test_governed_category_not_leave_type_name_drives_sick_control(self):
		doc = frappe.new_doc("Leave Application")
		doc.leave_type = "Sick Leave By Name Only"
		doc.total_leave_days = 10
		leave_type = frappe._dict(
			za_bcea_leave_category="Annual Leave",
			za_medical_certificate_required_after=2,
		)
		with patch("za_local_payroll.overrides.leave_application.frappe.get_all") as get_all:
			ZALeaveApplication.validate_medical_certificate(doc, leave_type)
		get_all.assert_not_called()
