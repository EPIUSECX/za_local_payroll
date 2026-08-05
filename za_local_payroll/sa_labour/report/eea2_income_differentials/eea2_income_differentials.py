from __future__ import annotations

import frappe
from frappe import _

from za_local_payroll.sa_labour.report_utils import (
	CONTROLLED_MANUAL_MESSAGE,
	get_permitted_company,
	get_reporting_date,
	get_small_cell_control,
	is_small_cell,
	suppress_count,
	validate_employee_fields,
)

REMUNERATION_BASIS = "Current submitted Salary Structure Assignment base (monthly working-paper proxy)"


def execute(filters=None):
	return get_columns(), get_data(filters), CONTROLLED_MANUAL_MESSAGE


def get_columns():
	return [
		{
			"label": _("Occupational Level"),
			"fieldname": "occupational_level",
			"fieldtype": "Data",
			"width": 170,
		},
		{"label": _("Race"), "fieldname": "race", "fieldtype": "Data", "width": 100},
		{"label": _("Gender"), "fieldname": "gender", "fieldtype": "Data", "width": 100},
		{"label": _("Count"), "fieldname": "count", "fieldtype": "Data", "width": 80},
		{
			"label": _("Total Monthly Base"),
			"fieldname": "total_remuneration",
			"fieldtype": "Currency",
			"width": 150,
		},
		{
			"label": _("Average Monthly Base"),
			"fieldname": "avg_remuneration",
			"fieldtype": "Currency",
			"width": 160,
		},
		{
			"label": _("Remuneration Basis"),
			"fieldname": "remuneration_basis",
			"fieldtype": "Data",
			"width": 360,
		},
	]


def get_data(filters):
	company = get_permitted_company(filters)
	reporting_date = get_reporting_date(filters)
	threshold, show_small_cells = get_small_cell_control(filters, company)
	validate_employee_fields({"za_occupational_level", "za_race"})
	rows = frappe.db.sql(
		"""
			SELECT
				e.za_occupational_level AS occupational_level,
				e.za_race AS race,
				e.gender,
				COUNT(e.name) AS count,
				SUM(IFNULL(ssa.base, 0)) AS total_remuneration,
				AVG(IFNULL(ssa.base, 0)) AS avg_remuneration
			FROM `tabEmployee` e
			LEFT JOIN `tabSalary Structure Assignment` ssa
				ON ssa.name = (
					SELECT latest.name
					FROM `tabSalary Structure Assignment` latest
					WHERE latest.employee = e.name
						AND latest.company = e.company
						AND latest.docstatus = 1
						AND latest.from_date <= %(reporting_date)s
					ORDER BY latest.from_date DESC, latest.creation DESC
					LIMIT 1
				)
			WHERE e.company = %(company)s
				AND e.date_of_joining <= %(reporting_date)s
				AND (e.relieving_date IS NULL OR e.relieving_date >= %(reporting_date)s)
				AND e.za_occupational_level IS NOT NULL
				AND e.za_race IS NOT NULL
			GROUP BY e.za_occupational_level, e.za_race, e.gender
			ORDER BY e.za_occupational_level, e.za_race, e.gender
		""",
		{"company": company, "reporting_date": reporting_date},
		as_dict=True,
	)
	for row in rows:
		if is_small_cell(row.count, threshold, show_small_cells):
			row.total_remuneration = None
			row.avg_remuneration = None
		row.count = suppress_count(row.count, threshold, show_small_cells)
		row.remuneration_basis = REMUNERATION_BASIS
	return rows
