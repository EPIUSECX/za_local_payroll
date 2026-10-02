"""Regressions found by the reference-company end-to-end validation.

Each test reproduces a defect observed on the synthetic reference company and
pins the fix: LAB-1, PAY-FB-1, PAY-FB-2, PAY-CONTRIB-1, EMP201-2, SKL-1, EE-ISO-1,
INJ-1, INJ-2, INJ-3.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.classes import IntegrationTestCase

from za_local_payroll.sa_coida.doctype.oid_claim.oid_claim import OIDClaim
from za_local_payroll.sa_coida.doctype.workplace_injury.workplace_injury import WorkplaceInjury
from za_local_payroll.sa_labour import governance
from za_local_payroll.sa_payroll.doctype.emp201_submission.emp201_submission import (
	_looks_like_legacy_statutory_component,
)
from za_local_payroll.sa_payroll.fringe_benefits import service
from za_local_payroll.setup.default_data import DEFAULT_SALARY_COMPONENT_SARS_CODES

APP = Path(__file__).resolve().parents[1]


class TestReferenceCompanyRegressions(IntegrationTestCase):
	def test_fringe_benefit_component_lookup_aliases_abbreviation(self):
		"""PAY-FB-1: get_all selected a non-existent `abbr` column and fringe benefits never reached the slip."""
		with patch("frappe.get_all", return_value=[]) as get_all, self.assertRaises(frappe.ValidationError):
			# No rows: the lookup then reports the component missing; only the query is under test.
			service._get_salary_components({"Company Car Benefit"})
		fields = get_all.call_args_list[0].kwargs["fields"]
		self.assertIn("salary_component_abbr as abbr", fields)
		self.assertNotIn("abbr", fields)

	def test_company_car_paye_adjustment_has_sars_code(self):
		"""PAY-FB-2: the seeded adjustment component had no code, so every payroll with a car failed."""
		self.assertEqual("3802", DEFAULT_SALARY_COMPONENT_SARS_CODES["Company Car PAYE Adjustment"])

	def test_company_contribution_formula_fields_fetch_from_component(self):
		"""PAY-CONTRIB-1: structure rows lost the component's formula, so contributions computed nil."""
		meta = json.loads(
			(APP / "sa_payroll/doctype/company_contribution/company_contribution.json").read_text()
		)
		fields = {field["fieldname"]: field for field in meta["fields"]}
		for fieldname in ("condition", "amount_based_on_formula", "formula"):
			self.assertEqual(1, fields[fieldname].get("fetch_if_empty"), fieldname)

	def test_emp201_legacy_component_tokens_match_whole_words(self):
		"""EMP201-2: "Retirement Annuity" contains "eti" and blocked EMP201 as an unmapped ETI component."""
		self.assertFalse(_looks_like_legacy_statutory_component("Retirement Annuity", {}))
		self.assertFalse(_looks_like_legacy_statutory_component("Medical Aid Employee", {}))
		self.assertTrue(_looks_like_legacy_statutory_component("UIF Employee", {}))
		self.assertTrue(_looks_like_legacy_statutory_component("ETI Claimed", {}))
		self.assertTrue(_looks_like_legacy_statutory_component("Skills Development Levy", {}))

	def test_labour_doctypes_name_per_year_not_per_company_only(self):
		"""SKL-1: several sa_labour doctypes shared one naming series and a second record collided."""
		expected = {
			"skills_development_record": "format:SKI-{YYYY}-{#####}",
			"annual_training_report": "format:ATR-{YYYY}-{#####}",
			"workplace_skills_plan": "format:WSP-{YYYY}-{#####}",
			"employment_equity_movement": "format:EE-MOVE-{YYYY}-{#####}",
			"skills_development_facilitator": "format:SDF-{company}-{#####}",
			"employment_equity_target_plan": "format:EE-PLAN-{company}-{YYYY}-{#####}",
		}
		for doctype, autoname in expected.items():
			meta = json.loads((APP / f"sa_labour/doctype/{doctype}/{doctype}.json").read_text())
			self.assertEqual(autoname, meta["autoname"], doctype)

	def test_labour_records_reject_non_south_african_company(self):
		"""EE-ISO-1: an Employment Equity plan was accepted for a UK company."""
		with (
			patch("frappe.has_permission", return_value=True),
			patch.object(governance, "is_south_african_company", return_value=False),
		):
			with self.assertRaisesRegex(frappe.ValidationError, "Country set to South Africa"):
				governance.validate_company_access("UK Company")
		with (
			patch("frappe.has_permission", return_value=True),
			patch.object(governance, "is_south_african_company", return_value=True),
		):
			governance.validate_company_access("ZA Company")

	def test_injury_leave_application_carries_resolved_leave_approver(self):
		"""INJ-1: submit failed with "Leave Approver is mandatory" when HR Settings requires one."""
		doc = frappe.new_doc("Workplace Injury")
		doc.update(
			{
				"name": "INJ-TEST",
				"employee": "EMP-1",
				"injury_date": "2026-09-14",
				"leave_days": 3,
				"injury_leave_type": "ZA Occupational Injury Leave",
			}
		)
		leave = MagicMock()
		leave.name = "LAP-1"
		with (
			patch.object(WorkplaceInjury, "_validate_injury_leave_type"),
			patch.object(WorkplaceInjury, "db_set"),
			patch("frappe.db.table_exists", return_value=True),
			patch("frappe.new_doc", return_value=leave),
			patch("frappe.msgprint"),
			patch(
				"hrms.hr.doctype.leave_application.leave_application.get_employee_leave_approver",
				return_value="approver@example.test",
			),
		):
			doc.create_leave_application()
		values = leave.update.call_args.args[0]
		self.assertEqual("approver@example.test", values["leave_approver"])
		leave.insert.assert_called_once()

	def test_oid_medical_report_rejects_public_attachment(self):
		"""INJ-2: medical reports (special personal information) accepted public files."""
		doc = frappe.new_doc("OID Claim")
		doc.append(
			"medical_reports",
			{
				"report_date": "2026-09-14",
				"medical_provider": "Clinic",
				"report_type": "Initial Assessment",
				"diagnosis": "Test",
				"attachment": "/files/public-report.pdf",
			},
		)
		with patch(
			"za_local_payroll.sa_coida.doctype.oid_claim.oid_claim.validate_populated_private_attachments",
			side_effect=frappe.ValidationError("must be stored as a private file"),
		) as validator:
			with self.assertRaisesRegex(frappe.ValidationError, "private file"):
				OIDClaim.validate_medical_reports(doc)
		validator.assert_called_once()

	def test_oid_claim_cancel_ignores_injury_back_link(self):
		"""INJ-3: cancelling a submitted claim failed because the injury links back to it."""
		doc = frappe.new_doc("OID Claim")
		doc.before_cancel()
		self.assertIn("Workplace Injury", doc.ignore_linked_doctypes)

	def test_injury_cancel_unlinks_draft_children_before_deleting(self):
		"""INJ-3: cancelling an injury could not delete its own draft leave/claim (its link blocked it)."""
		doc = frappe.new_doc("Workplace Injury")
		doc.leave_application = "LAP-1"
		doc.oid_claim = "OID-1"
		order = []
		draft = MagicMock(docstatus=0)
		draft.delete.side_effect = lambda: order.append("delete")
		with (
			patch("frappe.db.exists", return_value=True),
			patch("frappe.get_doc", return_value=draft),
			patch.object(
				WorkplaceInjury, "db_set", side_effect=lambda field, *a, **k: order.append(f"unlink:{field}")
			),
		):
			doc.on_cancel()
		self.assertEqual(["unlink:leave_application", "delete", "unlink:oid_claim", "delete"], order)


class TestMedicalCertificatePrivacy(IntegrationTestCase):
	def test_leave_medical_certificate_must_be_private(self):
		"""LAB-1: a sick-leave medical certificate was accepted as a public file."""
		from za_local_payroll.overrides.leave_application import ZALeaveApplication

		doc = frappe.new_doc("Leave Application")
		doc.za_medical_certificate = "/files/public-certificate.pdf"
		with (
			patch.object(ZALeaveApplication.__mro__[1], "validate"),
			patch.object(ZALeaveApplication, "_get_governed_leave_type", return_value=None),
			patch.object(ZALeaveApplication, "validate_gender_specific_leave"),
			patch(
				"za_local_payroll.overrides.leave_application.validate_private_evidence",
				side_effect=frappe.ValidationError("must be stored as a private file"),
			) as validator,
		):
			with self.assertRaisesRegex(frappe.ValidationError, "private file"):
				ZALeaveApplication.validate(doc)
		validator.assert_called_once_with(doc, "za_medical_certificate")
