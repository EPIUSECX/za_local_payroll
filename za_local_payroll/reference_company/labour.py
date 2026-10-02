"""Stage 10: BCEA leave, termination decision support and labour statutory rates."""

import json

import frappe
from frappe.utils.file_manager import save_file

from za_local_payroll.reference_company import constants as C
from za_local_payroll.reference_company.governance import acting_as, user
from za_local_payroll.reference_company.guard import require_reference_site
from za_local_payroll.reference_company.payroll_run import employee_for
from za_local_payroll.reference_company.payroll_setup import EVIDENCE

LEAVE_TYPES = {
	"ZA Annual Leave": {"za_bcea_leave_category": "Annual Leave", "max_leaves_allowed": 21},
	"ZA Sick Leave": {
		"za_bcea_leave_category": "Sick Leave",
		"za_medical_certificate_required_after": 2,
		"max_leaves_allowed": 30,
	},
	"ZA Family Responsibility Leave": {
		"za_bcea_leave_category": "Family Responsibility Leave",
		"max_leaves_allowed": 3,
	},
	"ZA Maternity Leave": {
		"za_bcea_leave_category": "Maternity Leave",
		"za_applicable_gender": "Female",
		"max_leaves_allowed": 120,
	},
	"ZA Occupational Injury Leave": {
		"za_bcea_leave_category": "Occupational Injury Leave",
		"max_leaves_allowed": 365,
	},
}


def outcome(results, label, fn, expect_block):
	frappe.db.commit()
	try:
		value = fn()
		frappe.db.commit()
		results[label] = {
			"expected": "blocked" if expect_block else "allowed",
			"actual": "allowed",
			"pass": not expect_block,
			"detail": str(value)[:200] if value else None,
		}
	except Exception as exc:
		frappe.db.rollback()
		results[label] = {
			"expected": "blocked" if expect_block else "allowed",
			"actual": "blocked",
			"pass": expect_block,
			"detail": frappe.utils.strip_html(str(exc))[:240],
		}


def _leave_type(name, values):
	if not frappe.db.exists("Leave Type", name):
		frappe.get_doc(
			{
				"doctype": "Leave Type",
				"leave_type_name": name,
				"allow_negative": 0,
				"za_bcea_compliant": 1,
				**values,
			}
		).insert(ignore_permissions=True)
	return name


def _allocate(employee, leave_type, days):
	if frappe.db.exists("Leave Allocation", {"employee": employee, "leave_type": leave_type, "docstatus": 1}):
		return
	doc = frappe.get_doc(
		{
			"doctype": "Leave Allocation",
			"employee": employee,
			"leave_type": leave_type,
			"from_date": "2026-03-01",
			"to_date": "2027-02-28",
			"new_leaves_allocated": days,
		}
	)
	doc.insert(ignore_permissions=True)
	doc.submit()


def _leave(employee, leave_type, start, end, certificate=None, submit=True):
	doc = frappe.get_doc(
		{
			"doctype": "Leave Application",
			"employee": employee,
			"leave_type": leave_type,
			"from_date": start,
			"to_date": end,
			"status": "Approved" if submit else "Open",
			"leave_approver": "Administrator",
			"za_medical_certificate": certificate,
			"company": C.COMPANY,
		}
	)
	doc.insert(ignore_permissions=True)
	if submit:
		doc.submit()
	return doc.name


def stage_leave_tests() -> dict:
	require_reference_site()
	for name, values in LEAVE_TYPES.items():
		_leave_type(name, values)
	female, male = employee_for("P02_normal"), employee_for("P13_overtime")
	for emp in (female, male):
		for lt, days in (
			("ZA Sick Leave", 30),
			("ZA Family Responsibility Leave", 3),
			("ZA Annual Leave", 21),
			("Casual Leave", 5),
		):
			_allocate(emp, lt, days)
	_allocate(female, "ZA Maternity Leave", 120)
	_allocate(male, "ZA Maternity Leave", 120)
	frappe.db.commit()
	cert = save_file(
		"synthetic-medical-certificate.txt",
		b"SYNTHETIC medical certificate - test data only",
		None,
		None,
		is_private=1,
	).file_url
	public = save_file(
		"public-medical-certificate.txt", b"SYNTHETIC public certificate", None, None, is_private=0
	).file_url
	r = {}
	outcome(
		r,
		"non_governed_leave_standard_rules",
		lambda: _leave(female, "Casual Leave", "2026-10-05", "2026-10-06"),
		False,
	)
	outcome(
		r,
		"sick_3_days_without_certificate",
		lambda: _leave(female, "ZA Sick Leave", "2026-10-12", "2026-10-14", submit=False),
		True,
	)
	outcome(
		r,
		"sick_3_days_public_certificate",
		lambda: _leave(female, "ZA Sick Leave", "2026-10-12", "2026-10-14", public, submit=False),
		True,
	)
	outcome(
		r,
		"sick_3_days_private_certificate",
		lambda: _leave(female, "ZA Sick Leave", "2026-10-12", "2026-10-14", cert),
		False,
	)
	outcome(
		r,
		"sick_occasion_2_one_day",
		lambda: _leave(female, "ZA Sick Leave", "2026-10-20", "2026-10-20"),
		False,
	)
	outcome(
		r,
		"sick_occasion_3_within_8_weeks_no_certificate",
		lambda: _leave(female, "ZA Sick Leave", "2026-11-03", "2026-11-03", submit=False),
		True,
	)
	outcome(
		r,
		"family_responsibility_2_days",
		lambda: _leave(male, "ZA Family Responsibility Leave", "2026-10-19", "2026-10-20"),
		False,
	)
	outcome(
		r,
		"family_responsibility_exceeds_3_days",
		lambda: _leave(male, "ZA Family Responsibility Leave", "2026-11-09", "2026-11-10", submit=False),
		True,
	)
	outcome(
		r,
		"gender_restricted_leave_wrong_gender",
		lambda: _leave(male, "ZA Maternity Leave", "2026-12-01", "2026-12-05", submit=False),
		True,
	)
	outcome(
		r,
		"gender_restricted_leave_matching_gender",
		lambda: _leave(female, "ZA Maternity Leave", "2027-01-04", "2027-01-08", submit=False),
		False,
	)
	(EVIDENCE / "labour_leave_tests.json").write_text(json.dumps(r, indent=1, default=str))
	return r


def stage_rate_tests() -> dict:
	require_reference_site()
	from za_local_payroll.services.statutory_rates import (
		resolve_bcea_earnings_threshold,
		resolve_coida_cap,
		resolve_coida_industry_rate,
		resolve_coida_minimum_assessment,
		resolve_nmw_rate,
	)

	r = {}
	outcome(
		r, "bcea_threshold_2026-04-15_no_pack", lambda: resolve_bcea_earnings_threshold("2026-04-15"), True
	)
	outcome(
		r, "bcea_threshold_2026-06-15", lambda: resolve_bcea_earnings_threshold("2026-06-15").value, False
	)
	outcome(r, "nmw_general_2026-06-15", lambda: resolve_nmw_rate("General NMW", "2026-06-15").value, False)
	outcome(r, "nmw_epwp_2026-03-10", lambda: resolve_nmw_rate("EPWP", "2026-03-10").value, False)
	outcome(
		r,
		"nmw_sector_specific_not_automated",
		lambda: resolve_nmw_rate("Sector-specific", "2026-06-15"),
		True,
	)
	outcome(r, "nmw_before_any_pack_2026-02-15", lambda: resolve_nmw_rate("General NMW", "2026-02-15"), True)
	outcome(r, "coida_cap_2026-09-30", lambda: resolve_coida_cap("2026-09-30").value, False)
	outcome(
		r,
		"coida_minimum_general",
		lambda: resolve_coida_minimum_assessment("General Employer", "2026-09-30").value,
		False,
	)
	outcome(
		r,
		"coida_minimum_domestic",
		lambda: resolve_coida_minimum_assessment("Domestic Employer", "2026-09-30").value,
		False,
	)
	outcome(
		r,
		"coida_rate_company_class_9",
		lambda: resolve_coida_industry_rate(C.COMPANY, "9", "2026-09-30").value,
		False,
	)
	outcome(
		r,
		"coida_rate_unknown_class_fails",
		lambda: resolve_coida_industry_rate(C.COMPANY, "77", "2026-09-30"),
		True,
	)
	outcome(r, "coida_cap_before_pack_2026-02-01", lambda: resolve_coida_cap("2026-02-01"), True)
	(EVIDENCE / "labour_rate_tests.json").write_text(json.dumps(r, indent=1, default=str))
	return r


def stage_termination_tests() -> dict:
	require_reference_site()
	r = {}
	hr = user("hr_manager")

	def separation(employee, termination_type, termination_date, weekly=None, reviewed=False, submit=False):
		doc = frappe.get_doc(
			{
				"doctype": "Employee Separation",
				"employee": employee,
				"company": C.COMPANY,
				"boarding_begins_on": termination_date,
				"resignation_letter_date": termination_date,
				"za_termination_type": termination_type,
				"za_termination_date": termination_date,
				"za_bcea_weekly_remuneration": weekly,
				"za_bcea_daily_remuneration": (weekly or 0) / 5,
				"za_bcea_remuneration_basis": "Synthetic: basic salary x 12 / 52; no variable pay"
				if weekly
				else None,
				"za_bcea_remuneration_reviewed": int(reviewed),
			}
		)
		doc.insert(ignore_permissions=True)
		out = {
			"notice_days": doc.za_notice_period_days,
			"service_years": doc.za_completed_service_years,
			"severance": doc.za_severance_pay,
			"leave_days": doc.za_leave_payout_days,
			"leave_payout": doc.za_leave_payout,
		}
		frappe.db.rollback()
		return out

	five_months = employee_for("P20_it3a_no_paye")  # joined 2026-06-01
	twelve_years = employee_for("P13_overtime")  # joined 2023-02-01
	outcome(r, "missing_termination_type", lambda: separation(twelve_years, None, "2026-10-31"), True)
	outcome(
		r, "termination_before_joining", lambda: separation(five_months, "Resignation", "2026-05-01"), True
	)
	outcome(r, "notice_under_6_months", lambda: separation(five_months, "Resignation", "2026-10-31"), False)
	outcome(r, "notice_6_to_12_months", lambda: separation(five_months, "Resignation", "2026-12-15"), False)
	outcome(
		r,
		"over_1_year_without_reviewed_remuneration",
		lambda: separation(twelve_years, "Resignation", "2026-10-31"),
		True,
	)
	outcome(
		r,
		"non_operational_zero_severance",
		lambda: separation(twelve_years, "Dismissal - Misconduct", "2026-10-31", 4153.85, True),
		False,
	)
	outcome(
		r,
		"operational_without_reviewed_remuneration",
		lambda: separation(twelve_years, "Dismissal - Operational", "2026-10-31"),
		True,
	)
	with acting_as(hr):
		outcome(
			r,
			"operational_with_reviewed_remuneration",
			lambda: separation(twelve_years, "Dismissal - Operational", "2026-10-31", 4153.85, True),
			False,
		)
	with acting_as(user("payroll_user")):
		outcome(
			r,
			"non_hr_manager_confirms_remuneration",
			lambda: separation(twelve_years, "Dismissal - Operational", "2026-10-31", 4153.85, True),
			True,
		)
	(EVIDENCE / "labour_termination_tests.json").write_text(json.dumps(r, indent=1, default=str))
	return r


def stage_sick_occasion_retest() -> dict:
	"""Clean re-run of the sick-leave controls with submitted prior occasions (male persona P14)."""
	require_reference_site()
	employee = employee_for("P14_commission")
	for lt, days in (("ZA Sick Leave", 30),):
		_allocate(employee, lt, days)
	cert = save_file(
		"synthetic-medical-certificate-p14.txt",
		b"SYNTHETIC medical certificate P14 - test data",
		None,
		None,
		is_private=1,
	).file_url
	public = save_file(
		"public-medical-certificate-p14.txt", b"SYNTHETIC public certificate P14", None, None, is_private=0
	).file_url
	r = {}
	outcome(
		r,
		"occasion_1_three_days_private_certificate",
		lambda: _leave(employee, "ZA Sick Leave", "2026-10-05", "2026-10-07", cert),
		False,
	)
	outcome(
		r, "occasion_2_one_day", lambda: _leave(employee, "ZA Sick Leave", "2026-10-13", "2026-10-13"), False
	)
	outcome(
		r,
		"occasion_3_within_8_weeks_without_certificate",
		lambda: _leave(employee, "ZA Sick Leave", "2026-10-27", "2026-10-27", submit=False),
		True,
	)
	outcome(
		r,
		"occasion_3_with_private_certificate",
		lambda: _leave(employee, "ZA Sick Leave", "2026-10-27", "2026-10-27", cert),
		False,
	)
	outcome(
		r,
		"three_days_with_PUBLIC_certificate",
		lambda: _leave(employee, "ZA Sick Leave", "2026-11-16", "2026-11-18", public, submit=False),
		True,
	)
	(EVIDENCE / "labour_sick_retest.json").write_text(json.dumps(r, indent=1, default=str))
	return r
