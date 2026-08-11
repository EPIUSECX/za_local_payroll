"""Company setup a pay run needs that this suite must not decide for the customer.

Ledger accounts and the working week are customer policy, not statute. Guessing
them would post real money to accounts nobody chose, or pro-rate pay against a
calendar nobody agreed. So the suite names each gap precisely before a pay run
starts, rather than letting it surface one salary slip at a time at submit.
"""

from __future__ import annotations

import frappe
from frappe import _
from za_local_core.localisation import is_south_african_company

# The engine adds these to every slip, so they need ledgers even when no salary
# structure names them.
ALWAYS_POSTED_COMPONENTS = ("PAYE", "UIF Employee Contribution")


def get_missing_company_payroll_setup(company: str) -> list[str]:
	"""Return the company setup gaps that would break a pay run, in fixing order.

	Companies outside South Africa are not this app's concern and report nothing.
	"""
	if not is_south_african_company(company):
		return []

	return [
		*_unmapped_salary_components(company),
		*_untyped_payroll_payable_account(company),
		*_absent_holiday_calendar(company),
		*_no_employee_type_to_choose(),
	]


def validate_company_payroll_setup(company: str) -> None:
	"""Block a pay run while company setup is incomplete."""
	missing = get_missing_company_payroll_setup(company)
	if not missing:
		return
	frappe.throw(
		_("This company is not ready to run South African payroll:<br>{0}").format(
			"<br>".join(f"• {frappe.utils.escape_html(item)}" for item in missing)
		),
		title=_("Incomplete Company Payroll Setup"),
	)


def _unmapped_salary_components(company: str) -> list[str]:
	"""Components that will post for this company but have no account on it.

	Only components the company actually uses are reported. A component excluded
	from accounts posts nothing and needs no ledger.
	"""
	structures = frappe.get_all(
		"Salary Structure", filters={"company": company, "docstatus": 1, "is_active": "Yes"}, pluck="name"
	)
	used = set(ALWAYS_POSTED_COMPONENTS)
	if structures:
		used.update(
			frappe.get_all(
				"Salary Detail",
				filters={"parent": ["in", structures], "parenttype": "Salary Structure"},
				pluck="salary_component",
			)
		)

	posting = frappe.get_all(
		"Salary Component",
		filters={"name": ["in", list(used)], "do_not_include_in_accounts": 0},
		pluck="name",
	)
	if not posting:
		return []
	mapped = set(
		frappe.get_all(
			"Salary Component Account",
			filters={"parent": ["in", posting], "company": company},
			pluck="parent",
		)
	)
	return [
		_("Salary Component {0} has no account for this company").format(name)
		for name in sorted(set(posting) - mapped)
	]


def _untyped_payroll_payable_account(company: str) -> list[str]:
	"""ERPNext's standard chart ships Payroll Payable without an account type.

	HRMS then refuses the account at Payroll Entry, so the chart has to be
	corrected before a pay run. The suite reports it rather than reclassifying an
	account in someone else's chart.
	"""
	account = frappe.db.get_value("Company", company, "default_payroll_payable_account")
	if not account:
		return [_("Company has no Default Payroll Payable Account")]
	if frappe.db.get_value("Account", account, "account_type") == "Payable":
		return []
	return [
		_("Account {0} must have Account Type set to Payable before it can carry payroll").format(account)
	]


def _no_employee_type_to_choose() -> list[str]:
	"""Payroll requires an Employee Type per employee and the master ships empty.

	Missing it on one employee is that employee's problem and payroll already names
	them. An empty master is setup: nobody can be given a type that does not exist.
	The suite does not create one, because Employee Type carries a mandatory payroll
	payable account and that is the customer's ledger to choose.
	"""
	if frappe.db.count("Employee Type"):
		return []
	return [
		_(
			"No Employee Type exists. Payroll requires one on every employee, so create "
			"the types this employer uses and give each its payroll payable account."
		)
	]


def _absent_holiday_calendar(company: str) -> list[str]:
	"""No holiday calendar reaches this company's employees by any route.

	The payroll engine resolves a calendar through Holiday List Assignment or the
	employee's own list. A Default Holiday List on the Company is deliberately not
	accepted here: the engine does not read it, so treating it as coverage would
	pass this check and then fail the pay run.

	The suite ships the official public holidays but assigns nothing, because a
	five or six day week changes what a day of pay is worth and only the customer
	knows theirs.
	"""
	if frappe.db.exists(
		"Holiday List Assignment",
		{"applicable_for": "Company", "assigned_to": company, "docstatus": ["<", 2]},
	):
		return []

	employees = frappe.get_all(
		"Employee", filters={"company": company, "status": "Active"}, pluck="holiday_list"
	)
	if employees and all(employees):
		return []

	return [
		_(
			"No holiday calendar reaches this company. Assign one of the shipped South "
			"African public holiday lists through Holiday List Assignment, and set the "
			"weekly off days that match this employer's working week."
		)
	]
