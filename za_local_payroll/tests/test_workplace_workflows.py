"""Regression coverage for workplace calculations and reminders."""

from __future__ import annotations

from unittest.mock import patch

import frappe
from frappe.tests.classes import UnitTestCase
from frappe.utils import add_days, flt, getdate, today

from za_local_payroll.sa_coida.doctype.coida_annual_return.coida_annual_return import COIDAAnnualReturn
from za_local_payroll.sa_coida.doctype.oid_claim.oid_claim import OIDClaim
from za_local_payroll.sa_coida.doctype.workplace_injury.workplace_injury import WorkplaceInjury
from za_local_payroll.sa_labour.doctype.business_trip.business_trip import BusinessTrip
from za_local_payroll.tasks import remind_coida_rate_review, remind_employment_equity_reporting


class TestWorkplaceWorkflows(UnitTestCase):
	def test_business_trip_totals_use_configured_mileage_rate(self):
		doc = frappe.new_doc("Business Trip")
		doc.from_date = "2026-04-10"
		doc.to_date = "2026-04-11"
		doc.allowances = [
			frappe._dict(daily_rate=522, incidental_rate=169),
			frappe._dict(daily_rate=522, incidental_rate=169),
		]
		doc.journeys = [
			frappe._dict(transport_mode="Car (Private)", distance_km=120, mileage_claim=0),
			frappe._dict(transport_mode="Flight", receipt_amount=1800),
		]
		doc.accommodations = [frappe._dict(amount=1250)]
		doc.other_expenses = [frappe._dict(amount=300)]

		with patch("frappe.get_cached_doc", return_value=frappe._dict(mileage_allowance_rate=4.84)):
			BusinessTrip.validate(doc)

		self.assertEqual(1044, doc.total_allowance)
		self.assertEqual(338, doc.total_incidental)
		self.assertEqual(580.8, flt(doc.total_mileage_claim, 2))
		self.assertEqual(5312.8, flt(doc.grand_total, 2))

	def test_coida_return_uses_march_fiscal_year_and_server_rate(self):
		doc = frappe.new_doc("COIDA Annual Return")
		doc.company = "Test Company"
		doc.industry_class = "Class 1"
		doc.employer_category = "General Employer"
		doc.fiscal_year = "2026-2027"
		doc.total_annual_earnings = 1_250_000
		fiscal_year = frappe._dict(year_start_date="2026-03-01", year_end_date="2027-02-28")

		with (
			patch("frappe.get_cached_doc", return_value=fiscal_year),
			patch(
				"za_local_payroll.sa_coida.doctype.coida_annual_return.coida_annual_return.resolve_coida_industry_rate",
				return_value=frappe._dict(
					value=1.35,
					rule_key="coida.assessment_rate.Test Company.Class 1",
					source_reference="TEST-SOURCE",
				),
			),
			patch(
				"za_local_payroll.sa_coida.doctype.coida_annual_return.coida_annual_return.resolve_coida_minimum_assessment",
				return_value=frappe._dict(
					value=1621,
					rule_key="coida.minimum_assessment",
					source_reference="GAZETTE-54577-3910",
				),
			),
		):
			COIDAAnnualReturn.validate(doc)

		self.assertEqual(getdate("2026-03-01"), doc.from_date)
		self.assertEqual(getdate("2027-02-28"), doc.to_date)
		self.assertEqual(16875, doc.assessment_fee)
		self.assertEqual(1621, doc.minimum_assessment)

	def test_injury_and_claim_dates_are_validated(self):
		injury = frappe.new_doc("Workplace Injury")
		injury.injury_date = add_days(today(), 1)
		with self.assertRaises(frappe.ValidationError):
			WorkplaceInjury.validate_dates(injury)

		injury.injury_date = "2026-04-01"
		injury.expected_recovery_date = "2026-04-05"
		WorkplaceInjury.calculate_leave_days(injury)
		self.assertEqual(5, injury.leave_days)

		claim = frappe.new_doc("OID Claim")
		claim.injury_date = "2026-04-10"
		claim.claim_date = "2026-04-09"
		with self.assertRaises(frappe.ValidationError):
			OIDClaim.validate_dates(claim)

	def test_reminders_use_month_recovery_windows(self):
		with (
			patch("za_local_payroll.tasks.today", return_value="2026-12-18"),
			patch("za_local_payroll.tasks._notify_roles_once") as notify,
		):
			remind_employment_equity_reporting()
		notify.assert_called_once()
		self.assertEqual(getdate("2026-12-01"), notify.call_args.kwargs["reference_date"])

		with (
			patch("za_local_payroll.tasks.today", return_value="2027-02-18"),
			patch("za_local_payroll.tasks._notify_roles_once") as notify,
		):
			remind_coida_rate_review()
		notify.assert_called_once()
		self.assertEqual(getdate("2027-02-01"), notify.call_args.kwargs["reference_date"])
