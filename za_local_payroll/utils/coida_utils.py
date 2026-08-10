"""Utilities for Compensation Fund assessment and claim reporting."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt

from za_local_payroll.services.statutory_rates import (
	get_coida_annual_earnings_cap,
	resolve_coida_industry_rate,
)

EXCLUDED_PAYROLL_TREATMENTS = {
	"Non-Taxable Reimbursement",
	"Reimbursive Travel",
	"Working Paper Only",
}


def calculate_coida_contribution(assessable_remuneration, industry_rate):
	"""Return the assessment amount for an assessable remuneration base."""
	if not assessable_remuneration or not industry_rate:
		return 0

	return flt(flt(assessable_remuneration) * flt(industry_rate) / 100, 2)


def get_company_industry_rate(company, industry_class=None, date_value=None):
	"""Return one approved assessment rate for a company and class."""
	return flt(resolve_coida_industry_rate(company, industry_class, date_value).value)


def validate_industry_rates(industry_rates):
	"""Validate COIDA Settings child rows and return all configuration errors."""
	errors = []
	seen = set()

	if not industry_rates:
		return {"valid": False, "errors": [_("At least one industry rate must be configured")]}

	for row in industry_rates:
		if not row.industry_class:
			errors.append(_("Industry class is required"))

		rate = flt(row.assessment_rate)
		if rate <= 0:
			errors.append(
				_("Assessment rate for industry class {0} must be greater than zero").format(
					row.industry_class or _("Not specified")
				)
			)
		elif rate > 100:
			errors.append(
				_("Assessment rate for industry class {0} cannot exceed 100%").format(row.industry_class)
			)

		key = (row.get("company") or "", row.industry_class or "")
		if key in seen:
			errors.append(
				_("Duplicate COIDA rate for company {0} and industry class {1}").format(
					row.get("company") or _("All Companies"), row.industry_class or _("Not specified")
				)
			)
		seen.add(key)

	return {"valid": not errors, "errors": errors}


def get_coida_salary_slip_rows(company, from_date, to_date):
	"""Return one deterministic source row per submitted Salary Slip.

	A slip belongs to the assessment period containing its end date. This avoids
	dropping cross-boundary payroll periods and prevents one slip being counted in
	two annual returns.
	"""
	frappe.has_permission("Salary Slip", "read", throw=True)
	salary_slip_meta = frappe.get_meta("Salary Slip")
	if salary_slip_meta.has_field("za_coida_basis"):
		return frappe.db.sql(
			"""
				SELECT ss.name AS salary_slip, ss.employee, ss.start_date, ss.end_date,
					ss.gross_pay AS gross_earnings,
					IFNULL(ss.za_coida_basis, 0) AS assessable_earnings
				FROM `tabSalary Slip` ss
				WHERE ss.company = %(company)s
					AND ss.end_date BETWEEN %(from_date)s AND %(to_date)s
					AND ss.docstatus = 1
				ORDER BY ss.employee, ss.end_date, ss.name
			""",
			{"company": company, "from_date": from_date, "to_date": to_date},
			as_dict=True,
		)

	# Every field below is created at install and refreshed on migrate. Dropping a
	# condition because its field is absent would silently narrow the leviable base
	# of a statutory return, so an incomplete install fails here instead.
	component_meta = frappe.get_meta("Salary Component")
	detail_meta = frappe.get_meta("Salary Detail")
	missing_fields = [
		f"Salary Component.{fieldname}"
		for fieldname in ("za_coida_applicable", "za_is_reimbursement", "za_payroll_treatment")
		if not component_meta.has_field(fieldname)
	] + [
		f"Salary Detail.{fieldname}"
		for fieldname in ("statistical_component", "do_not_include_in_total")
		if not detail_meta.has_field(fieldname)
	]
	if missing_fields:
		frappe.throw(
			_("COIDA earnings cannot be calculated. Run bench migrate to restore: {0}").format(
				", ".join(missing_fields)
			)
		)

	return frappe.db.sql(
		"""
			SELECT ss.name AS salary_slip, ss.employee, ss.start_date, ss.end_date,
				ss.gross_pay AS gross_earnings,
				SUM(
					CASE
						WHEN IFNULL(sc.za_coida_applicable, 0) = 1
							AND IFNULL(sc.za_is_reimbursement, 0) = 0
							AND IFNULL(sc.za_payroll_treatment, '') NOT IN %(excluded_treatments)s
							AND IFNULL(sd.statistical_component, 0) = 0
							AND IFNULL(sd.do_not_include_in_total, 0) = 0
						THEN IFNULL(sd.amount, 0)
						ELSE 0
					END
				) AS assessable_earnings
			FROM `tabSalary Slip` ss
			LEFT JOIN `tabSalary Detail` sd
				ON sd.parent = ss.name
				AND sd.parenttype = 'Salary Slip'
				AND sd.parentfield = 'earnings'
			LEFT JOIN `tabSalary Component` sc ON sc.name = sd.salary_component
			WHERE ss.company = %(company)s
				AND ss.end_date BETWEEN %(from_date)s AND %(to_date)s
				AND ss.docstatus = 1
			GROUP BY ss.name, ss.employee, ss.start_date, ss.end_date, ss.gross_pay
			ORDER BY ss.employee, ss.end_date, ss.name
		""",
		{
			"company": company,
			"from_date": from_date,
			"to_date": to_date,
			"excluded_treatments": tuple(EXCLUDED_PAYROLL_TREATMENTS),
		},
		as_dict=True,
	)


def get_coida_earnings_by_employee(company, from_date, to_date):
	"""Aggregate deterministic source rows by employee."""
	result = {}
	for row in get_coida_salary_slip_rows(company, from_date, to_date):
		totals = result.setdefault(
			row.employee,
			frappe._dict(gross_total=0, assessable_total=0),
		)
		totals.gross_total += flt(row.gross_earnings)
		totals.assessable_total += flt(row.assessable_earnings)
	return result


def calculate_annual_coida(company, from_date, to_date, industry_class=None):
	"""Calculate capped COIDA assessable earnings and the assessment amount."""
	earnings = get_coida_earnings_by_employee(company, from_date, to_date)
	cap = get_coida_annual_earnings_cap(from_date)
	gross_remuneration = sum(row.gross_total for row in earnings.values())
	uncapped_assessable = sum(row.assessable_total for row in earnings.values())
	total_remuneration = sum(min(row.assessable_total, cap) for row in earnings.values())
	industry_rate = get_company_industry_rate(company, industry_class, from_date)

	return {
		"total_remuneration": flt(total_remuneration, 2),
		"uncapped_remuneration": flt(gross_remuneration, 2),
		"uncapped_assessable_remuneration": flt(uncapped_assessable, 2),
		"excluded_remuneration": flt(max(0, gross_remuneration - total_remuneration), 2),
		"total_coida": calculate_coida_contribution(total_remuneration, industry_rate),
		"employee_count": len(earnings),
		"earnings_cap": cap,
		"industry_rate": industry_rate,
	}


def get_workplace_injuries_for_period(company, from_date, to_date):
	"""Return permission-filtered, non-medical injury summary fields."""
	return frappe.get_list(
		"Workplace Injury",
		filters={"company": company, "injury_date": ["between", [from_date, to_date]]},
		fields=[
			"name",
			"employee",
			"employee_name",
			"company",
			"injury_date",
			"injury_type",
			"severity",
			"status",
			"oid_claim",
		],
		order_by="injury_date desc",
	)


def get_oid_claims_for_period(company, from_date, to_date, status=None):
	"""Return permission-filtered claim summary fields without medical details."""
	filters = {"company": company, "claim_date": ["between", [from_date, to_date]]}
	if status:
		filters["claim_status"] = status

	return frappe.get_list(
		"OID Claim",
		filters=filters,
		fields=[
			"name",
			"employee",
			"company",
			"workplace_injury",
			"claim_reference",
			"claim_date",
			"claim_status",
			"compensation_amount",
		],
		order_by="claim_date desc",
	)
