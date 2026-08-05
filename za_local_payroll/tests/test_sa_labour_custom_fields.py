import frappe
from frappe.tests.classes import UnitTestCase


class TestSALabourCustomFields(UnitTestCase):
	def test_employee_employment_equity_fields_exist(self):
		meta = frappe.get_meta("Employee")
		fieldnames = {field.fieldname for field in meta.fields if field.fieldname}

		expected = {
			"za_race",
			"za_occupational_level",
			"za_is_disabled",
		}

		self.assertTrue(
			expected.issubset(fieldnames),
			msg=f"Missing Employee employment equity fields: {sorted(expected - fieldnames)}",
		)

	def test_bcea_leave_and_termination_fields_exist(self):
		expected_by_doctype = {
			"Leave Type": {"za_bcea_leave_category"},
			"Leave Application": {"za_medical_certificate"},
			"Employee Separation": {
				"za_termination_date",
				"za_completed_service_years",
				"za_bcea_weekly_remuneration",
				"za_bcea_daily_remuneration",
				"za_bcea_remuneration_basis",
				"za_bcea_remuneration_reviewed",
				"za_bcea_remuneration_reviewed_by",
				"za_bcea_remuneration_reviewed_on",
				"za_leave_payout_days",
			},
		}

		for doctype, expected in expected_by_doctype.items():
			fieldnames = {field.fieldname for field in frappe.get_meta(doctype).fields if field.fieldname}
			self.assertTrue(
				expected.issubset(fieldnames),
				msg=f"Missing {doctype} BCEA fields: {sorted(expected - fieldnames)}",
			)
