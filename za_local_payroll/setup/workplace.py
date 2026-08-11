"""Setup for the SA Labour and SA COIDA modules of the payroll and HR app.

These modules arrived from the separate ``za_local_workplace`` app. Their setup
lives here rather than in ``install.py`` so each domain keeps its own file, and
because both apps defined ``DEFAULT_PRINT_FORMATS``.
"""

from __future__ import annotations

import frappe
from za_local_core.dashboards import seed_dashboards
from za_local_core.localisation import resolve_south_african_companies

WORKPLACE_MODULES = ("SA Labour", "SA COIDA")

WORKPLACE_FEATURES = (
	(
		"BCEA-LEAVE-AND-TERMINATION",
		"BCEA leave and termination decision support",
		"Labour",
		"Preview",
		"Employment terms, bargaining-council rules, case facts, and practitioner review remain authoritative.",
	),
	(
		"EMPLOYMENT-EQUITY-WORKING-PAPERS",
		"Employment Equity analysis and working papers",
		"Employment Equity",
		"Controlled Manual",
		"The app prepares working papers; Department of Employment and Labour filing and evidence remain manual.",
	),
	(
		"WSP-ATR-WORKING-PAPERS",
		"Workplace Skills Plan and Annual Training Report working papers",
		"Skills Development",
		"Controlled Manual",
		"SETA submission, acceptance, and supporting evidence remain practitioner-controlled.",
	),
	(
		"COIDA-RETURN-WORKING-PAPER",
		"COIDA Return of Earnings working paper",
		"COIDA",
		"Controlled Manual",
		"The company class, gazetted ceiling and rate require approval; eCOID filing and receipt capture remain manual.",
	),
	(
		"COIDA-INJURY-AND-CLAIM",
		"Workplace injury and OID claim workflow",
		"COIDA",
		"Preview",
		"Health-data permissions, statutory forms, submission deadlines, and Compensation Fund acceptance require operational sign-off.",
	),
)

WORKPLACE_PRINT_FORMATS = {
	"COIDA Annual Return": "SA COIDA Annual Return",
	"Business Trip": "SA Business Trip",
	"OID Claim": "SA OID Claim",
	"Workplace Skills Plan": "SA Workplace Skills Plan",
	"Annual Training Report": "SA Annual Training Report",
}


def claim_workplace_module_ownership() -> None:
	"""Assign the extracted standard modules to this app."""
	for module_name in WORKPLACE_MODULES:
		if frappe.db.exists("Module Def", module_name):
			frappe.db.set_value(
				"Module Def",
				module_name,
				"app_name",
				"za_local_payroll",
				update_modified=False,
			)
	for workspace_name in WORKPLACE_MODULES:
		if frappe.db.exists("Workspace", workspace_name):
			frappe.db.set_value(
				"Workspace",
				workspace_name,
				"app",
				"za_local_payroll",
				update_modified=False,
			)
	frappe.clear_cache()


def seed_workplace_readiness(company: str | None = None) -> None:
	"""Advertise capabilities conservatively without overwriting practitioner sign-off."""
	if not frappe.db.exists("DocType", "ZA Feature Readiness"):
		return
	for company_name in resolve_south_african_companies(company):
		for feature_code, feature_name, domain, status, limitation in WORKPLACE_FEATURES:
			key = f"{company_name}|{feature_code}"
			if frappe.db.exists("ZA Feature Readiness", key):
				continue
			frappe.get_doc(
				{
					"doctype": "ZA Feature Readiness",
					"company": company_name,
					"feature_code": feature_code,
					"feature_name": feature_name,
					"domain": domain,
					"status": status,
					"blocking_reason": limitation,
					"remediation_route": "Complete the relevant practitioner sign-off and retain external evidence.",
				}
			).insert(ignore_permissions=True)


def seed_2026_labour_reference_rows() -> None:
	"""Seed review-required NMW references without asserting operational approval."""
	if not frappe.db.exists("DocType", "Sectoral Minimum Wage"):
		return
	rows = (
		{
			"worker_category": "General NMW",
			"sector": "All Sectors",
			"position_category": "Ordinary workers subject to the general NMW",
			"hourly_rate": 30.23,
		},
		{
			"worker_category": "EPWP",
			"sector": "Expanded Public Works Programme",
			"position_category": "EPWP workers",
			"hourly_rate": 16.62,
		},
		{
			"worker_category": "Learnership Schedule 2",
			"sector": "Learnerships",
			"position_category": "Workers on qualifying learnership agreements",
			"schedule_reference": "National Minimum Wage Act Schedule 2 allowances",
		},
	)
	for values in rows:
		filters = {
			"worker_category": values["worker_category"],
			"effective_from": "2026-03-01",
		}
		if frappe.db.exists("Sectoral Minimum Wage", filters):
			continue
		frappe.get_doc(
			{
				"doctype": "Sectoral Minimum Wage",
				**values,
				"effective_from": "2026-03-01",
				"source_reference": "Gazette 54075, Notice 7083",
				"reviewed_by": "Administrator",
				"governance_status": "Draft Reference",
			}
		).insert(ignore_permissions=True)


def ensure_workplace_print_formats() -> None:
	"""Set app-owned formats only when the site has no existing default."""
	for doctype_name, print_format_name in WORKPLACE_PRINT_FORMATS.items():
		if not frappe.db.exists("DocType", doctype_name) or not frappe.db.exists(
			"Print Format", print_format_name
		):
			continue
		if not frappe.db.get_value("DocType", doctype_name, "default_print_format"):
			frappe.db.set_value("DocType", doctype_name, "default_print_format", print_format_name)


COIDA_MODULE = "SA COIDA"
LABOUR_MODULE = "SA Labour"

COIDA_NUMBER_CARDS = (
	{
		"label": "COIDA Assessable Earnings",
		"document_type": "COIDA Annual Return",
		"function": "Sum",
		"aggregate_function_based_on": "total_annual_earnings",
		"filters": [["docstatus", "=", 1]],
	},
	{
		"label": "COIDA Assessment Fee",
		"document_type": "COIDA Annual Return",
		"function": "Sum",
		"aggregate_function_based_on": "assessment_fee",
		"filters": [["docstatus", "=", 1]],
	},
	{
		"label": "Workplace Injuries Open",
		"document_type": "Workplace Injury",
		"function": "Count",
		"filters": [["status", "in", ["Reported", "Investigating", "Treating"]]],
	},
	{
		"label": "OID Claims Awaiting Outcome",
		"document_type": "OID Claim",
		"function": "Count",
		"filters": [["claim_status", "in", ["Pending", "Submitted", "Under Review"]]],
	},
)

COIDA_CHARTS = (
	{
		"chart_name": "SA OID Claims by Status",
		"chart_type": "Group By",
		"document_type": "OID Claim",
		"group_by_type": "Count",
		"group_by_based_on": "claim_status",
		"type": "Donut",
	},
	{
		"chart_name": "SA Workplace Injuries by Severity",
		"chart_type": "Group By",
		"document_type": "Workplace Injury",
		"group_by_type": "Count",
		"group_by_based_on": "severity",
		"type": "Bar",
	},
	{
		"chart_name": "SA COIDA Assessable Earnings by Year",
		"chart_type": "Sum",
		"document_type": "COIDA Annual Return",
		"based_on": "to_date",
		"aggregate_function_based_on": "total_annual_earnings",
		"time_interval": "Yearly",
		"timespan": "Last Year",
		"type": "Bar",
		"filters": [["docstatus", "=", 1]],
	},
)

LABOUR_NUMBER_CARDS = (
	{
		"label": "Workplace Skills Plans Not Approved",
		"document_type": "Workplace Skills Plan",
		"function": "Count",
		"filters": [["status", "=", "Draft Working Paper"]],
	},
	{
		"label": "Training Budget Planned (WSP)",
		"document_type": "Workplace Skills Plan",
		"function": "Sum",
		"aggregate_function_based_on": "total_training_budget",
		"filters": [["docstatus", "=", 1]],
	},
	{
		"label": "Business Trips Awaiting Approval",
		"document_type": "Business Trip",
		"function": "Count",
		"filters": [["docstatus", "=", 0]],
	},
	{
		"label": "Employment Equity Movements Recorded",
		"document_type": "Employment Equity Movement",
		"function": "Count",
		"filters": [["docstatus", "=", 1]],
	},
)

LABOUR_CHARTS = (
	{
		"chart_name": "SA Workplace Skills Plans by Status",
		"chart_type": "Group By",
		"document_type": "Workplace Skills Plan",
		"group_by_type": "Count",
		"group_by_based_on": "status",
		"type": "Donut",
	},
	{
		"chart_name": "SA Business Trip Spend by Month",
		"chart_type": "Sum",
		"document_type": "Business Trip",
		"based_on": "to_date",
		"aggregate_function_based_on": "grand_total",
		"time_interval": "Monthly",
		"timespan": "Last Year",
		"type": "Bar",
		"filters": [["docstatus", "=", 1]],
	},
)


def seed_workplace_dashboards() -> dict:
	"""Create the SA COIDA and SA Labour number cards and charts when missing."""
	coida = seed_dashboards(COIDA_MODULE, cards=COIDA_NUMBER_CARDS, charts=COIDA_CHARTS, workspace="SA COIDA")
	labour = seed_dashboards(
		LABOUR_MODULE, cards=LABOUR_NUMBER_CARDS, charts=LABOUR_CHARTS, workspace="SA Labour"
	)
	return {"coida": coida, "labour": labour}
