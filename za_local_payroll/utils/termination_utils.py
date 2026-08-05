"""BCEA termination and settlement calculations."""

from __future__ import annotations

from datetime import date

import frappe
from frappe import _
from frappe.utils import add_months, add_years, cint, flt, getdate
from hrms.hr.doctype.leave_application.leave_application import get_leave_balance_on

ANNUAL_LEAVE_CATEGORY = "Annual Leave"
OPERATIONAL_DISMISSAL = "Dismissal - Operational"


def calculate_bcea_notice_period(employee, termination_date) -> int:
	"""Return the minimum notice period from exact service milestones."""
	employee_doc = _get_employee(employee)
	joining_date, actual_termination_date = _validate_service_dates(
		employee_doc.date_of_joining, termination_date
	)

	if actual_termination_date < add_months(joining_date, 6):
		return 7
	if actual_termination_date < add_years(joining_date, 1):
		return 14
	return 28


def calculate_completed_service_years(date_of_joining, termination_date) -> int:
	"""Return whole years completed on the employee's service anniversary."""
	joining_date, actual_termination_date = _validate_service_dates(date_of_joining, termination_date)
	years = actual_termination_date.year - joining_date.year
	if add_years(joining_date, years) > actual_termination_date:
		years -= 1
	return max(0, years)


def calculate_severance_pay(
	employee,
	termination_date,
	termination_type,
	*,
	weekly_remuneration=None,
	remuneration_reviewed: bool = False,
) -> float:
	"""Calculate operational-requirements severance from a reviewed weekly snapshot."""
	if termination_type != OPERATIONAL_DISMISSAL:
		return 0.0

	employee_doc = _get_employee(employee)
	completed_years = calculate_completed_service_years(employee_doc.date_of_joining, termination_date)
	if completed_years < 1:
		return 0.0

	weekly_rate = _require_reviewed_remuneration(
		weekly_remuneration,
		remuneration_reviewed,
		_("Reviewed BCEA Weekly Remuneration"),
	)
	return flt(weekly_rate * completed_years, 2)


def get_annual_leave_balance_on_termination(employee, termination_date) -> dict[str, float]:
	"""Return positive HRMS ledger balances for governed annual-leave types."""
	if not termination_date:
		frappe.throw(
			_("Actual Termination Date is required for annual-leave settlement."),
			title=_("Termination Date Required"),
		)
	employee_name = employee if isinstance(employee, str) else employee.name
	actual_termination_date = getdate(termination_date)
	leave_types = frappe.get_all(
		"Leave Type",
		filters={
			"za_bcea_compliant": 1,
			"za_bcea_leave_category": ANNUAL_LEAVE_CATEGORY,
			"is_lwp": 0,
		},
		pluck="name",
	)
	if not leave_types:
		frappe.throw(
			_(
				"No governed annual Leave Type is configured. Set BCEA Leave Category to "
				"Annual Leave before calculating a final settlement."
			),
			title=_("Annual Leave Configuration Required"),
		)

	balances = {}
	for leave_type in leave_types:
		balance = get_leave_balance_on(
			employee_name,
			leave_type,
			actual_termination_date,
			to_date=actual_termination_date,
			consider_all_leaves_in_the_allocation_period=False,
		)
		balances[leave_type] = max(0.0, flt(balance))
	return balances


def calculate_leave_payout_on_termination(
	employee,
	termination_date,
	*,
	daily_remuneration=None,
	remuneration_reviewed: bool = False,
) -> dict:
	"""Calculate leave payout from ledger days and a reviewed daily snapshot."""
	balances = get_annual_leave_balance_on_termination(employee, termination_date)
	total_days = flt(sum(balances.values()), 4)
	if not total_days:
		return {"days": 0.0, "amount": 0.0, "balances": balances}

	daily_rate = _require_reviewed_remuneration(
		daily_remuneration,
		remuneration_reviewed,
		_("Reviewed BCEA Daily Remuneration"),
	)
	return {
		"days": total_days,
		"amount": flt(daily_rate * total_days, 2),
		"balances": balances,
	}


def calculate_severance_tax(severance_amount, date_value=None, previous_lump_sums=0):
	"""Calculate cumulative SARS lump-sum tax through the payroll service."""
	from za_local_payroll.services.tax import calculate_lump_sum_benefit_tax

	return calculate_lump_sum_benefit_tax(
		severance_amount,
		date_value=date_value,
		previous_lump_sums=previous_lump_sums,
	)


def _get_employee(employee):
	if isinstance(employee, str):
		return frappe.get_cached_doc("Employee", employee)
	return employee


def _validate_service_dates(date_of_joining, termination_date) -> tuple[date, date]:
	if not date_of_joining:
		frappe.throw(
			_("Employee Date of Joining is required for BCEA termination calculations."),
			title=_("Employment Date Required"),
		)
	if not termination_date:
		frappe.throw(
			_("Actual Termination Date is required for BCEA termination calculations."),
			title=_("Termination Date Required"),
		)

	joining_date = getdate(date_of_joining)
	actual_termination_date = getdate(termination_date)
	if actual_termination_date < joining_date:
		frappe.throw(
			_("Actual Termination Date cannot be before Date of Joining."),
			title=_("Invalid Employment Dates"),
		)
	return joining_date, actual_termination_date


def _require_reviewed_remuneration(value, reviewed: bool, label: str) -> float:
	amount = flt(value)
	if not cint(reviewed) or amount <= 0:
		frappe.throw(
			_(
				"{0} must be greater than zero and practitioner-reviewed before this "
				"settlement can be calculated. Salary Structure base is not used as a "
				"substitute for BCEA remuneration."
			).format(label),
			title=_("BCEA Remuneration Review Required"),
		)
	return amount
