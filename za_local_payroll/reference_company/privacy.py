"""Stage 12: POPIA/PAIA registers and case files for the reference company.

All names, references and evidence are synthetic. The registers prove the
maker-checker, private-evidence and state-machine controls; they are not a
legal opinion on the reference company's POPIA position.
"""

import json

import frappe
from frappe.utils import add_days, now_datetime, today

from za_local_payroll.reference_company import constants as C
from za_local_payroll.reference_company import paths
from za_local_payroll.reference_company.ee_skills import _private
from za_local_payroll.reference_company.governance import acting_as, user
from za_local_payroll.reference_company.guard import commit_stage, require_reference_site
from za_local_payroll.reference_company.labour import outcome


def _public(name):
	return (
		frappe.get_doc(
			{"doctype": "File", "file_name": name, "is_private": 0, "content": b"SYNTHETIC public file"}
		)
		.insert(ignore_permissions=True)
		.file_url
	)


def _reviewed(doctype, key, values, results, label):
	"""Create as preparer, prove the preparer cannot approve, approve as reviewer."""
	name = frappe.db.get_value(doctype, {"company": C.COMPANY, key: values[key], "docstatus": 1}, "name")
	if name:
		return name
	with acting_as(user("preparer")):
		doc = frappe.get_doc(
			{
				"doctype": doctype,
				"company": C.COMPANY,
				"responsible_user": user("preparer"),
				"reviewed_by": user("reviewer"),
				**values,
			}
		)
		doc.insert()
		commit_stage()
		outcome(
			results, f"{label}_preparer_approves", lambda: frappe.get_doc(doctype, doc.name).submit(), True
		)
	with acting_as(user("reviewer")):
		outcome(
			results, f"{label}_reviewer_approves", lambda: frappe.get_doc(doctype, doc.name).submit(), False
		)
	return doc.name


def stage_privacy_registers() -> dict:
	require_reference_site()
	r = {}
	io = _reviewed(
		"ZA Information Officer Registration",
		"officer_name",
		{
			"officer_name": "Avi Approver (synthetic)",
			"designation": "Chief Executive Officer (synthetic)",
			"registration_reference": "SYNTH-IR-0001",
			"submitted_on": "2026-03-02",
			"registered_on": "2026-03-09",
			"effective_from": "2026-03-09",
			"submission_evidence": _private("io-submission.txt"),
			"registration_evidence": _private("io-registration.txt"),
			"deputy_officers": "Pat Preparer (synthetic deputy)",
		},
		r,
		"io_registration",
	)
	paia = _reviewed(
		"ZA PAIA Manual",
		"manual_version",
		{
			"manual_title": "PAIA and POPIA Manual (synthetic)",
			"manual_version": "REF-2026.1",
			"information_officer_registration": io,
			"published_on": "2026-03-15",
			"effective_from": "2026-03-15",
			"publication_url": "https://cohenix-ref.test/paia",
			"physical_availability": "Synthetic head office reception",
			"languages": "English",
			"last_reviewed_on": "2026-03-15",
			"next_review_due": "2027-03-15",
			"review_scope": "Full manual review (synthetic)",
			"manual_file": _private("paia-manual.txt"),
			"publication_evidence": _private("paia-publication.txt"),
		},
		r,
		"paia_manual",
	)
	retention = _reviewed(
		"ZA Retention Schedule",
		"record_class",
		{
			"record_class": "Payroll and tax records (synthetic)",
			"business_owner": "Payroll",
			"retention_trigger": "End of tax year of the last payroll transaction",
			"retention_period_value": 5,
			"retention_period_unit": "Years",
			"legal_requirement": 1,
			"legal_basis": "SYNTHETIC: practitioner to confirm statutory retention basis (e.g. Tax Administration Act s29; BCEA s31).",
			"disposal_method": "Secure Destruction",
			"disposal_instructions": "Shred / crypto-erase (synthetic)",
			"legal_hold_process": "Hold on notice of audit or dispute (synthetic)",
			"effective_from": "2026-03-01",
			"legal_basis_evidence": _private("retention-basis.txt"),
			"approval_evidence": _private("retention-approval.txt"),
		},
		r,
		"retention_schedule",
	)
	transfer = _reviewed(
		"ZA Cross Border Transfer",
		"transfer_name",
		{
			"transfer_name": "Group HR analytics to UK affiliate (synthetic)",
			"recipient_name": "Cohenix UK Reference Ltd (synthetic)",
			"destination_country": "United Kingdom",
			"transfer_purpose": "Group headcount reporting (synthetic)",
			"personal_information_categories": "Employee number, job grade",
			"data_subject_categories": "Employees",
			"transfer_ground": "Adequate Protection or Binding Agreement",
			"safeguards": "Intra-group agreement (synthetic)",
			"assessment_date": "2026-03-10",
			"next_review_date": "2027-03-10",
			"effective_from": "2026-03-10",
			"transfer_assessment": _private("tia.txt"),
			"safeguard_evidence": _private("igda.txt"),
		},
		r,
		"cross_border",
	)
	activity = _reviewed(
		"ZA Processing Activity",
		"activity_name",
		{
			"activity_name": "Payroll processing (synthetic)",
			"business_process": "Payroll",
			"processing_purpose": "Pay employees and meet SARS/UIF/SDL/COIDA obligations",
			"processing_justification": "Legal Obligation",
			"justification_details": "SYNTHETIC: statutory payroll obligations",
			"data_subject_categories": "Employees",
			"personal_information_categories": "Identity, banking, remuneration, tax",
			"special_personal_information": 1,
			"recipients": "SARS, UIF, Compensation Fund, bank (synthetic)",
			"operators": "Synthetic Payroll Bureau",
			"cross_border_transfer": 1,
			"cross_border_transfer_record": transfer,
			"retention_schedule": retention,
			"security_measures": "Role-based access, private files (synthetic)",
			"last_reviewed_on": "2026-03-20",
			"next_review_date": "2027-03-20",
			"risk_assessment": _private("pa-risk.txt"),
			"approval_evidence": _private("pa-approval.txt"),
		},
		r,
		"processing_activity",
	)
	operator = _reviewed(
		"ZA Operator Agreement",
		"agreement_reference",
		{
			"operator_name": "Synthetic Payroll Bureau (Pty) Ltd",
			"agreement_reference": "SYNTH-OA-001",
			"service_description": "Payslip distribution (synthetic)",
			"processing_scope": "Payslips only (synthetic)",
			"personal_information_categories": "Name, remuneration",
			"security_obligations": "s19-s21 POPIA controls (synthetic)",
			"sub_operator_controls": "Prior written consent",
			"return_or_destruction_terms": "Return within 30 days",
			"breach_notification_hours": 24,
			"signed_on": "2026-03-01",
			"effective_from": "2026-03-01",
			"effective_to": "2027-02-28",
			"last_assessed_on": "2026-03-01",
			"next_assessment_due": "2027-03-01",
			"signed_agreement": _private("oa-signed.txt"),
			"security_assessment": _private("oa-security.txt"),
		},
		r,
		"operator_agreement",
	)

	with acting_as(user("preparer")):
		base_pa = {
			"doctype": "ZA Processing Activity",
			"company": C.COMPANY,
			"activity_name": "Negative test",
			"business_process": "X",
			"processing_purpose": "X",
			"processing_justification": "Consent",
			"justification_details": "X",
			"data_subject_categories": "X",
			"personal_information_categories": "X",
			"recipients": "X",
			"retention_schedule": retention,
			"security_measures": "X",
			"last_reviewed_on": "2026-03-20",
			"next_review_date": "2027-03-20",
		}
		outcome(
			r,
			"processing_activity_cross_border_without_record",
			lambda: frappe.get_doc({**base_pa, "cross_border_transfer": 1}).insert(),
			True,
		)
		outcome(
			r,
			"retention_zero_period",
			lambda: frappe.get_doc(
				{
					"doctype": "ZA Retention Schedule",
					"company": C.COMPANY,
					"record_class": "X",
					"business_owner": "X",
					"retention_trigger": "X",
					"retention_period_value": 0,
					"retention_period_unit": "Years",
					"legal_basis": "X",
					"disposal_method": "Secure Destruction",
					"disposal_instructions": "X",
					"legal_hold_process": "X",
					"effective_from": "2026-03-01",
				}
			).insert(),
			True,
		)
		outcome(
			r,
			"cross_border_destination_south_africa",
			lambda: frappe.get_doc(
				{
					"doctype": "ZA Cross Border Transfer",
					"company": C.COMPANY,
					"transfer_name": "X",
					"recipient_name": "X",
					"destination_country": "South Africa",
					"transfer_purpose": "X",
					"personal_information_categories": "X",
					"data_subject_categories": "X",
					"transfer_ground": "Adequate Protection or Binding Agreement",
					"safeguards": "X",
					"assessment_date": "2026-03-10",
					"next_review_date": "2027-03-10",
					"effective_from": "2026-03-10",
				}
			).insert(),
			True,
		)
		outcome(
			r,
			"operator_breach_hours_zero",
			lambda: frappe.get_doc(
				{
					"doctype": "ZA Operator Agreement",
					"company": C.COMPANY,
					"operator_name": "X",
					"agreement_reference": "X0",
					"service_description": "X",
					"processing_scope": "X",
					"personal_information_categories": "X",
					"security_obligations": "X",
					"sub_operator_controls": "X",
					"return_or_destruction_terms": "X",
					"breach_notification_hours": 0,
					"signed_on": "2026-03-01",
					"effective_from": "2026-03-01",
					"effective_to": "2027-02-28",
					"last_assessed_on": "2026-03-01",
					"next_assessment_due": "2027-03-01",
				}
			).insert(),
			True,
		)

		def approved_record_edit():
			d = frappe.get_doc("ZA Processing Activity", activity)
			d.processing_purpose = "Changed after approval"
			d.save()

		outcome(r, "approved_processing_activity_edit", approved_record_edit, True)

	def public_evidence_submit():
		with acting_as(user("preparer")):
			d = frappe.get_doc(
				{
					"doctype": "ZA Retention Schedule",
					"company": C.COMPANY,
					"record_class": "Public evidence test",
					"business_owner": "X",
					"retention_trigger": "X",
					"retention_period_value": 1,
					"retention_period_unit": "Years",
					"legal_basis": "X",
					"disposal_method": "Secure Destruction",
					"disposal_instructions": "X",
					"legal_hold_process": "X",
					"effective_from": "2026-03-01",
					"reviewed_by": user("reviewer"),
					"legal_basis_evidence": _public("retention-public.txt"),
					"approval_evidence": _private("x.txt"),
				}
			).insert()
		with acting_as(user("reviewer")):
			frappe.get_doc("ZA Retention Schedule", d.name).submit()

	outcome(r, "public_evidence_blocks_approval", public_evidence_submit, True)
	for role_user in ("accounts_user", "hr_manager", "employee"):
		with acting_as(user(role_user)):
			outcome(
				r,
				f"{role_user}_reads_processing_register",
				lambda: frappe.get_list("ZA Processing Activity", fields=["name"]) or None,
				True,
			)
	out = {
		"records": {
			"io_registration": io,
			"paia_manual": paia,
			"retention_schedule": retention,
			"cross_border_transfer": transfer,
			"processing_activity": activity,
			"operator_agreement": operator,
		},
		"tests": r,
	}
	(paths.payroll() / "privacy_registers.json").write_text(json.dumps(out, indent=1, default=str))
	return out


def stage_privacy_cases() -> dict:
	require_reference_site()
	r = {}
	dsr = frappe.db.get_value("ZA Data Subject Request", {"company": C.COMPANY, "status": "Closed"}, "name")
	if not dsr:
		frappe.db.delete("ZA Data Subject Request", {"company": C.COMPANY})
		commit_stage()
		with acting_as(user("preparer")):
			d = frappe.get_doc(
				{
					"doctype": "ZA Data Subject Request",
					"company": C.COMPANY,
					"request_type": "Access to Personal Information",
					"data_subject_reference": "SYNTH-DS-0001",
					"responsible_user": user("preparer"),
					"status": "Received",
					"request_channel": "Email",
					"received_on": "2026-09-01",
					"due_date": "2026-10-01",
					"request_scope": "Payslips Mar-Aug 2026 (synthetic)",
					"request_evidence": _private("dsr-request.txt"),
				}
			)
			outcome(
				r,
				"dsr_created_in_progress",
				lambda: frappe.get_doc({**d.as_dict(), "status": "In Progress"}).insert(),
				True,
			)
			d.insert()
			commit_stage()
			dsr = d.name

			def step(**values):
				doc = frappe.get_doc("ZA Data Subject Request", dsr)
				doc.update(values)
				doc.save()
				return doc.status

			outcome(
				r,
				"dsr_received_to_fulfilled",
				lambda: step(status="Fulfilled", completed_on="2026-09-05"),
				True,
			)
			outcome(r, "dsr_in_progress_without_identity", lambda: step(status="In Progress"), True)
			outcome(r, "dsr_identity_pending", lambda: step(status="Identity Verification Pending"), False)
			outcome(
				r,
				"dsr_in_progress_with_identity",
				lambda: step(
					status="In Progress",
					identity_verified_on="2026-09-03",
					identity_verification_method="Synthetic ID check",
					identity_verification_evidence=_private("dsr-id.txt"),
				),
				False,
			)
			outcome(r, "dsr_extended_without_reason", lambda: step(status="Extended"), True)
			outcome(
				r,
				"dsr_fulfilled_self_review",
				lambda: step(
					status="Fulfilled",
					completed_on="2026-09-20",
					final_response_evidence=_private("dsr-response.txt"),
					reviewed_by=user("preparer"),
				),
				True,
			)
		with acting_as(user("reviewer")):
			outcome(
				r,
				"dsr_fulfilled_independent_review",
				lambda: step(
					status="Fulfilled",
					completed_on="2026-09-20",
					final_response_evidence=_private("dsr-response.txt"),
					reviewed_by=user("reviewer"),
				),
				False,
			)
			outcome(r, "dsr_closed", lambda: step(status="Closed"), False)
			outcome(r, "dsr_closed_reopened", lambda: step(status="In Progress"), True)

	def public_response_by_reviewer():
		with acting_as(user("preparer")):
			t = frappe.get_doc(
				{
					"doctype": "ZA Data Subject Request",
					"company": C.COMPANY,
					"request_type": "Correction",
					"data_subject_reference": "SYNTH-DS-0002",
					"responsible_user": user("preparer"),
					"status": "Received",
					"request_channel": "Email",
					"received_on": "2026-09-01",
					"due_date": "2026-10-01",
					"request_scope": "Correct address (synthetic)",
					"request_evidence": _private("dsr2.txt"),
				}
			).insert()
			for values in (
				{"status": "Identity Verification Pending"},
				{
					"status": "In Progress",
					"identity_verified_on": "2026-09-02",
					"identity_verification_evidence": _private("dsr2-id.txt"),
				},
			):
				t.update(values)
				t.save()
		with acting_as(user("reviewer")):
			t = frappe.get_doc("ZA Data Subject Request", t.name)
			t.update(
				{
					"status": "Fulfilled",
					"completed_on": "2026-09-05",
					"reviewed_by": user("reviewer"),
					"final_response_evidence": _public("dsr2-public.txt"),
				}
			)
			t.save()

	outcome(r, "dsr_fulfilled_public_response_by_reviewer", public_response_by_reviewer, True)
	frappe.db.delete("ZA Data Subject Request", {"data_subject_reference": "SYNTH-DS-0002"})
	commit_stage()
	with acting_as(user("reviewer")):
		masked = frappe.get_list(
			"ZA Data Subject Request", fields=["name", "data_subject_reference", "request_scope"]
		)
		r["reviewer_list_view_masked"] = masked[:1]
	for role_user in ("accounts_user", "hr_manager", "payroll_manager"):
		with acting_as(user(role_user)):
			outcome(
				r,
				f"{role_user}_reads_dsr",
				lambda: frappe.get_list("ZA Data Subject Request", fields=["name"]) or None,
				True,
			)

	incident = frappe.db.get_value(
		"ZA Personal Information Incident", {"company": C.COMPANY, "status": "Closed"}, "name"
	)
	if not incident:
		frappe.db.delete("ZA Personal Information Incident", {"company": C.COMPANY})
		commit_stage()
		with acting_as(user("preparer")):
			i = frappe.get_doc(
				{
					"doctype": "ZA Personal Information Incident",
					"company": C.COMPANY,
					"incident_title": "SYNTHETIC: payslip e-mailed to wrong recipient",
					"severity": "Moderate",
					"responsible_user": user("preparer"),
					"status": "Reported",
					"detected_at": "2026-09-10 09:00:00",
					"occurred_from": "2026-09-10 08:30:00",
					"incident_summary": "SYNTHETIC test incident",
					"systems_or_locations": "Payroll e-mail",
					"personal_information_categories": "Remuneration",
					"affected_data_subjects": 1,
					"notification_decision": "Pending Assessment",
				}
			)
			i.insert()
			commit_stage()
			incident = i.name

			def istep(**values):
				doc = frappe.get_doc("ZA Personal Information Incident", incident)
				doc.update(values)
				doc.save()
				return doc.status

			outcome(r, "incident_skip_to_resolved", lambda: istep(status="Resolved"), True)
			outcome(r, "incident_triaged", lambda: istep(status="Triaged"), False)
			outcome(
				r,
				"incident_contained_without_evidence",
				lambda: istep(status="Contained", contained_at="2026-09-10 10:00:00"),
				True,
			)
			outcome(
				r,
				"incident_contained",
				lambda: istep(
					status="Contained",
					contained_at="2026-09-10 10:00:00",
					containment_evidence=_private("inc-contain.txt"),
					containment_actions="Recall requested",
				),
				False,
			)
			outcome(
				r,
				"incident_assessment_pending_decision",
				lambda: istep(status="Notification Assessment"),
				True,
			)
			outcome(
				r,
				"incident_assessment",
				lambda: istep(
					status="Notification Assessment",
					notification_decision="Regulator and Data Subjects",
					notification_rationale="SYNTHETIC: s22 assessment",
					notification_assessment_evidence=_private("inc-assess.txt"),
				),
				False,
			)
			outcome(r, "incident_notifying", lambda: istep(status="Notifying"), False)
			outcome(
				r, "incident_remediating_without_notifications", lambda: istep(status="Remediating"), True
			)
			outcome(
				r,
				"incident_remediating",
				lambda: istep(
					status="Remediating",
					regulator_notified_on="2026-09-11 12:00:00",
					regulator_notification_reference="SYNTH-IR-BREACH-1",
					regulator_notification_evidence=_private("inc-reg.txt"),
					data_subjects_notified_on="2026-09-11 12:30:00",
					data_subject_notification_evidence=_private("inc-ds.txt"),
				),
				False,
			)
		with acting_as(user("reviewer")):
			outcome(
				r,
				"incident_resolved_independent_review",
				lambda: istep(
					status="Resolved",
					resolved_at="2026-09-15 16:00:00",
					root_cause="Autocomplete",
					remediation_actions="Disable autocomplete",
					remediation_evidence=_private("inc-rem.txt"),
					reviewed_by=user("reviewer"),
				),
				False,
			)
			outcome(r, "incident_closed", lambda: istep(status="Closed"), False)
	out = {
		"dsr": dsr,
		"incident": incident,
		"tests": r,
		"dsr_final": frappe.db.get_value(
			"ZA Data Subject Request", dsr, ["status", "reviewed_by"], as_dict=True
		),
		"incident_final": frappe.db.get_value(
			"ZA Personal Information Incident", incident, ["status", "reviewed_by"], as_dict=True
		),
		"generated": str(now_datetime()),
		"today": today(),
		"dsr_due_rule": str(add_days("2026-09-01", 30)),
	}
	(paths.payroll() / "privacy_cases.json").write_text(json.dumps(out, indent=1, default=str))
	return out
