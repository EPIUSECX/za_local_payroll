"""Stage 11: COIDA Return of Earnings, workplace injury and OID claim lifecycle.

Golden earnings are rebuilt from submitted Salary Slip earning rows using this
module's own component classification (COIDA_CLASSIFICATION), never from the
app's za_coida_applicable flags. Two golden variants are produced:

- "configured": the classification the shipped defaults intend (to prove the
  return's mechanics: cap per employee, rate, minimum, director split);
- "notice_2025": the 25 April 2025 Ministerial notice on the manner of
  calculating earnings (24 earning types incl. regular allowances; excludes
  reimbursements and ex gratia). Taken from secondary summaries because the
  notice itself was not archived, so it is a practitioner sign-off item.
"""

import json

import frappe
from frappe.utils import flt

from za_local_payroll.reference_company import constants as C
from za_local_payroll.reference_company import paths
from za_local_payroll.reference_company.ee_skills import _fy, _private
from za_local_payroll.reference_company.governance import acting_as, user
from za_local_payroll.reference_company.guard import commit_stage, require_reference_site
from za_local_payroll.reference_company.labour import _allocate, outcome
from za_local_payroll.reference_company.payroll_run import employee_for


def golden() -> dict:
	"""The golden COIDA figures, read when needed so importing this module never needs the file."""
	return json.loads(paths.golden_file().read_text())["coida"]


RATE = 0.39  # synthetic reference-company assessment notice, class 9 (governance.SYNTHETIC_COIDA_NOTICE)
DIRECTOR = "P09_retirement_cap"

# component -> (configured, notice_2025)
COIDA_CLASSIFICATION = {
	"Basic": (True, True),
	"Hourly Wages": (True, True),
	"Overtime": (True, True),
	"Commission": (True, True),
	"Performance Bonus": (True, True),
	"13th Cheque": (True, True),
	"Arrear": (True, True),
	"Leave Encashment": (True, True),
	"Leave Payout": (True, True),
	"Notice Pay": (True, True),
	"Cellphone Allowance": (True, True),
	"Fixed Travel Allowance": (True, True),
	"Uniform Allowance": (True, True),  # "any other non-pensionable allowance" unless a reimbursement
	"Reimbursive Travel": (False, False),
	"Business Expense Reimbursement": (False, False),
	"Severance Benefit": (False, False),
}
NON_CASH = {
	"Company Car Benefit",
	"Company Car PAYE Adjustment",
	"Housing Fringe Benefit",
	"Low Interest Loan Fringe Benefit",
	"Other Fringe Benefit",
	"Medical Aid Company Contribution",
}


def golden_roe() -> dict:
	slips = frappe.get_all(
		"Salary Slip",
		filters={"company": C.COMPANY, "docstatus": 1, "end_date": ["between", ["2026-03-01", "2027-02-28"]]},
		fields=["name", "employee", "end_date"],
		order_by="employee, end_date, name",
	)
	cap = flt(golden()["annual_earnings_cap"])
	directors = {employee_for(DIRECTOR)}
	out, unknown = {}, set()
	for variant, index in (("configured", 0), ("notice_2025", 1)):
		running, total, director_total, uncapped = {}, 0.0, 0.0, 0.0
		for s in slips:
			amount = 0.0
			for row in frappe.get_all(
				"Salary Detail",
				filters={"parent": s.name, "parentfield": "earnings"},
				fields=["salary_component", "amount"],
			):
				if row.salary_component in NON_CASH:
					continue
				if row.salary_component not in COIDA_CLASSIFICATION:
					unknown.add(row.salary_component)
					continue
				if COIDA_CLASSIFICATION[row.salary_component][index]:
					amount += flt(row.amount)
			uncapped += amount
			remaining = max(0.0, cap - running.get(s.employee, 0.0))
			capped = round(min(amount, remaining), 2)
			running[s.employee] = running.get(s.employee, 0.0) + amount
			total += capped
			if s.employee in directors:
				director_total += capped
		before_min = round(total * RATE / 100, 2)
		out[variant] = {
			"slips": len(slips),
			"employees": len(running),
			"assessable_uncapped": round(uncapped, 2),
			"assessable_capped": round(total, 2),
			"director_earnings": round(director_total, 2),
			"employee_earnings_excl_directors": round(total - director_total, 2),
			"assessment_before_minimum": before_min,
			"assessment_fee": round(max(before_min, flt(golden()["minimum_assessment"])), 2),
			"capped_employees": sorted(k for k, v in running.items() if v > cap),
		}
	out["unclassified_components"] = sorted(unknown)
	return out


def _new_return(industry_class="9", fiscal_year=None):
	return frappe.get_doc(
		{
			"doctype": "COIDA Annual Return",
			"company": C.COMPANY,
			"industry_class": industry_class,
			"employer_category": "General Employer",
			"fiscal_year": fiscal_year or _fy(),
			"total_employees": 0,
			"total_annual_earnings": 0,
			"status": "Draft",
		}
	)


def stage_coida_return() -> dict:
	require_reference_site()
	frappe.db.set_value("Employee", employee_for(DIRECTOR), "za_coida_director", 1)
	commit_stage()
	r = {}
	golden = golden_roe()
	name = frappe.db.get_value("COIDA Annual Return", {"company": C.COMPANY, "docstatus": 1}, "name")
	if not name:
		frappe.db.delete("COIDA Annual Return", {"company": C.COMPANY, "docstatus": 0})
		commit_stage()
		with acting_as(user("hr_manager")):

			def unknown_class():
				d = _new_return("77").insert()
				d.fetch_employee_data()

			def without_fetch():
				_new_return().insert().submit()

			def drop_drafts():
				frappe.db.delete("COIDA Annual Return", {"company": C.COMPANY, "docstatus": 0})
				commit_stage()

			outcome(r, "unknown_industry_class_fetch", unknown_class, True)
			drop_drafts()
			outcome(r, "submit_without_fetch", without_fetch, True)
			drop_drafts()
			doc = _new_return()
			doc.insert()
			doc.fetch_employee_data()
			doc.save()
			commit_stage()
			name = doc.name

			def stale():
				d = frappe.get_doc("COIDA Annual Return", name)
				d.total_annual_earnings = flt(d.total_annual_earnings) - 1000
				d.save()
				d.submit()

			outcome(r, "manually_edited_total_rejected", stale, True)

			def director_flip():
				frappe.db.set_value("Employee", employee_for("P03_high_income"), "za_coida_director", 1)
				frappe.get_doc("COIDA Annual Return", name).submit()

			outcome(r, "source_changed_after_fetch_rejected", director_flip, True)
			frappe.db.set_value("Employee", employee_for("P03_high_income"), "za_coida_director", 0)
			commit_stage()
		frappe.db.set_value("COIDA Annual Return", name, "reviewed_by", user("hr_reviewer"))
		commit_stage()
		with acting_as(user("payroll_user")):
			outcome(
				r,
				"payroll_user_cannot_submit",
				lambda: frappe.get_doc("COIDA Annual Return", name).submit(),
				True,
			)
		with acting_as(user("hr_manager")):
			outcome(
				r,
				"preparer_submits_own_return",
				lambda: frappe.get_doc("COIDA Annual Return", name).submit(),
				True,
			)
		with acting_as(user("hr_reviewer")):
			outcome(
				r,
				"independent_reviewer_submits",
				lambda: frappe.get_doc("COIDA Annual Return", name).submit(),
				False,
			)
		commit_stage()
	doc = frappe.get_doc("COIDA Annual Return", name)
	actual = {
		"slips": doc.source_slip_count,
		"employees": doc.total_employees,
		"assessable_uncapped": None,
		"gross_uncapped": flt(doc.uncapped_annual_earnings),
		"assessable_capped": flt(doc.total_annual_earnings),
		"excluded": flt(doc.excluded_annual_earnings),
		"director_earnings": flt(doc.director_earnings),
		"assessment_rate": flt(doc.assessment_rate),
		"cap": flt(doc.coida_annual_earnings_cap),
		"assessment_before_minimum": flt(doc.assessment_before_minimum),
		"minimum_assessment": flt(doc.minimum_assessment),
		"assessment_fee": flt(doc.assessment_fee),
		"status": doc.status,
		"rules": [doc.cap_rate_rule, doc.assessment_rate_rule, doc.minimum_assessment_rule],
	}
	cfg = golden["configured"]
	checks = {
		k: {"golden": cfg[g], "actual": actual[a], "pass": abs(flt(cfg[g]) - flt(actual[a])) <= 0.01}
		for k, g, a in (
			("slip_count", "slips", "slips"),
			("employees", "employees", "employees"),
			("capped_earnings", "assessable_capped", "assessable_capped"),
			("director_earnings", "director_earnings", "director_earnings"),
			("assessment_before_minimum", "assessment_before_minimum", "assessment_before_minimum"),
			("assessment_fee", "assessment_fee", "assessment_fee"),
		)
	}
	monthly = doc.get("monthly_earnings") or []
	monthly_total = flt(sum(flt(m.employee_earnings) + flt(m.director_earnings) for m in monthly), 2)
	checks["monthly_rows"] = {"golden": 12, "actual": len(monthly), "pass": len(monthly) == 12}
	checks["monthly_total_equals_annual"] = {
		"golden": flt(doc.total_annual_earnings),
		"actual": monthly_total,
		"pass": abs(monthly_total - flt(doc.total_annual_earnings)) <= 0.01,
	}
	checks["cap_value"] = {
		"golden": golden()["annual_earnings_cap"],
		"actual": actual["cap"],
		"pass": flt(actual["cap"]) == flt(golden()["annual_earnings_cap"]),
	}
	checks["minimum"] = {
		"golden": golden()["minimum_assessment"],
		"actual": actual["minimum_assessment"],
		"pass": flt(actual["minimum_assessment"]) == flt(golden()["minimum_assessment"]),
	}
	notice_gap = round(golden["notice_2025"]["assessable_capped"] - cfg["assessable_capped"], 2)
	# ROE CF-2A form: per-month employee/director split and free food & quarters are not on the return.
	out = {
		"return": name,
		"actual": actual,
		"golden": golden,
		"checks": checks,
		"tests": r,
		"notice_2025_earnings_gap": notice_gap,
		"notice_2025_fee_gap": round(golden["notice_2025"]["assessment_fee"] - cfg["assessment_fee"], 2),
	}
	(paths.payroll() / "coida_return.json").write_text(json.dumps(out, indent=1, default=str))
	return out


def stage_injury_claim() -> dict:
	require_reference_site()
	r = {}
	employee = employee_for("P13_overtime")
	base = {
		"doctype": "Workplace Injury",
		"employee": employee,
		"company": C.COMPANY,
		"injury_date": "2026-09-14",
		"injury_time": "10:30:00",
		"injury_location": "Synthetic warehouse bay 3",
		"injury_type": "Moderate",
		"severity": "Medium",
		"injury_description": "SYNTHETIC: laceration to left hand from pallet strap (test data).",
		"incident_mechanism": "Struck by released strap",
		"body_part_affected": "Left hand",
		"medical_attention_required": 1,
		"medical_provider": "Synthetic Clinic",
		"requires_leave": 1,
		"leave_days": 3,
		"requires_claim": 1,
		"status": "Reported",
		"injury_leave_type": "ZA Occupational Injury Leave",
		"investigation_summary": "SYNTHETIC: strap tension release; retraining scheduled (test data).",
	}
	injury = frappe.db.get_value("Workplace Injury", {"employee": employee, "docstatus": 1}, "name")
	_allocate(employee, "ZA Occupational Injury Leave", 30)
	frappe.db.set_value("Employee", employee, "leave_approver", user("hr_manager"))
	frappe.db.delete("Workplace Injury", {"employee": employee, "docstatus": 0})
	commit_stage()
	with acting_as(user("payroll_user")):
		outcome(r, "payroll_user_cannot_create_injury", lambda: frappe.get_doc(dict(base)).insert(), True)
	with acting_as(user("employee")):
		outcome(
			r,
			"employee_self_service_cannot_read_injuries",
			lambda: frappe.get_list("Workplace Injury", fields=["name", "injury_description"]) or None,
			True,
		)
		outcome(
			r,
			"employee_cannot_read_oid_claims",
			lambda: frappe.get_list("OID Claim", fields=["name", "id_number"]) or None,
			True,
		)
	with acting_as(user("accounts_user")):
		outcome(
			r,
			"accounts_user_cannot_read_injuries",
			lambda: frappe.get_list("Workplace Injury", fields=["name"]) or None,
			True,
		)
	with acting_as(user("hr_manager")):
		outcome(
			r,
			"future_injury_date",
			lambda: frappe.get_doc({**base, "injury_date": "2027-12-01"}).insert(),
			True,
		)
		if not injury:
			doc = frappe.get_doc(dict(base))
			doc.insert()
			r["deadline_after_insert"] = {
				"due": str(doc.statutory_report_due_on),
				"status": doc.statutory_deadline_status,
			}
			doc.submit()
			commit_stage()
			injury = doc.name
		inj = frappe.get_doc("Workplace Injury", injury)
		r["injury"] = {
			"name": inj.name,
			"status": inj.status,
			"due": str(inj.statutory_report_due_on),
			"deadline_status": inj.statutory_deadline_status,
			"oid_claim": inj.oid_claim,
			"leave": inj.leave_application,
		}
		claim = inj.oid_claim
		c = frappe.get_doc("OID Claim", claim)
		r["claim_auto_created"] = {
			"name": c.name,
			"status": c.claim_status,
			"docstatus": c.docstatus,
			"id_number_present": bool(c.id_number),
		}
		public = (
			frappe.get_doc(
				{
					"doctype": "File",
					"file_name": "public-oid-report.txt",
					"is_private": 0,
					"content": b"SYNTHETIC public medical report",
				}
			)
			.insert(ignore_permissions=True)
			.file_url
		)
		private = _private("oid-first-medical-report.txt")

		def report(attachment):
			d = frappe.get_doc("OID Claim", claim)
			d.append(
				"medical_reports",
				{
					"report_date": "2026-09-14",
					"medical_provider": "Synthetic Clinic",
					"report_type": "Initial Assessment",
					"diagnosis": "SYNTHETIC laceration",
					"attachment": attachment,
				},
			)
			d.save()

		if c.docstatus == 0:
			outcome(r, "public_medical_report_attachment", lambda: report(public), True)
			outcome(r, "private_medical_report_attachment", lambda: report(private), False)
			outcome(r, "claim_submit", lambda: frappe.get_doc("OID Claim", claim).submit(), False)
			c = frappe.get_doc("OID Claim", claim)
			outcome(r, "skip_to_paid", lambda: c.update_claim_status("Paid", payment_date="2026-10-20"), True)
			outcome(r, "approve_without_amount", lambda: c.update_claim_status("Approved"), True)
			for status, kwargs in (
				("Under Review", {}),
				("Approved", {"compensation_amount": 4250}),
				# Paid on the day the harness runs: a claim cannot be paid before it is lodged.
				("Paid", {"payment_date": frappe.utils.today()}),
			):
				outcome(
					r,
					f"transition_{status}",
					lambda s=status, k=kwargs: frappe.get_doc("OID Claim", claim).update_claim_status(s, **k),
					False,
				)
			outcome(
				r,
				"paid_back_to_pending",
				lambda: frappe.get_doc("OID Claim", claim).update_claim_status("Pending"),
				True,
			)
	c = frappe.get_doc("OID Claim", claim)
	inj = frappe.get_doc("Workplace Injury", injury)
	r["final"] = {
		"claim_status": c.claim_status,
		"amount": c.compensation_amount,
		"paid": str(c.payment_date),
		"injury_status": inj.status,
		"leave_application": inj.leave_application,
		"leave_docstatus": frappe.db.get_value("Leave Application", inj.leave_application, "docstatus"),
	}
	with acting_as(user("hr_manager")):

		def cancel_cascade():
			d = frappe.get_doc(
				{
					**base,
					"injury_date": "2026-09-28",
					"injury_description": "SYNTHETIC: captured in error (test).",
				}
			)
			d.insert()
			d.submit()
			claim_name, leave_name = d.oid_claim, d.leave_application
			frappe.get_doc("Workplace Injury", d.name).cancel()
			return {
				"injury": frappe.db.get_value("Workplace Injury", d.name, "docstatus"),
				"draft_claim_deleted": not frappe.db.exists("OID Claim", claim_name),
				"draft_leave_deleted": not frappe.db.exists("Leave Application", leave_name),
			}

		outcome(r, "hr_manager_cancel_injury", cancel_cascade, False)
	outcome(r, "injury_cancel_cascades_drafts_administrator", cancel_cascade, False)

	def cancel_submitted_claim():
		d = frappe.get_doc(
			{**base, "injury_date": "2026-09-29", "injury_description": "SYNTHETIC: claim withdrawn (test)."}
		)
		d.insert()
		d.submit()
		c = frappe.get_doc("OID Claim", d.oid_claim)
		c.submit()
		frappe.get_doc("OID Claim", c.name).cancel()
		frappe.get_doc("Workplace Injury", d.name).cancel()
		return frappe.db.get_value("OID Claim", c.name, ["docstatus", "claim_status"])

	outcome(r, "submitted_claim_and_injury_cancel_administrator", cancel_submitted_claim, False)
	r["injury_privacy_fields"] = {
		f.fieldname: f.permlevel
		for f in frappe.get_meta("Workplace Injury").fields
		if f.fieldname
		in ("injury_description", "investigation_summary", "witness_details", "body_part_affected")
	}
	r["oid_privacy_fields"] = {
		f.fieldname: f.permlevel
		for f in frappe.get_meta("OID Claim").fields
		if f.fieldname in ("id_number", "injury_description", "medical_reports")
	}
	(paths.payroll() / "coida_injury_claim.json").write_text(json.dumps(r, indent=1, default=str))
	return r
