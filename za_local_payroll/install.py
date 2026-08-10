"""Idempotent install and migrate entry points for za_local_payroll."""

import frappe
from frappe import _
from za_local_core.dashboards import repair_metric_presentation, seed_dashboards
from za_local_core.navigation import sync_shared_navigation
from za_local_core.practitioner_guide.stage import unpublish_app_guide

from za_local_payroll.patches.v1_0.transfer_payroll_ownership import execute as transfer_ownership
from za_local_payroll.setup.custom_fields import apply_payroll_custom_fields
from za_local_payroll.setup.masters import seed_payroll_masters
from za_local_payroll.setup.property_setters import apply_payroll_property_setters
from za_local_payroll.setup.records import install_payroll_doctype_links
from za_local_payroll.setup.statutory import ensure_all_company_tax_configuration
from za_local_payroll.setup.workplace import (
	COIDA_CHARTS,
	COIDA_MODULE,
	COIDA_NUMBER_CARDS,
	LABOUR_CHARTS,
	LABOUR_MODULE,
	LABOUR_NUMBER_CARDS,
	claim_workplace_module_ownership,
	ensure_workplace_print_formats,
	seed_2026_labour_reference_rows,
	seed_workplace_dashboards,
	seed_workplace_readiness,
)
from za_local_payroll.setup.workplace_custom_fields import ensure_workplace_custom_fields
from za_local_payroll.utils.csv_importer import import_default_master_data

REQUIRED_APPS = {"erpnext", "hrms", "za_local_core"}

PAYROLL_FEATURES = (
	(
		"PAYROLL-CALCULATION",
		"PAYE, UIF, SDL and ETI payroll calculation",
		"Payroll",
		"Preview",
		"An approved, date-effective statutory pack and parallel-run sign-off are required before live pay runs.",
	),
	(
		"EMP201-WORKING-PAPER",
		"EMP201 declaration working paper",
		"Payroll",
		"Controlled Manual",
		"The app prepares and reconciles the declaration; SARS eFiling submission and receipt evidence remain manual.",
	),
	(
		"IRP5-EMP501-WORKING-PAPERS",
		"IRP5/IT3(a) certificates and EMP501 reconciliation",
		"Payroll",
		"Controlled Manual",
		"Electronic SARS filing-format certification and portal submission are not automated.",
	),
	(
		"PAYROLL-BANK-OUTPUT",
		"Payroll bank and EFT preparation",
		"Payroll",
		"Controlled Manual",
		"Each bank layout, approval chain and payment control total requires bank-specific acceptance testing.",
	),
	(
		"FRINGE-BENEFITS",
		"South African fringe-benefit calculation support",
		"Payroll",
		"Preview",
		"Benefit classification, valuation inputs, tax directives and certificate coding require practitioner review.",
	),
)

DEFAULT_PRINT_FORMATS = {
	"Salary Slip": "SA Salary Slip",
	"IRP5 Certificate": "IRP5 Employee Certificate",
	"EMP201 Submission": "SA EMP201 Submission",
	"EMP501 Reconciliation": "SA EMP501 Reconciliation",
}


def before_install() -> None:
	"""Reject partial installations before any payroll schema is applied."""
	missing = sorted(REQUIRED_APPS.difference(frappe.get_installed_apps() or ()))
	if missing:
		frappe.throw(
			_("Install the following apps before SA Localisation Payroll: {0}").format(", ".join(missing)),
			title=_("Payroll Dependencies Missing"),
		)


def after_install() -> None:
	"""Install schema support and conservative initial payroll masters."""
	_sync_schema_support()
	seed_payroll_masters()
	ensure_all_company_tax_configuration()
	seed_payroll_readiness()
	ensure_default_print_formats()
	seed_payroll_dashboards()
	_setup_workplace_modules()
	sync_shared_navigation()


def after_migrate() -> None:
	"""Keep schema ownership current without rewriting statutory master data."""
	_sync_schema_support()
	seed_payroll_masters()
	ensure_all_company_tax_configuration()
	seed_payroll_readiness()
	ensure_default_print_formats()
	seed_payroll_dashboards()
	repair_payroll_metrics()
	_setup_workplace_modules()
	sync_shared_navigation()


def repair_payroll_metrics(user_input: dict | None = None) -> dict:
	"""Restamp metric presentation from the currency in force now.

	Number Card and Dashboard Chart persist a currency on the record. Nothing
	corrected a wrong one on a fresh install: ``install_app`` marks every patch
	complete before it runs ``after_install``, so the repair patch could never
	execute, and ``seed_dashboards`` skips records that already exist. Whatever
	currency was resolvable during install was therefore permanent, and Frappe
	ships INR, so South African statutory figures rendered in rupees forever.

	Called from ``after_migrate`` and from ``setup_wizard_complete``, which is the
	first moment the real company currency is known. ``user_input`` is the setup
	wizard payload and is unused.
	"""
	return {
		PAYROLL_MODULE: repair_metric_presentation(
			PAYROLL_MODULE, cards=PAYROLL_NUMBER_CARDS, charts=PAYROLL_CHARTS
		),
		COIDA_MODULE: repair_metric_presentation(
			COIDA_MODULE, cards=COIDA_NUMBER_CARDS, charts=COIDA_CHARTS
		),
		LABOUR_MODULE: repair_metric_presentation(
			LABOUR_MODULE, cards=LABOUR_NUMBER_CARDS, charts=LABOUR_CHARTS
		),
	}


def before_uninstall() -> None:
	"""Withdraw this app's contribution to the on-site guides.

	Frappe reclaims records by module and neither Wiki DocType has one, so the
	pages this app published stay live and reachable unless they are removed here.
	Business and audit records are deliberately retained.
	"""
	unpublish_app_guide("za_local_payroll")


def _sync_schema_support() -> None:
	apply_payroll_custom_fields()
	apply_payroll_property_setters()
	install_payroll_doctype_links()
	transfer_ownership()


def _setup_workplace_modules() -> None:
	"""Set up the SA Labour and SA COIDA modules this app absorbed."""
	claim_workplace_module_ownership()
	ensure_workplace_custom_fields()
	import_default_master_data()
	seed_2026_labour_reference_rows()
	seed_workplace_readiness()
	ensure_workplace_print_formats()
	seed_workplace_dashboards()


def seed_payroll_readiness() -> None:
	"""Advertise payroll capabilities conservatively without changing sign-off."""
	if not frappe.db.exists("DocType", "ZA Feature Readiness"):
		return
	companies = frappe.get_all("Company", filters={"country": "South Africa"}, pluck="name")
	for company in companies:
		for feature_code, feature_name, domain, status, limitation in PAYROLL_FEATURES:
			key = f"{company}|{feature_code}"
			if frappe.db.exists("ZA Feature Readiness", key):
				continue
			frappe.get_doc(
				{
					"doctype": "ZA Feature Readiness",
					"company": company,
					"feature_code": feature_code,
					"feature_name": feature_name,
					"domain": domain,
					"status": status,
					"blocking_reason": limitation,
					"remediation_route": "Complete payroll parallel-run and practitioner sign-off evidence.",
				}
			).insert(ignore_permissions=True)


def ensure_default_print_formats() -> None:
	"""Set app-owned formats only when the customer has no existing default."""
	for doctype_name, print_format_name in DEFAULT_PRINT_FORMATS.items():
		if not frappe.db.exists("DocType", doctype_name) or not frappe.db.exists(
			"Print Format", print_format_name
		):
			continue
		if not frappe.db.get_value("DocType", doctype_name, "default_print_format"):
			frappe.db.set_value("DocType", doctype_name, "default_print_format", print_format_name)


PAYROLL_MODULE = "SA Payroll"

PAYROLL_NUMBER_CARDS = (
	{
		"label": "PAYE Payable (EMP201)",
		"document_type": "EMP201 Submission",
		"function": "Sum",
		"aggregate_function_based_on": "net_paye_payable",
		"filters": [["docstatus", "=", 1]],
	},
	{
		"label": "UIF Payable (EMP201)",
		"document_type": "EMP201 Submission",
		"function": "Sum",
		"aggregate_function_based_on": "uif_payable",
		"filters": [["docstatus", "=", 1]],
	},
	{
		"label": "SDL Payable (EMP201)",
		"document_type": "EMP201 Submission",
		"function": "Sum",
		"aggregate_function_based_on": "sdl_payable",
		"filters": [["docstatus", "=", 1]],
	},
	{
		"label": "ETI Utilised (EMP201)",
		"document_type": "EMP201 Submission",
		"function": "Sum",
		"aggregate_function_based_on": "eti_utilized_current_month",
		"filters": [["docstatus", "=", 1]],
	},
	{
		"label": "ETI Carried Forward (EMP201)",
		"document_type": "EMP201 Submission",
		"function": "Sum",
		"aggregate_function_based_on": "eti_to_be_carried_forward",
		"filters": [["docstatus", "=", 1]],
	},
	{
		"label": "Salary Slips in Draft",
		"document_type": "Salary Slip",
		"function": "Count",
		"filters": [["docstatus", "=", 0]],
	},
	{
		"label": "IRP5 Certificates Not Submitted",
		"document_type": "IRP5 Certificate",
		"function": "Count",
		"filters": [["docstatus", "=", 0]],
	},
	{
		"label": "Payroll Payment Batches Awaiting Release",
		"document_type": "Payroll Payment Batch",
		"function": "Count",
		"filters": [["docstatus", "=", 0]],
	},
)

PAYROLL_CHARTS = (
	{
		"chart_name": "SA PAYE Payable by Month",
		"chart_type": "Sum",
		"document_type": "EMP201 Submission",
		"based_on": "submission_period_end_date",
		"aggregate_function_based_on": "net_paye_payable",
		"time_interval": "Monthly",
		"timespan": "Last Year",
		"type": "Bar",
		"filters": [["docstatus", "=", 1]],
	},
	{
		"chart_name": "SA ETI Utilised by Month",
		"chart_type": "Sum",
		"document_type": "EMP201 Submission",
		"based_on": "submission_period_end_date",
		"aggregate_function_based_on": "eti_utilized_current_month",
		"time_interval": "Monthly",
		"timespan": "Last Year",
		"type": "Line",
		"filters": [["docstatus", "=", 1]],
	},
	{
		"chart_name": "SA Net Pay by Month",
		"chart_type": "Sum",
		"document_type": "Salary Slip",
		"based_on": "end_date",
		"aggregate_function_based_on": "net_pay",
		"time_interval": "Monthly",
		"timespan": "Last Year",
		"type": "Bar",
		"filters": [["docstatus", "=", 1]],
	},
	{
		"chart_name": "SA IRP5 Certificates by Status",
		"chart_type": "Group By",
		"document_type": "IRP5 Certificate",
		"group_by_type": "Count",
		"group_by_based_on": "status",
		"type": "Donut",
	},
)


def seed_payroll_dashboards() -> dict:
	"""Create the SA Payroll number cards and charts when missing."""
	return seed_dashboards(
		PAYROLL_MODULE, cards=PAYROLL_NUMBER_CARDS, charts=PAYROLL_CHARTS, workspace="SA Payroll"
	)
