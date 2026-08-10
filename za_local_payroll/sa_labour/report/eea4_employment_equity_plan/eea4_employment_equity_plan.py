from __future__ import annotations

from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import flt

from za_local_payroll.sa_labour.report_utils import (
	get_controlled_manual_message,
	get_permitted_company,
	get_reporting_date,
	get_small_cell_control,
	suppress_count,
	validate_employee_fields,
)


def execute(filters=None):
	return get_columns(), get_data(filters), get_controlled_manual_message()


def get_columns():
	return [
		{"label": _("Effective Date"), "fieldname": "effective_date", "fieldtype": "Date", "width": 110},
		{
			"label": _("Occupational Level"),
			"fieldname": "occupational_level",
			"fieldtype": "Data",
			"width": 170,
		},
		{"label": _("Race"), "fieldname": "race", "fieldtype": "Data", "width": 90},
		{"label": _("Gender"), "fieldname": "gender", "fieldtype": "Data", "width": 90},
		{"label": _("Disability"), "fieldname": "disability_status", "fieldtype": "Data", "width": 150},
		{
			"label": _("Current Headcount"),
			"fieldname": "current_headcount",
			"fieldtype": "Data",
			"width": 120,
		},
		{"label": _("Target Headcount"), "fieldname": "target_headcount", "fieldtype": "Int", "width": 110},
		{"label": _("Target %"), "fieldname": "target_percentage", "fieldtype": "Percent", "width": 90},
		{"label": _("Source Basis"), "fieldname": "source_basis", "fieldtype": "Data", "width": 160},
		{"label": _("Source Reference"), "fieldname": "source_reference", "fieldtype": "Data", "width": 220},
	]


def get_data(filters):
	filters = filters or {}
	company = get_permitted_company(filters)
	reporting_date = get_reporting_date(filters)
	target_plan = filters.get("target_plan")
	if not target_plan:
		frappe.throw(_("Employment Equity Target Plan is required."))
	plan = frappe.get_doc("Employment Equity Target Plan", target_plan, check_permission=True)
	if plan.docstatus != 1 or plan.company != company:
		frappe.throw(_("Select a submitted Employment Equity Target Plan for the chosen company."))
	if not (plan.plan_start_date <= reporting_date <= plan.plan_end_date):
		frappe.throw(_("Reporting Date must fall within the selected target plan period."))
	threshold, show_small_cells = get_small_cell_control(filters, company, target_plan)
	validate_employee_fields({"za_is_disabled", "za_occupational_level", "za_race"})

	current = _get_current_cells(company, reporting_date)
	targets = frappe.get_all(
		"Employment Equity Target",
		filters={
			"parent": target_plan,
			"parenttype": "Employment Equity Target Plan",
			"effective_date": ["<=", reporting_date],
		},
		fields=[
			"effective_date",
			"occupational_level",
			"race",
			"gender",
			"disability_status",
			"target_percentage",
			"target_headcount",
		],
		order_by="effective_date desc, idx asc",
	)
	latest_targets = {}
	for target in targets:
		key = (target.occupational_level, target.race, target.gender, target.disability_status)
		latest_targets.setdefault(key, target)

	data = []
	for target in latest_targets.values():
		count = _matching_count(current, target)
		data.append(
			{
				**target,
				"current_headcount": suppress_count(count, threshold, show_small_cells),
				"target_headcount": target.target_headcount,
				"target_percentage": flt(target.target_percentage),
				"source_basis": plan.source_basis,
				"source_reference": plan.source_reference,
			}
		)
	return data


def _get_current_cells(company, reporting_date):
	rows = frappe.db.sql(
		"""
			SELECT za_occupational_level AS occupational_level, za_race AS race, gender,
				CASE WHEN za_is_disabled = 1 THEN 'Persons with Disabilities'
					ELSE 'Persons without Disabilities' END AS disability_status,
				COUNT(*) AS headcount
			FROM `tabEmployee`
			WHERE company = %(company)s
				AND date_of_joining <= %(reporting_date)s
				AND (relieving_date IS NULL OR relieving_date >= %(reporting_date)s)
			GROUP BY za_occupational_level, za_race, gender, za_is_disabled
		""",
		{"company": company, "reporting_date": reporting_date},
		as_dict=True,
	)
	return rows


def _matching_count(current, target):
	return sum(
		row.headcount
		for row in current
		if row.occupational_level == target.occupational_level
		and target.race in {"All", row.race}
		and target.gender in {"All", row.gender}
		and target.disability_status in {"All", row.disability_status}
	)
