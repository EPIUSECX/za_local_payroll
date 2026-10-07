"""BCEA leave standards: statutory minimums, service cycles and template policies."""

from __future__ import annotations

from datetime import date
from unittest.mock import patch

import frappe
from frappe.tests.classes import UnitTestCase

from za_local_payroll.overrides.leave_application import ZALeaveApplication
from za_local_payroll.utils import bcea_leave as bcea


class TestBCEALeaveStandards(UnitTestCase):
	def test_standards_cite_a_source_for_every_entitlement(self):
		standards = bcea.get_standards()
		for section in ("annual_leave", "sick_leave", "family_responsibility_leave"):
			self.assertIn(standards[section]["source"], standards["sources"])
			self.assertTrue(standards["sources"][standards[section]["source"]]["url"].startswith("https://"))

	def test_statutory_minimums_by_work_week(self):
		self.assertEqual(15, bcea.annual_leave_days(5))
		self.assertEqual(18, bcea.annual_leave_days(6))
		self.assertEqual(30, bcea.sick_leave_days(5))
		self.assertEqual(36, bcea.sick_leave_days(6))
		self.assertEqual(3, bcea.family_leave_days())
		self.assertEqual(4, bcea.family_leave_min_service_months())

	def test_unsupported_work_week_is_refused(self):
		with self.assertRaises(frappe.ValidationError):
			bcea.annual_leave_days(7)

	def test_annual_cycle_follows_the_service_anniversary(self):
		start, end = bcea.service_cycle("2018-03-01", "2026-10-07", 12)
		self.assertEqual((date(2026, 3, 1), date(2027, 2, 28)), (start, end))
		# The day before the anniversary is still in the previous cycle.
		start, end = bcea.service_cycle("2018-03-15", "2026-03-14", 12)
		self.assertEqual((date(2025, 3, 15), date(2026, 3, 14)), (start, end))

	def test_sick_leave_cycle_is_thirty_six_months(self):
		start, end = bcea.service_cycle("2018-03-01", "2026-10-07", 36)
		self.assertEqual((date(2024, 3, 1), date(2027, 2, 28)), (start, end))
		start, end = bcea.service_cycle("2018-03-01", "2027-03-01", 36)
		self.assertEqual(date(2027, 3, 1), start)

	def test_cycle_handles_month_end_joiners(self):
		# Joined on 31 January: the 12-month cycle starts on the last day of January each year.
		start, end = bcea.service_cycle("2020-01-31", "2025-02-15", 12)
		self.assertEqual(date(2025, 1, 31), start)
		self.assertEqual(date(2026, 1, 30), end)

	def test_cycle_refuses_a_reference_before_joining(self):
		with self.assertRaises(frappe.ValidationError):
			bcea.service_cycle("2026-03-01", "2026-02-28", 12)

	def test_only_annual_and_family_leave_live_in_a_policy(self):
		templates = {template["title"]: template for template in bcea.policy_templates()}
		self.assertEqual(2, len(templates))
		for template in templates.values():
			self.assertEqual({bcea.ANNUAL, bcea.FAMILY}, set(template["allocations"]))
			self.assertEqual(12, template["cycle_months"])
		self.assertEqual(
			15, templates["SA BCEA Annual and Family Leave - 5-day week"]["allocations"][bcea.ANNUAL]
		)
		self.assertEqual(
			18, templates["SA BCEA Annual and Family Leave - 6-day week"]["allocations"][bcea.ANNUAL]
		)

	def test_sick_leave_is_allocated_on_the_thirty_six_month_cycle(self):
		spec = bcea.sick_leave_allocation("2018-03-01", "2026-10-07", 5)
		self.assertEqual(
			(date(2024, 3, 1), date(2027, 2, 28), 30.0), (spec["from_date"], spec["to_date"], spec["days"])
		)

	def test_sick_leave_already_taken_reduces_the_allocation(self):
		spec = bcea.sick_leave_allocation("2018-03-01", "2026-10-07", 6, already_taken=10)
		self.assertEqual(26.0, spec["days"])
		with self.assertRaises(frappe.ValidationError):
			bcea.sick_leave_allocation("2018-03-01", "2026-10-07", 5, already_taken=31)

	def test_sick_leave_below_the_minimum_is_refused(self):
		with self.assertRaises(frappe.ValidationError):
			bcea.sick_leave_allocation("2018-03-01", "2026-10-07", 5, sick_days=29)

	def test_leave_types_are_governed_and_unpaid_types_are_leave_without_pay(self):
		specs = {spec["leave_type_name"]: spec for spec in bcea.leave_type_specs()}
		self.assertEqual("Annual Leave", specs[bcea.ANNUAL]["za_bcea_leave_category"])
		self.assertEqual(182, specs[bcea.ANNUAL]["expire_carry_forwarded_leaves_after_days"])
		self.assertEqual(0, specs[bcea.ANNUAL]["allow_encashment"])
		self.assertEqual(0, specs[bcea.ANNUAL]["include_holiday"])
		self.assertEqual(2, specs[bcea.SICK]["za_medical_certificate_required_after"])
		self.assertEqual("Female", specs[bcea.MATERNITY]["za_applicable_gender"])
		for name in (bcea.MATERNITY, bcea.PARENTAL, bcea.ADOPTION, bcea.COMMISSIONING):
			self.assertEqual(1, specs[name]["is_lwp"], name)

	def test_company_policy_below_the_minimum_is_refused(self):
		bcea.validate_not_below_minimum({bcea.ANNUAL: 15, bcea.SICK: 30, bcea.FAMILY: 3}, 5)
		bcea.validate_not_below_minimum({bcea.ANNUAL: 20, bcea.SICK: 30, bcea.FAMILY: 5}, 5)
		with self.assertRaises(frappe.ValidationError):
			bcea.validate_not_below_minimum({bcea.ANNUAL: 14}, 5)
		with self.assertRaises(frappe.ValidationError):
			bcea.validate_not_below_minimum({bcea.SICK: 30}, 6)


class TestFamilyResponsibilityEligibility(UnitTestCase):
	def _application(self):
		return frappe._dict(employee="EMP-1", from_date="2026-11-02", total_leave_days=1, name=None)

	def test_refused_before_four_months_of_service(self):
		employee = frappe._dict(date_of_joining="2026-09-01")
		with patch("frappe.get_cached_doc", return_value=employee), self.assertRaises(frappe.ValidationError):
			ZALeaveApplication.validate_family_leave_bcea(self._application())

	def test_allowed_after_four_months_of_service(self):
		employee = frappe._dict(date_of_joining="2026-06-01")
		with (
			patch("frappe.get_cached_doc", return_value=employee),
			patch("frappe.get_all", return_value=[]),
		):
			ZALeaveApplication.validate_family_leave_bcea(self._application())

	def test_cap_applies_across_the_service_cycle(self):
		employee = frappe._dict(date_of_joining="2020-03-01")
		with (
			patch("frappe.get_cached_doc", return_value=employee),
			patch("frappe.get_all", return_value=[frappe._dict(total_leave_days=3)]),
			self.assertRaises(frappe.ValidationError),
		):
			ZALeaveApplication.validate_family_leave_bcea(self._application())
