"""BCEA leave standards: statutory minimums, service cycles and policy templates.

The numbers live in ``setup/data/bcea_leave_standards.json``. This module holds the
pure logic (no database writes) so it can be unit tested and reused by the seeding
and assignment code in ``za_local_payroll.setup.leave_standards``.
"""

from __future__ import annotations

from functools import lru_cache

import frappe
from frappe import _
from frappe.utils import add_days, add_months, cint, getdate
from za_local_core.files import read_packaged_json

# Leave Type names this app owns. The suffix keeps them apart from the HRMS defaults
# ("Sick Leave", "Privilege Leave") that a client may already use.
ANNUAL = "Annual Leave (BCEA)"
SICK = "Sick Leave (BCEA)"
FAMILY = "Family Responsibility Leave (BCEA)"
MATERNITY = "Maternity Leave (BCEA)"
PARENTAL = "Parental Leave (BCEA)"
ADOPTION = "Adoption Leave (BCEA)"
COMMISSIONING = "Commissioning Parental Leave (BCEA)"
OCCUPATIONAL_INJURY = "Occupational Injury Leave (BCEA)"

SUPPORTED_WORK_WEEKS = (5, 6)


@lru_cache(maxsize=1)
def get_standards() -> dict:
	"""Return the packaged BCEA leave standards."""
	return read_packaged_json("za_local_payroll", "setup", "data", "bcea_leave_standards.json")


def _week_key(work_days_per_week: int) -> str:
	if cint(work_days_per_week) not in SUPPORTED_WORK_WEEKS:
		frappe.throw(
			_("The BCEA leave templates cover a 5-day or a 6-day work week, not {0} days.").format(
				work_days_per_week
			),
			title=_("Unsupported Work Week"),
		)
	return str(cint(work_days_per_week))


def annual_leave_days(work_days_per_week: int) -> int:
	return cint(get_standards()["annual_leave"]["working_days_by_week"][_week_key(work_days_per_week)])


def sick_leave_days(work_days_per_week: int) -> int:
	return cint(get_standards()["sick_leave"]["working_days_by_week"][_week_key(work_days_per_week)])


def family_leave_days() -> int:
	return cint(get_standards()["family_responsibility_leave"]["days"])


def family_leave_min_service_months() -> int:
	return cint(get_standards()["family_responsibility_leave"]["min_service_months"])


def service_cycle(date_of_joining, reference_date, cycle_months: int) -> tuple:
	"""Return the (start, end) of the service cycle that contains ``reference_date``.

	Cycles run from the date of joining in blocks of ``cycle_months`` (12 for annual and
	family responsibility leave, 36 for sick leave), never from a calendar or tax year.
	"""
	if not date_of_joining:
		frappe.throw(_("Date of Joining is required to work out a leave cycle."))
	joining, reference = getdate(date_of_joining), getdate(reference_date)
	if reference < joining:
		frappe.throw(
			_("The reference date {0} is before the date of joining {1}.").format(reference, joining)
		)
	blocks = 0
	while add_months(joining, (blocks + 1) * cycle_months) <= reference:
		blocks += 1
	start = add_months(joining, blocks * cycle_months)
	end = add_days(add_months(joining, (blocks + 1) * cycle_months), -1)
	return start, end


def minimum_for(leave_type: str, work_days_per_week: int) -> int:
	"""Statutory minimum days for a template Leave Type and work week."""
	if leave_type == ANNUAL:
		return annual_leave_days(work_days_per_week)
	if leave_type == SICK:
		return sick_leave_days(work_days_per_week)
	if leave_type == FAMILY:
		return family_leave_days()
	frappe.throw(_("{0} has no allocated statutory minimum.").format(leave_type))


def leave_type_specs() -> list[dict]:
	"""Leave Type field values for every BCEA type, keyed by name.

	``za_*`` fields are the SA Labour custom fields. Types that are not allocated by a
	policy (maternity, parental and so on) are unpaid by the employer: UIF pays the
	benefit, so they are leave without pay in HRMS.
	"""
	standards = get_standards()
	annual = standards["annual_leave"]
	sick = standards["sick_leave"]
	family = standards["family_responsibility_leave"]
	return [
		{
			"leave_type_name": ANNUAL,
			"za_bcea_leave_category": "Annual Leave",
			"is_earned_leave": 1,
			"earned_leave_frequency": annual["accrual_frequency"],
			"allocate_on_day": "Date of Joining",
			"rounding": "0.25",
			"is_carry_forward": 1,
			"expire_carry_forwarded_leaves_after_days": annual["take_within_days_after_cycle"],
			"include_holiday": 0,
			"allow_encashment": 0,
		},
		{
			"leave_type_name": SICK,
			"za_bcea_leave_category": "Sick Leave",
			"za_medical_certificate_required_after": sick["medical_certificate_after_consecutive_days"],
			"include_holiday": 0,
		},
		{
			"leave_type_name": FAMILY,
			"za_bcea_leave_category": "Family Responsibility Leave",
			"applicable_after": family["min_service_months"] * 30,
			"include_holiday": 0,
		},
		{
			"leave_type_name": MATERNITY,
			"za_bcea_leave_category": "Maternity Leave",
			"za_applicable_gender": "Female",
			"is_lwp": 1,
			"include_holiday": 1,
		},
		{
			"leave_type_name": PARENTAL,
			"za_bcea_leave_category": "Parental Leave",
			"is_lwp": 1,
			"include_holiday": 1,
		},
		{
			"leave_type_name": ADOPTION,
			"za_bcea_leave_category": "Adoption Leave",
			"is_lwp": 1,
			"include_holiday": 1,
		},
		{
			"leave_type_name": COMMISSIONING,
			"za_bcea_leave_category": "Commissioning Parental Leave",
			"is_lwp": 1,
			"include_holiday": 1,
		},
		{
			"leave_type_name": OCCUPATIONAL_INJURY,
			"za_bcea_leave_category": "Occupational Injury Leave",
			"is_lwp": 0,
			"include_holiday": 0,
		},
	]


def policy_templates() -> list[dict]:
	"""Template Leave Policies: title, assignment cycle in months and allocations.

	Only annual and family responsibility leave live in a policy. They share the 12-month
	service cycle. Sick leave runs on a 36-month cycle and HRMS allows one submitted
	Leave Policy Assignment per employee for any overlapping period, so a second policy
	for sick leave cannot be assigned alongside the annual one. Sick leave is therefore
	granted as a direct Leave Allocation per employee (see ``sick_leave_allocation``).
	"""
	return [
		{
			"title": f"SA BCEA Annual and Family Leave - {weeks}-day week",
			"cycle_months": get_standards()["annual_leave"]["cycle_months"],
			"work_days_per_week": weeks,
			"allocations": {ANNUAL: annual_leave_days(weeks), FAMILY: family_leave_days()},
		}
		for weeks in SUPPORTED_WORK_WEEKS
	]


def sick_leave_allocation(
	date_of_joining,
	reference_date,
	work_days_per_week: int,
	sick_days: float | None = None,
	already_taken: float = 0,
) -> dict:
	"""Dates and days for an employee's sick leave allocation in the current 36-month cycle.

	``already_taken`` is sick leave used earlier in the cycle outside this system, so an
	employee going live part-way through a cycle is not given a fresh entitlement.
	"""
	standards = get_standards()["sick_leave"]
	days = float(sick_days) if sick_days not in (None, "") else float(sick_leave_days(work_days_per_week))
	validate_not_below_minimum({SICK: days}, work_days_per_week)
	if already_taken < 0 or already_taken > days:
		frappe.throw(_("Sick leave already taken must be between 0 and {0} days.").format(days))
	start, end = service_cycle(date_of_joining, reference_date, cint(standards["cycle_months"]))
	return {"from_date": start, "to_date": end, "days": days - already_taken}


def validate_not_below_minimum(allocations: dict[str, float], work_days_per_week: int) -> None:
	"""Refuse a company policy that grants less than the statutory minimum."""
	for leave_type, days in allocations.items():
		minimum = minimum_for(leave_type, work_days_per_week)
		if days < minimum:
			frappe.throw(
				_("{0}: {1} days is below the BCEA minimum of {2} days for a {3}-day week.").format(
					leave_type, days, minimum, work_days_per_week
				),
				title=_("Below Statutory Minimum"),
			)
