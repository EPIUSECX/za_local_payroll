"""EMP201 Reconciliation: payroll totals against the EMP201 Submission for the same months.

Payroll amounts come from ``Statutory Submissions Summary``, which classifies Salary Slip
deductions and Company Contributions by SARS payroll code, so this report cannot drift from it.
The EMP201 side is read from submissions whose period starts inside the filter dates, which lets a
payroll officer check employee UIF, employer UIF, SDL and PAYE before filing.
"""

import frappe
from frappe import _
from frappe.utils import escape_html, flt

from za_local_payroll.sa_payroll.report.statutory_submissions_summary.statutory_submissions_summary import (
	get_data as get_payroll_totals,
)

TOLERANCE = 0.01

PAYE = "PAYE"
EMPLOYEE_UIF = "UIF Employee Contribution"
EMPLOYER_UIF = "UIF Employer Contribution"
SDL = "SDL Contribution"


def execute(filters=None):
	filters = _validate_filters(filters)
	submissions = get_submissions(filters)
	data = get_data(get_payroll_amounts(filters), submissions)
	return get_columns(), data, _message(submissions)


def _validate_filters(filters):
	filters = frappe._dict(filters or {})
	if not filters.company or not filters.from_date or not filters.to_date:
		frappe.throw(_("Company, From Date, and To Date are required."))
	frappe.has_permission("Company", "read", doc=filters.company, throw=True)
	return filters


def get_columns():
	return [
		{"label": _("Item"), "fieldname": "item", "fieldtype": "Data", "width": 280},
		{"label": _("Payroll"), "fieldname": "payroll_amount", "fieldtype": "Currency", "width": 140},
		{"label": _("EMP201"), "fieldname": "emp201_amount", "fieldtype": "Currency", "width": 140},
		{"label": _("Difference"), "fieldname": "difference", "fieldtype": "Currency", "width": 140},
		{"label": _("Check"), "fieldname": "check", "fieldtype": "Data", "width": 120},
	]


def get_payroll_amounts(filters):
	"""Payroll totals for the period, keyed by the summary's component names."""
	return {row.component: flt(row.amount) for row in get_payroll_totals(filters)}


def get_submissions(filters):
	"""Draft and submitted EMP201s that start inside the period, honouring the user's permissions."""
	return frappe.get_list(
		"EMP201 Submission",
		filters={
			"company": filters.company,
			"docstatus": ["<", 2],
			"submission_period_start_date": ["between", [filters.from_date, filters.to_date]],
		},
		fields=[
			"name",
			"docstatus",
			"gross_paye_before_eti",
			"uif_payable",
			"sdl_payable",
			"submission_period_start_date",
		],
		order_by="submission_period_start_date",
	)


def get_data(payroll, submissions):
	"""One row per EMP201 box. UIF is filed as one figure, so only its total is compared."""
	employee_uif = payroll.get(EMPLOYEE_UIF, 0)
	employer_uif = payroll.get(EMPLOYER_UIF, 0)
	has_submission = bool(submissions)

	def filed(fieldname):
		return sum(flt(row.get(fieldname)) for row in submissions) if has_submission else None

	return [
		_row(_("PAYE before ETI"), payroll.get(PAYE, 0), filed("gross_paye_before_eti")),
		_row(_("UIF: employee deductions"), employee_uif, None, compare=False),
		_row(_("UIF: employer contributions"), employer_uif, None, compare=False),
		_row(_("UIF payable (employee + employer)"), employee_uif + employer_uif, filed("uif_payable")),
		_row(_("SDL"), payroll.get(SDL, 0), filed("sdl_payable")),
	]


def _row(item, payroll_amount, emp201_amount, compare=True):
	row = {"item": item, "payroll_amount": flt(payroll_amount, 2)}
	if not compare:
		return row
	if emp201_amount is None:
		row["check"] = _("No EMP201")
		return row
	row["emp201_amount"] = flt(emp201_amount, 2)
	row["difference"] = flt(payroll_amount - emp201_amount, 2)
	row["check"] = _("Agrees") if abs(row["difference"]) <= TOLERANCE else _("Differs")
	return row


def _message(submissions):
	if not submissions:
		return _(
			"No EMP201 Submission starts in this period. The payroll amounts are what it should contain."
		)
	listed = ", ".join(
		"{0} ({1})".format(escape_html(row.name), _("Submitted") if row.docstatus == 1 else _("Draft"))
		for row in submissions
	)
	return _("Compared with: {0}. Dates should cover whole EMP201 months.").format(listed)
