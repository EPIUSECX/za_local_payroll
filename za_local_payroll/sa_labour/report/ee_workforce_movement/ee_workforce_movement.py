from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import getdate

from za_local_payroll.sa_labour.report_utils import (
	get_controlled_manual_message,
	get_permitted_company,
	get_small_cell_control,
	suppress_count,
)


def execute(filters=None):
	return get_columns(), get_data(filters), get_controlled_manual_message()


def get_columns():
	return [
		{"label": _("Movement Type"), "fieldname": "movement_type", "fieldtype": "Data", "width": 120},
		{
			"label": _("Previous Level"),
			"fieldname": "previous_occupational_level",
			"fieldtype": "Data",
			"width": 170,
		},
		{"label": _("New Level"), "fieldname": "new_occupational_level", "fieldtype": "Data", "width": 170},
		{"label": _("Race"), "fieldname": "race", "fieldtype": "Data", "width": 100},
		{"label": _("Gender"), "fieldname": "gender", "fieldtype": "Data", "width": 100},
		{"label": _("Disability"), "fieldname": "disability", "fieldtype": "Data", "width": 150},
		{"label": _("Count"), "fieldname": "count", "fieldtype": "Data", "width": 80},
	]


def get_data(filters):
	filters = filters or {}
	company = get_permitted_company(filters)
	from_date = filters.get("from_date")
	to_date = filters.get("to_date")
	if not from_date or not to_date:
		frappe.throw(_("From Date and To Date are required."))
	if getdate(to_date) < getdate(from_date):
		frappe.throw(_("To Date cannot be before From Date."))
	threshold, show_small_cells = get_small_cell_control(filters, company)
	rows = frappe.db.sql(
		"""
			SELECT movement_type, previous_occupational_level, new_occupational_level, race, gender,
				CASE WHEN is_disabled = 1 THEN 'Persons with Disabilities'
					ELSE 'Persons without Disabilities' END AS disability,
				COUNT(*) AS count
			FROM `tabEmployment Equity Movement`
			WHERE company = %(company)s AND docstatus = 1
				AND effective_date BETWEEN %(from_date)s AND %(to_date)s
			GROUP BY movement_type, previous_occupational_level, new_occupational_level, race, gender, is_disabled
			ORDER BY movement_type, previous_occupational_level, new_occupational_level
		""",
		{"company": company, "from_date": from_date, "to_date": to_date},
		as_dict=True,
	)
	for row in rows:
		row.count = suppress_count(row.count, threshold, show_small_cells)
	return rows
