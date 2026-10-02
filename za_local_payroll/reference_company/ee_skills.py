"""Stage 11: Employment Equity and skills development working papers."""

import json

import frappe
from frappe.utils.file_manager import save_file

from za_local_payroll.reference_company import constants as C
from za_local_payroll.reference_company.governance import acting_as, user
from za_local_payroll.reference_company.guard import require_reference_site
from za_local_payroll.reference_company.labour import outcome
from za_local_payroll.reference_company.payroll_run import employee_for
from za_local_payroll.reference_company.payroll_setup import EVIDENCE


def _private(name, text="SYNTHETIC evidence - test data only"):
	return save_file(name, f"{text} [{name}]".encode(), None, None, is_private=1).file_url


def _fy():
	return frappe.db.get_value("Fiscal Year", {"year_start_date": "2026-03-01"}, "name")


def stage_employment_equity() -> dict:
	require_reference_site()
	from za_local_payroll.sa_labour.report.ee_workforce_movement import ee_workforce_movement as mov
	from za_local_payroll.sa_labour.report.ee_workforce_profile import ee_workforce_profile as prof
	from za_local_payroll.sa_labour.report.eea2_income_differentials import eea2_income_differentials as eea2
	from za_local_payroll.sa_labour.report.eea4_employment_equity_plan import (
		eea4_employment_equity_plan as eea4,
	)

	frappe.db.set_value(
		"Company",
		C.COMPANY,
		{
			"za_ee_designated_employer": 1,
			"za_ee_sector": "Finance and Business Services",
			"za_ee_small_cell_threshold": 5,
		},
	)
	r = {}
	plan = frappe.db.get_value(
		"Employment Equity Target Plan", {"company": C.COMPANY, "docstatus": 1}, "name"
	)
	if not plan:
		with acting_as(user("hr_manager")):
			doc = frappe.get_doc(
				{
					"doctype": "Employment Equity Target Plan",
					"company": C.COMPANY,
					"plan_start_date": "2026-03-01",
					"plan_end_date": "2027-02-28",
					"sector": "Finance and Business Services",
					"source_basis": "Approved Employer Plan",
					"source_reference": "SYNTHETIC: board-approved EE plan 2026/27 (test)",
					"source_evidence": _private("ee-sector-targets.txt"),
					"small_cell_threshold": 5,
					"reviewed_by": user("reviewer"),
					"review_evidence": _private("ee-plan-review.txt"),
					"targets": [
						{
							"effective_date": "2026-03-01",
							"occupational_level": "Top Management",
							"race": "African",
							"gender": "All",
							"disability_status": "All",
							"target_percentage": 40,
						},
						{
							"effective_date": "2026-03-01",
							"occupational_level": "Skilled Technical",
							"race": "All",
							"gender": "Female",
							"disability_status": "All",
							"target_percentage": 50,
						},
					],
				}
			)
			doc.insert()
		with acting_as(user("hr_manager")):
			outcome(
				r,
				"plan_submitted_by_preparer",
				lambda: frappe.get_doc("Employment Equity Target Plan", doc.name).submit(),
				True,
			)
		with acting_as(user("reviewer")):
			outcome(
				r,
				# EE-PERM-1: the reviewer role now ships with Company read.
				"reviewer_submits_plan",
				lambda: frappe.get_doc("Employment Equity Target Plan", doc.name).submit(),
				False,
			)
		frappe.db.commit()
		plan = doc.name
	employee = employee_for("P20_it3a_no_paye")
	if not frappe.db.exists("Employment Equity Movement", {"employee": employee, "docstatus": 1}):
		with acting_as(user("hr_manager")):
			mv = frappe.get_doc(
				{
					"doctype": "Employment Equity Movement",
					"company": C.COMPANY,
					"employee": employee,
					"effective_date": "2026-06-01",
					"movement_type": "Appointment",
					"new_occupational_level": "Semi-Skilled",
					"race": "African",
					"gender": "Female",
					"private_evidence": _private("ee-appointment.txt"),
				}
			)
			mv.insert()
			mv.submit()
		frappe.db.commit()
	base = {"company": C.COMPANY, "reporting_date": "2026-09-30"}
	results = {}
	outcome(r, "profile_without_company", lambda: prof.execute({"reporting_date": "2026-09-30"}), True)
	outcome(r, "profile_without_date", lambda: prof.execute({"company": C.COMPANY}), True)
	_cols, data = prof.execute(base)[:2]
	results["profile_rows"] = len(data)
	results["profile_sample"] = data[:3]
	results["profile_suppressed_cells_present"] = any(
		isinstance(v, str) and not v.replace(".", "").isdigit()
		for row in data
		for v in (row.values() if isinstance(row, dict) else row)
	)
	with acting_as(user("hr_manager")):
		outcome(
			r, "hr_manager_reveal_small_cells", lambda: prof.execute({**base, "show_small_cells": 1}), True
		)
	with acting_as(user("reviewer")):
		outcome(
			r,
			# Revealing small cells shows identifiable employees: it also needs Employee read,
			# which the reviewer role deliberately does not carry (documented requirement).
			"reviewer_without_employee_read_reveal_small_cells",
			lambda: len(prof.execute({**base, "show_small_cells": 1})[1]),
			True,
		)
	with acting_as(user("ee_reviewer")):
		outcome(
			r,
			"reviewer_with_hr_user_reveal_small_cells",
			lambda: len(prof.execute({**base, "show_small_cells": 1})[1]),
			False,
		)
	with acting_as(user("foreign_accounts")):
		outcome(r, "user_without_company_permission", lambda: prof.execute(base), True)
	outcome(r, "eea2_income_differentials", lambda: len(eea2.execute(base)[1]), False)
	outcome(
		r, "eea4_plan_with_submitted_plan", lambda: len(eea4.execute({**base, "target_plan": plan})[1]), False
	)
	outcome(r, "eea4_without_plan", lambda: eea4.execute(base), True)
	outcome(
		r,
		"workforce_movement",
		lambda: len(
			mov.execute({"company": C.COMPANY, "from_date": "2026-03-01", "to_date": "2027-02-28"})[1]
		),
		False,
	)
	out = {"tests": r, "results": results, "plan": plan}
	(EVIDENCE / "employment_equity.json").write_text(json.dumps(out, indent=1, default=str))
	return out


def stage_skills() -> dict:
	require_reference_site()
	r = {}
	seta = frappe.db.get_value("SETA", {"seta_name": "Services SETA"}, "name")
	if not seta:
		seta = (
			frappe.get_doc(
				{
					"doctype": "SETA",
					"seta_name": "Services SETA",
					"code": "SERVICES",
					"source_reference": "DHET SETA landscape (synthetic reference)",
					"active": 1,
				}
			)
			.insert(ignore_permissions=True)
			.name
		)
	if not frappe.db.get_value("SETA", seta, "source_reference"):
		# SKL-2: seeded SETA masters ship without an authority reference; the WSP control requires one.
		frappe.db.set_value(
			"SETA",
			seta,
			"source_reference",
			"SYNTHETIC: practitioner-confirmed SETA landscape reference (test)",
		)
	frappe.db.set_value("Company", C.COMPANY, "za_seta", seta)
	sdf = frappe.db.get_value(
		"Skills Development Facilitator", {"company": C.COMPANY, "docstatus": 1}, "name"
	)
	draft_sdf = None
	if not sdf:
		with acting_as(user("hr_manager")):
			d = frappe.get_doc(
				{
					"doctype": "Skills Development Facilitator",
					"company": C.COMPANY,
					"user": user("hr_manager"),
					"registration_number": "SDF-SYNTH-001",
					"effective_from": "2026-03-01",
					"appointment_evidence": _private("sdf-appointment.txt"),
					"reviewed_by": user("reviewer"),
					"review_evidence": _private("sdf-review.txt"),
				}
			)
			d.insert()
			draft = frappe.get_doc(
				{
					"doctype": "Skills Development Facilitator",
					"company": C.COMPANY,
					"user": user("payroll_user"),
					"effective_from": "2026-03-01",
					"appointment_evidence": _private("sdf2-appointment.txt"),
					"reviewed_by": user("reviewer"),
					"review_evidence": _private("sdf2-review.txt"),
				}
			)
			draft.insert()
			draft_sdf = draft.name
		with acting_as(user("reviewer")):
			frappe.get_doc("Skills Development Facilitator", d.name).submit()
		frappe.db.commit()
		sdf = d.name
	draft_sdf = draft_sdf or frappe.db.get_value(
		"Skills Development Facilitator", {"company": C.COMPANY, "docstatus": 0}, "name"
	)
	ofo = (
		frappe.db.get_value("OFO Occupation", {"ofo_code": "2021-242101"}, "name")
		or frappe.get_doc(
			{
				"doctype": "OFO Occupation",
				"ofo_code": "2021-242101",
				"occupation_title": "Management Consultant (synthetic)",
				"ofo_version": "OFO 2021",
				"effective_from": "2021-01-01",
				"source_reference": "DHET OFO 2021 (synthetic extract)",
				"active": 1,
			}
		)
		.insert(ignore_permissions=True)
		.name
	)
	provider = frappe.db.get_value("Training Provider", {"provider_name": "Synthetic Skills Academy"}, "name")
	if not provider:
		provider = (
			frappe.get_doc(
				{
					"doctype": "Training Provider",
					"provider_name": "Synthetic Skills Academy",
					"accredited": 1,
					"accreditation_body": "QCTO (synthetic)",
					"accreditation_number": "SYNTH-ACC-01",
					"accreditation_from": "2025-01-01",
					"accreditation_to": "2027-12-31",
					"accreditation_evidence": _private("provider-accreditation.txt"),
					"active": 1,
				}
			)
			.insert(ignore_permissions=True)
			.name
		)
	outcome(
		r,
		"accredited_provider_without_evidence",
		lambda: frappe.get_doc(
			{
				"doctype": "Training Provider",
				"provider_name": "No Evidence Provider",
				"accredited": 1,
				"accreditation_body": "QCTO",
				"accreditation_number": "X",
				"accreditation_from": "2025-01-01",
				"accreditation_to": "2027-12-31",
			}
		).insert(ignore_permissions=True),
		True,
	)

	def wsp(sdf_name, cost=25000, submit_as=None):
		doc = frappe.get_doc(
			{
				"doctype": "Workplace Skills Plan",
				"company": C.COMPANY,
				"fiscal_year": _fy(),
				"seta": seta,
				"skills_development_facilitator": sdf_name,
				"source_reference": "SYNTHETIC WSP 2026/27",
				"reviewed_by": user("reviewer"),
				"review_evidence": _private(f"wsp-review-{cost}.txt"),
				"training_details": [
					{
						"ofo_occupation": ofo,
						"occupational_level": "Skilled Technical",
						"planned_training": "Payroll compliance short course",
						"intervention_type": "Short course",
						"training_provider": provider,
						"number_of_employees": 3,
						"estimated_cost": cost,
					}
				],
			}
		)
		with acting_as(user("hr_manager")):
			doc.insert()
		if submit_as:
			with acting_as(submit_as):
				frappe.get_doc("Workplace Skills Plan", doc.name).submit()
		return doc.name

	outcome(r, "wsp_with_draft_sdf", lambda: wsp(draft_sdf), True)
	outcome(r, "wsp_negative_cost", lambda: wsp(sdf, cost=-100), True)
	plan = frappe.db.get_value("Workplace Skills Plan", {"company": C.COMPANY, "docstatus": 1}, "name")
	if not plan:
		outcome(r, "wsp_submitted_by_preparer", lambda: wsp(sdf, submit_as=user("hr_manager")), True)
		plan = wsp(sdf, submit_as=user("reviewer"))
		frappe.db.commit()
	total = frappe.db.get_value("Workplace Skills Plan", plan, "total_training_budget")
	atr = frappe.db.get_value("Annual Training Report", {"company": C.COMPANY, "docstatus": 1}, "name")
	if not atr:

		def make_atr(evidence=True):
			doc = frappe.get_doc(
				{
					"doctype": "Annual Training Report",
					"company": C.COMPANY,
					"fiscal_year": _fy(),
					"seta": seta,
					"skills_development_facilitator": sdf,
					"workplace_skills_plan": plan,
					"source_reference": "SYNTHETIC ATR 2026/27",
					"reviewed_by": user("reviewer"),
					"review_evidence": _private("atr-review.txt"),
					"training_completed": [
						{
							"ofo_occupation": ofo,
							"occupational_level": "Skilled Technical",
							"training_completed": "Payroll compliance short course",
							"intervention_type": "Short course",
							"training_provider": provider,
							"number_trained": 3,
							"actual_cost": 23500,
							"completion_evidence": _private("atr-completion.txt") if evidence else None,
						}
					],
				}
			)
			with acting_as(user("hr_manager")):
				doc.insert()
			return doc

		outcome(r, "atr_row_without_completion_evidence", lambda: make_atr(evidence=False), True)
		doc = make_atr()
		with acting_as(user("reviewer")):
			frappe.get_doc("Annual Training Report", doc.name).submit()
		frappe.db.commit()
		atr = doc.name
	with acting_as(user("hr_manager")):

		def filed_without_evidence():
			doc = frappe.copy_doc(frappe.get_doc("Workplace Skills Plan", plan), ignore_no_copy=False)
			doc.update(
				{
					"external_filing_status": "Filed Externally",
					"external_filing_reference": "SYNTH-SETA-1",
					"external_filing_date": "2026-04-30",
				}
			)
			doc.insert()

		outcome(r, "wsp_filed_externally_without_evidence", filed_without_evidence, True)
	rec = frappe.db.get_value("Skills Development Record", {"company": C.COMPANY, "docstatus": 1}, "name")
	if not rec:
		with acting_as(user("hr_manager")):
			doc = frappe.get_doc(
				{
					"doctype": "Skills Development Record",
					"company": C.COMPANY,
					"fiscal_year": _fy(),
					"seta": seta,
					"workplace_skills_plan": plan,
					"annual_training_report": atr,
					"employee": employee_for("P02_normal"),
					"ofo_occupation": ofo,
					"training_program": "Payroll compliance short course",
					"intervention_type": "Short course",
					"training_provider": provider,
					"provider_accreditation_required": 1,
					"start_date": "2026-05-04",
					"end_date": "2026-05-08",
					"training_cost": 7833.33,
					"completion_evidence": _private("sdr-completion.txt"),
				}
			)
			doc.insert()
			doc.submit()
		frappe.db.commit()
		rec = doc.name
	rec_doc = frappe.get_doc("Skills Development Record", rec)
	out = {
		"tests": r,
		"seta": seta,
		"sdf": sdf,
		"wsp": plan,
		"wsp_total": total,
		"atr": atr,
		"atr_spend": frappe.db.get_value("Annual Training Report", atr, "actual_training_spend"),
		"record": rec,
		"bbbee_status": rec_doc.bbbee_scoring_status,
		"bec_points": rec_doc.bec_points,
	}
	(EVIDENCE / "skills.json").write_text(json.dumps(out, indent=1, default=str))
	return out
