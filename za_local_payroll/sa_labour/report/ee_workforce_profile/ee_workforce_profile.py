from __future__ import annotations

import frappe
from frappe import _

from za_local_payroll.sa_labour.report_utils import (
	CONTROLLED_MANUAL_MESSAGE,
	get_permitted_company,
	get_reporting_date,
	get_small_cell_control,
	suppress_count,
	validate_employee_fields,
)


def execute(filters=None):
	return get_columns(), get_data(filters), CONTROLLED_MANUAL_MESSAGE


def get_columns():
	return [
		{
			"label": _("Occupational Level"),
			"fieldname": "occupational_level",
			"fieldtype": "Data",
			"width": 180,
		},
		{"label": _("Gender"), "fieldname": "gender", "fieldtype": "Data", "width": 100},
		{"label": _("Disability"), "fieldname": "disability", "fieldtype": "Data", "width": 130},
		{"label": _("African"), "fieldname": "african", "fieldtype": "Data", "width": 90},
		{"label": _("Coloured"), "fieldname": "coloured", "fieldtype": "Data", "width": 90},
		{"label": _("Indian"), "fieldname": "indian", "fieldtype": "Data", "width": 90},
		{"label": _("White"), "fieldname": "white", "fieldtype": "Data", "width": 90},
		{"label": _("Other"), "fieldname": "other", "fieldtype": "Data", "width": 90},
		{"label": _("Total"), "fieldname": "total", "fieldtype": "Data", "width": 80},
	]


def get_data(filters):
	company = get_permitted_company(filters)
	reporting_date = get_reporting_date(filters)
	threshold, show_small_cells = get_small_cell_control(filters, company)
	validate_employee_fields({"za_is_disabled", "za_occupational_level", "za_race"})
	rows = frappe.db.sql(
		"""
			SELECT
				COALESCE(za_occupational_level, 'Not Classified') AS occupational_level,
				COALESCE(gender, 'Not Classified') AS gender,
				CASE WHEN za_is_disabled = 1 THEN 'Persons with Disabilities'
					ELSE 'Persons without Disabilities' END AS disability,
				SUM(CASE WHEN za_race = 'African' THEN 1 ELSE 0 END) AS african,
				SUM(CASE WHEN za_race = 'Coloured' THEN 1 ELSE 0 END) AS coloured,
				SUM(CASE WHEN za_race = 'Indian' THEN 1 ELSE 0 END) AS indian,
				SUM(CASE WHEN za_race = 'White' THEN 1 ELSE 0 END) AS white,
				SUM(CASE WHEN za_race = 'Other' OR IFNULL(za_race, '') = '' THEN 1 ELSE 0 END) AS other,
				COUNT(*) AS total
			FROM `tabEmployee`
			WHERE company = %(company)s
				AND date_of_joining <= %(reporting_date)s
				AND (relieving_date IS NULL OR relieving_date >= %(reporting_date)s)
			GROUP BY za_occupational_level, gender, za_is_disabled
			ORDER BY za_occupational_level, gender, za_is_disabled
		""",
		{"company": company, "reporting_date": reporting_date},
		as_dict=True,
	)
	for row in rows:
		for fieldname in ("african", "coloured", "indian", "white", "other", "total"):
			row[fieldname] = suppress_count(row[fieldname], threshold, show_small_cells)
	return rows
