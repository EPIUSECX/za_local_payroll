"""
South African Payroll Utility Functions

This module provides utility functions for South African payroll processing,
including frequency calculations, payroll period handling, and employee mapping.
"""

from datetime import datetime, timedelta

import frappe
from dateutil.relativedelta import relativedelta

from za_local_payroll.utils.hrms import require_hrms, safe_import_hrms

# Conditionally import HRMS functions
(get_payroll_period,) = safe_import_hrms(
	"hrms.payroll.doctype.payroll_period.payroll_period", "get_payroll_period"
)

(hrms_get_additional_salaries,) = safe_import_hrms(
	"hrms.payroll.doctype.additional_salary.additional_salary",
	"get_additional_salaries",
)

if get_payroll_period is None:

	def get_payroll_period(*args, **kwargs):
		require_hrms("Payroll Period")
		return None


if hrms_get_additional_salaries is None:

	def hrms_get_additional_salaries(*args, **kwargs):
		require_hrms("Additional Salary")
		return []


# Frequency mapping for payroll calculations
FREQUENCY_MONTHS = {"Quarterly": 3, "Half-Yearly": 6, "Yearly": 12}


def get_current_block(frequency, date, payroll_period):
	"""
	Get the current payroll block for a given frequency and date.

	Args:
	    frequency (str): Payroll frequency (Quarterly, Half-Yearly, Yearly)
	    date (date): Date to check
	    payroll_period (Document): Payroll Period document

	Returns:
	    frappe._dict: Dict with start_date and end_date of the block, or None if invalid
	"""
	if frequency not in FREQUENCY_MONTHS:
		return None

	if not payroll_period or not hasattr(payroll_period, "start_date"):
		return None

	start_date = payroll_period.start_date
	end_date = payroll_period.end_date
	months = FREQUENCY_MONTHS[frequency]

	if isinstance(start_date, str):
		start_date = datetime.strptime(str(start_date), "%Y-%m-%d").date()
	if isinstance(end_date, str):
		end_date = datetime.strptime(str(end_date), "%Y-%m-%d").date()
	if isinstance(date, str):
		date = datetime.strptime(str(date), "%Y-%m-%d").date()
	if isinstance(start_date, datetime):
		start_date = start_date.date()
	if isinstance(end_date, datetime):
		end_date = end_date.date()
	if isinstance(date, datetime):
		date = date.date()

	current_start = start_date
	for _iteration in range(20):
		block_end_date = current_start + relativedelta(months=months) - timedelta(days=1)
		if current_start <= date <= block_end_date:
			return frappe._dict({"start_date": current_start, "end_date": block_end_date})
		current_start = block_end_date + timedelta(days=1)
		if current_start > end_date:
			break

	return None


def get_current_block_period(doc):
	"""
	Get current block period for all configured frequencies.

	Args:
	    doc: Document with start_date, end_date, and company (Salary Slip or Payroll Entry)

	Returns:
	    dict: Map of frequency to block period
	"""
	# Handle both Salary Slip and Payroll Entry
	start_date = getattr(doc, "start_date", None)
	end_date = getattr(doc, "end_date", None)
	company = getattr(doc, "company", None)

	if not all([start_date, end_date, company]):
		return {}

	payroll_period = get_payroll_period(start_date, end_date, company)

	if not payroll_period:
		return {}

	payroll_period_doc = frappe.get_doc("Payroll Period", payroll_period)
	frequency_map = {}

	for frequency in FREQUENCY_MONTHS:
		block = get_current_block(frequency, start_date, payroll_period_doc)
		if block:
			frequency_map[frequency] = block

	return frequency_map


def get_employee_frequency_map():
	"""
	Get mapping of employees to their payroll frequencies.

	Returns:
	    dict: Employee ID to frequency mapping
	"""
	emp_map = {}

	frequency_details = frappe.get_all("Employee Frequency Detail", fields=["employee", "frequency"])

	for detail in frequency_details:
		emp_map[detail.employee] = detail.frequency

	return emp_map


def is_payroll_processed(employee, frequency_period, company=None):
	"""
	Check if payroll has already been processed for an employee in a period.

	Args:
	    employee (str): Employee ID
	    frequency_period (frappe._dict): Period with start_date and end_date

	Returns:
	    bool: True if already processed
	"""
	if not frequency_period:
		return False

	filters = {
		"employee": employee,
		"start_date": [">=", frequency_period.start_date],
		"end_date": ["<=", frequency_period.end_date],
		"docstatus": 1,
	}
	if company:
		filters["company"] = company

	return frappe.db.exists(
		"Salary Slip",
		filters,
	)


def get_company_contribution_additional_salaries(employee, from_date, to_date):
	"""Return Additional Salaries whose own Salary Component is a Company Contribution.

	Additional Salary fetches `type` from the linked Salary Component, so a row for a
	Company Contribution component is never returned by HRMS, which only ever selects
	"Earning" or "Deduction". Those rows would otherwise be silently dropped. Date
	eligibility mirrors HRMS: a recurring row spans the period end, a one-off row falls
	on a payroll date inside the period.
	"""
	additional_salary = frappe.qb.DocType("Additional Salary")
	recurring = (
		(additional_salary.is_recurring == 1)
		& (additional_salary.from_date <= to_date)
		& (additional_salary.to_date >= to_date)
	)
	one_off = (additional_salary.is_recurring == 0) & additional_salary.payroll_date[from_date:to_date]

	return (
		frappe.qb.from_(additional_salary)
		.select(
			additional_salary.name,
			additional_salary.salary_component.as_("component"),
			additional_salary.type,
			additional_salary.amount,
			additional_salary.is_recurring,
			additional_salary.overwrite_salary_structure_amount.as_("overwrite"),
			additional_salary.deduct_full_tax_on_selected_payroll_date,
			additional_salary.ref_doctype,
		)
		.where(
			(additional_salary.employee == employee)
			& (additional_salary.docstatus == 1)
			& (additional_salary.disabled == 0)
			& (additional_salary.type == "Company Contribution")
			& (recurring | one_off)
		)
		.run(as_dict=True)
	)


def get_additional_salaries(employee, from_date, to_date, component_type="earnings"):
	"""Return HRMS-selected Additional Salaries for the requested ZA bucket.

	HRMS owns date eligibility, recurring salary handling, disabled records,
	overwrite aliases, and duplicate-overwrite validation. ZA Local only adds
	the company-contribution partition and the reference name needed by the
	Employee Benefit Ledger.

	A company contribution reaches the slip either by flagging
	za_is_company_contribution on an earning or deduction, or by using a Salary
	Component that is itself typed Company Contribution. Both are honoured.
	"""
	component_typed_contributions = []
	if component_type == "company_contributions":
		additional_salaries = hrms_get_additional_salaries(
			employee, from_date, to_date, "earnings"
		) + hrms_get_additional_salaries(employee, from_date, to_date, "deductions")
		component_typed_contributions = get_company_contribution_additional_salaries(
			employee, from_date, to_date
		)
		include_company_contributions = True
	elif component_type in {"earnings", "deductions"}:
		additional_salaries = hrms_get_additional_salaries(employee, from_date, to_date, component_type)
		include_company_contributions = False
	else:
		frappe.throw(frappe._("Unsupported Additional Salary component type: {0}").format(component_type))

	if not additional_salaries and not component_typed_contributions:
		return []

	selected_names = [row.name for row in additional_salaries] + [
		row.name for row in component_typed_contributions
	]
	details_by_name = {
		row.name: row
		for row in frappe.get_all(
			"Additional Salary",
			filters={"name": ["in", selected_names]},
			fields=["name", "za_is_company_contribution", "ref_docname"],
		)
	}

	filtered_salaries = []
	for additional_salary in additional_salaries:
		details = details_by_name.get(additional_salary.name, frappe._dict())
		is_company_contribution = bool(details.get("za_is_company_contribution"))
		if is_company_contribution != include_company_contributions:
			continue

		additional_salary.za_is_company_contribution = is_company_contribution
		additional_salary.ref_docname = details.get("ref_docname")
		filtered_salaries.append(additional_salary)

	for additional_salary in component_typed_contributions:
		details = details_by_name.get(additional_salary.name, frappe._dict())
		additional_salary.za_is_company_contribution = True
		additional_salary.ref_docname = details.get("ref_docname")
		filtered_salaries.append(additional_salary)

	return filtered_salaries


def validate_payroll_frequency(employee, start_date, end_date, frequency):
	"""
	Validate that payroll frequency is correctly configured for employee.

	Args:
	    employee (str): Employee ID
	    start_date (date): Payroll start date
	    end_date (date): Payroll end date
	    frequency (str): Expected frequency

	Returns:
	    bool: True if valid

	Raises:
	    frappe.ValidationError: If frequency is invalid
	"""
	employee_frequency = frappe.db.get_value("Employee Frequency Detail", {"employee": employee}, "frequency")

	if employee_frequency and employee_frequency != frequency:
		frappe.throw(
			f"Employee {employee} is configured for {employee_frequency} payroll, "
			f"but {frequency} is being processed"
		)

	return True


def get_payroll_period_dates(payroll_period_name):
	"""
	Get start and end dates for a payroll period.

	Args:
	    payroll_period_name (str): Payroll Period name

	Returns:
	    tuple: (start_date, end_date)
	"""
	period = frappe.get_doc("Payroll Period", payroll_period_name)
	return period.start_date, period.end_date
