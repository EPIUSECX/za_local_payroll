"""Custom fields the SA Labour and SA COIDA modules add to standard HR DocTypes.

Kept beside setup/custom_fields.py rather than merged into it: that module already
carries the payroll field set and both apps named this file the same thing.
"""

from __future__ import annotations

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

WORKPLACE_CUSTOM_FIELDS = {
	"Employee": [
		{
			"fieldname": "za_working_hours_per_week",
			"label": "Working Hours Per Week",
			"fieldtype": "Float",
			"insert_after": "holiday_list",
			"module": "SA Labour",
			"description": "Standard working hours per week for workplace-rule calculations.",
		},
		{
			"fieldname": "za_has_children",
			"label": "Has Children",
			"fieldtype": "Check",
			"insert_after": "za_working_hours_per_week",
			"module": "SA Labour",
			"description": "Supports family-responsibility leave eligibility review.",
		},
		{
			"fieldname": "za_highest_qualification",
			"label": "Highest Qualification",
			"fieldtype": "Select",
			"options": "\nMatric\nNational Certificate\nNational Diploma\nBachelor's Degree\nHonours Degree\nMaster's Degree\nDoctorate\nOther",
			"insert_after": "za_has_children",
			"module": "SA Labour",
		},
		{
			"fieldname": "za_employment_equity_section",
			"label": "Employment Equity",
			"fieldtype": "Section Break",
			"insert_after": "za_highest_qualification",
			"module": "SA Labour",
			"collapsible": 1,
		},
		{
			"fieldname": "za_race",
			"label": "Race",
			"fieldtype": "Select",
			"options": "\nAfrican\nColoured\nIndian\nWhite\nOther",
			"insert_after": "za_employment_equity_section",
			"module": "SA Labour",
			"description": "Race classification for Employment Equity reporting.",
		},
		{
			"fieldname": "za_occupational_level",
			"label": "Occupational Level",
			"fieldtype": "Select",
			"options": "\nTop Management\nSenior Management\nProfessionally Qualified\nSkilled Technical\nSemi-Skilled\nUnskilled\nTemporary Employees\nNon-Permanent",
			"insert_after": "za_race",
			"module": "SA Labour",
		},
		{
			"fieldname": "za_ee_column_break",
			"fieldtype": "Column Break",
			"insert_after": "za_occupational_level",
			"module": "SA Labour",
		},
		{
			"fieldname": "za_is_disabled",
			"label": "Is Disabled",
			"fieldtype": "Check",
			"insert_after": "za_ee_column_break",
			"module": "SA Labour",
			"description": "Person with disability classification for Employment Equity reporting.",
		},
		{
			"fieldname": "za_coida_director",
			"label": "COIDA Director Classification",
			"fieldtype": "Check",
			"insert_after": "za_is_disabled",
			"module": "SA COIDA",
			"description": (
				"Explicit governed classification used for the director earnings subtotal on the "
				"COIDA Return of Earnings; designation names are not inferred."
			),
		},
	],
	"Company": [
		{
			"fieldname": "za_coida_registration_number",
			"label": "COIDA Registration Number",
			"fieldtype": "Data",
			"insert_after": "tax_id",
			"module": "SA COIDA",
		},
		{
			"fieldname": "za_seta",
			"label": "SETA",
			"fieldtype": "Link",
			"options": "SETA",
			"insert_after": "za_coida_registration_number",
			"module": "SA Labour",
		},
		{
			"fieldname": "za_bargaining_council",
			"label": "Bargaining Council",
			"fieldtype": "Link",
			"options": "Bargaining Council",
			"insert_after": "za_seta",
			"module": "SA Labour",
		},
		{
			"fieldname": "za_sectoral_determination",
			"label": "Sectoral Determination",
			"fieldtype": "Select",
			"options": "\nDomestic Workers\nFarm Workers\nPrivate Security\nHospitality\nWholesale/Retail\nOther",
			"insert_after": "za_bargaining_council",
			"module": "SA Labour",
		},
		{
			"fieldname": "za_ee_controls_section",
			"label": "Employment Equity Controls",
			"fieldtype": "Section Break",
			"insert_after": "za_sectoral_determination",
			"collapsible": 1,
			"module": "SA Labour",
		},
		{
			"fieldname": "za_ee_designated_employer",
			"label": "Designated Employer for EE",
			"fieldtype": "Check",
			"insert_after": "za_ee_controls_section",
			"module": "SA Labour",
		},
		{
			"fieldname": "za_ee_sector",
			"label": "Employment Equity Sector",
			"fieldtype": "Data",
			"insert_after": "za_ee_designated_employer",
			"module": "SA Labour",
			"description": "Reviewed sector classification used to select applicable sector numerical targets.",
		},
		{
			"fieldname": "za_ee_default_target_plan",
			"label": "Default Employment Equity Target Plan",
			"fieldtype": "Link",
			"options": "Employment Equity Target Plan",
			"insert_after": "za_ee_sector",
			"module": "SA Labour",
		},
		{
			"fieldname": "za_ee_small_cell_threshold",
			"label": "EE Small-cell Suppression Threshold",
			"fieldtype": "Int",
			"default": "5",
			"insert_after": "za_ee_default_target_plan",
			"module": "SA Labour",
			"description": "Positive Employment Equity counts below this value are suppressed by default.",
		},
	],
	"Expense Claim": [
		{
			"fieldname": "business_trip",
			"label": "Business Trip",
			"fieldtype": "Link",
			"options": "Business Trip",
			"insert_after": "company",
			"read_only": 1,
			"module": "SA Labour",
		},
	],
	"Leave Type": [
		{
			"fieldname": "za_bcea_section",
			"label": "South African BCEA",
			"fieldtype": "Section Break",
			"insert_after": "rounding",
			"collapsible": 1,
			"module": "SA Labour",
		},
		{
			"fieldname": "za_bcea_compliant",
			"label": "Apply BCEA Validation",
			"fieldtype": "Check",
			"insert_after": "za_bcea_section",
			"default": "0",
			"module": "SA Labour",
		},
		{
			"fieldname": "za_bcea_leave_category",
			"label": "BCEA Leave Category",
			"fieldtype": "Select",
			"options": (
				"\nAnnual Leave\nSick Leave\nFamily Responsibility Leave\nMaternity Leave"
				"\nParental Leave\nAdoption Leave\nCommissioning Parental Leave"
				"\nOccupational Injury Leave\nOther Statutory Leave"
			),
			"insert_after": "za_bcea_compliant",
			"module": "SA Labour",
			"description": "Governed category used by BCEA validation; the Leave Type name is not inferred.",
		},
		{
			"fieldname": "za_medical_certificate_required_after",
			"label": "Medical Certificate Required After (Days)",
			"fieldtype": "Int",
			"insert_after": "za_bcea_compliant",
			"default": "2",
			"module": "SA Labour",
		},
		{
			"fieldname": "za_applicable_gender",
			"label": "Applicable Gender",
			"fieldtype": "Link",
			"options": "Gender",
			"insert_after": "za_medical_certificate_required_after",
			"module": "SA Labour",
		},
	],
	"Leave Application": [
		{
			"fieldname": "za_medical_certificate",
			"label": "Medical Certificate Evidence",
			"fieldtype": "Attach",
			"insert_after": "description",
			"module": "SA Labour",
			"description": "Medical evidence retained for governed sick-leave controls.",
		},
	],
	"Employee Separation": [
		{
			"fieldname": "za_bcea_settlement_section",
			"label": "South African Final Settlement",
			"fieldtype": "Section Break",
			"insert_after": "amended_from",
			"collapsible": 1,
			"module": "SA Labour",
		},
		{
			"fieldname": "za_termination_type",
			"label": "Termination Type",
			"fieldtype": "Select",
			"options": "\nResignation\nDismissal - Misconduct\nDismissal - Incapacity\nDismissal - Operational\nRetirement\nDeath\nMutual Separation\nContract Expiry\nOther",
			"insert_after": "za_bcea_settlement_section",
			"module": "SA Labour",
		},
		{
			"fieldname": "za_termination_date",
			"label": "Actual Termination Date",
			"fieldtype": "Date",
			"insert_after": "za_termination_type",
			"fetch_from": "employee.relieving_date",
			"fetch_if_empty": 1,
			"module": "SA Labour",
			"description": "Actual last date of employment; resignation-letter date is not used.",
		},
		{
			"fieldname": "za_notice_period_days",
			"label": "BCEA Notice Period (Days)",
			"fieldtype": "Int",
			"insert_after": "za_termination_date",
			"read_only": 1,
			"module": "SA Labour",
		},
		{
			"fieldname": "za_completed_service_years",
			"label": "Completed Service Years",
			"fieldtype": "Int",
			"insert_after": "za_notice_period_days",
			"read_only": 1,
			"module": "SA Labour",
		},
		{
			"fieldname": "za_bcea_weekly_remuneration",
			"label": "Reviewed BCEA Weekly Remuneration",
			"fieldtype": "Currency",
			"insert_after": "za_completed_service_years",
			"module": "SA Labour",
			"description": "Practitioner-determined weekly remuneration snapshot for severance.",
		},
		{
			"fieldname": "za_bcea_daily_remuneration",
			"label": "Reviewed BCEA Daily Remuneration",
			"fieldtype": "Currency",
			"insert_after": "za_bcea_weekly_remuneration",
			"module": "SA Labour",
			"description": "Practitioner-determined daily remuneration snapshot for leave settlement.",
		},
		{
			"fieldname": "za_bcea_remuneration_basis",
			"label": "BCEA Remuneration Basis",
			"fieldtype": "Small Text",
			"insert_after": "za_bcea_daily_remuneration",
			"module": "SA Labour",
			"description": "Record the source, period, inclusions, exclusions, and review basis.",
		},
		{
			"fieldname": "za_bcea_remuneration_reviewed",
			"label": "BCEA Remuneration Reviewed",
			"fieldtype": "Check",
			"insert_after": "za_bcea_remuneration_basis",
			"module": "SA Labour",
		},
		{
			"fieldname": "za_bcea_remuneration_reviewed_by",
			"label": "BCEA Remuneration Reviewed By",
			"fieldtype": "Link",
			"options": "User",
			"insert_after": "za_bcea_remuneration_reviewed",
			"read_only": 1,
			"module": "SA Labour",
		},
		{
			"fieldname": "za_bcea_remuneration_reviewed_on",
			"label": "BCEA Remuneration Reviewed On",
			"fieldtype": "Datetime",
			"insert_after": "za_bcea_remuneration_reviewed_by",
			"read_only": 1,
			"module": "SA Labour",
		},
		{
			"fieldname": "za_severance_pay",
			"label": "Calculated Severance Pay",
			"fieldtype": "Currency",
			"insert_after": "za_bcea_remuneration_reviewed_on",
			"read_only": 1,
			"module": "SA Labour",
		},
		{
			"fieldname": "za_leave_payout_days",
			"label": "Annual Leave Payout Days",
			"fieldtype": "Float",
			"insert_after": "za_severance_pay",
			"read_only": 1,
			"module": "SA Labour",
		},
		{
			"fieldname": "za_leave_payout",
			"label": "Calculated Leave Payout",
			"fieldtype": "Currency",
			"insert_after": "za_leave_payout_days",
			"read_only": 1,
			"module": "SA Labour",
		},
	],
}


def ensure_workplace_custom_fields() -> None:
	"""Create missing workplace fields without overwriting site customisation."""
	available = {
		doctype: fields
		for doctype, fields in WORKPLACE_CUSTOM_FIELDS.items()
		if frappe.db.exists("DocType", doctype)
	}
	create_custom_fields(available, update=False)
	for doctype, fields in available.items():
		for field in fields:
			frappe.db.set_value(
				"Custom Field",
				{"dt": doctype, "fieldname": field["fieldname"]},
				"module",
				field["module"],
				update_modified=False,
			)
		frappe.clear_cache(doctype=doctype)
