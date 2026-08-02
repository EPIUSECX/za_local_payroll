"""Conservative setup of South African payroll masters."""

import frappe
from frappe import _
from za_local_core.files import read_packaged_json

from za_local_payroll.setup.default_data import (
	DEFAULT_IRP5_EXCLUDED_SALARY_COMPONENTS,
	DEFAULT_SALARY_COMPONENT_SARS_CODES,
	DEFAULT_SALARY_COMPONENT_TREATMENTS,
	DEFAULT_SARS_PAYROLL_CODES,
)

DEFAULT_SALARY_COMPONENT_ACCOUNT_NAMES = {
	"Basic": "Salaries and Wages",
	"Basic Salary": "Salaries and Wages",
	"Arrear": "Salaries and Wages",
	"Leave Encashment": "Salaries and Wages",
	"PAYE": "PAYE Payable - SARS",
	"Income Tax": "PAYE Payable - SARS",
	"UIF": "UIF Employee Contribution",
	"UIF Employee Contribution": "UIF Employee Contribution",
	"UIF Employer Contribution": "UIF Employer Expense",
	"SDL": "SDL Expense",
	"SDL Contribution": "SDL Expense",
	"COIDA": "COIDA Expense",
	"COIDA Contribution": "COIDA Expense",
}
GOVERNED_COMPONENT_CLASSIFICATIONS = {
	"PAYE",
	"UIF Employee Contribution",
	"UIF Employer Contribution",
	"SDL Contribution",
	"Company Car Benefit",
	"Company Car PAYE Adjustment",
	"Housing Fringe Benefit",
	"Low Interest Loan Fringe Benefit",
	"Other Fringe Benefit",
}
GOVERNED_COMPONENT_FIELDS = {
	"salary_component_abbr",
	"type",
	"is_tax_applicable",
	"is_income_tax_component",
	"variable_based_on_taxable_salary",
	"is_flexible_benefit",
	"depends_on_payment_days",
	"do_not_include_in_total",
	"do_not_include_in_accounts",
	"remove_if_zero_valued",
	"formula",
	"amount_based_on_formula",
}

TERMINATION_COMPONENTS = (
	{
		"salary_component": "Severance Benefit",
		"salary_component_abbr": "SEV",
		"type": "Earning",
		"description": "Severance benefit lump sum subject to a SARS tax directive",
		"is_tax_applicable": 1,
	},
	{
		"salary_component": "Leave Payout",
		"salary_component_abbr": "LEAVE",
		"type": "Earning",
		"description": "Termination leave payout",
		"is_tax_applicable": 1,
	},
	{
		"salary_component": "Notice Pay",
		"salary_component_abbr": "NOTICE",
		"type": "Earning",
		"description": "Termination notice pay",
		"is_tax_applicable": 1,
	},
	{
		"salary_component": "Tax on Lump Sum",
		"salary_component_abbr": "LSTAX",
		"type": "Deduction",
		"description": "Employees' tax on a directive-controlled lump sum",
		"is_tax_applicable": 0,
	},
)


def seed_payroll_masters() -> None:
	"""Create missing masters and fill only unconfigured classification fields."""
	if not frappe.db.exists("DocType", "Salary Component"):
		return
	_seed_salary_components()
	_seed_sars_codes()
	_seed_component_links()
	_seed_component_treatments()
	_seed_single_defaults()
	repair_salary_component_accounts()


def repair_salary_component_accounts(company: str | None = None) -> int:
	"""Map components to existing company accounts without creating a chart."""
	if not frappe.db.table_exists("Salary Component Account"):
		return 0
	companies = (
		[company] if company else frappe.get_all("Company", filters={"country": "South Africa"}, pluck="name")
	)
	repaired = 0
	for company_name in companies:
		if not company_name or not frappe.db.exists("Company", company_name):
			continue
		for component, account_name in DEFAULT_SALARY_COMPONENT_ACCOUNT_NAMES.items():
			if not frappe.db.exists("Salary Component", component):
				continue
			account = frappe.db.get_value(
				"Account",
				{"company": company_name, "account_name": account_name, "is_group": 0},
				"name",
			)
			if not account:
				continue
			row_name = frappe.db.get_value(
				"Salary Component Account",
				{"parent": component, "company": company_name},
				"name",
			)
			if row_name:
				if frappe.db.get_value("Salary Component Account", row_name, "account") != account:
					frappe.db.set_value(
						"Salary Component Account",
						row_name,
						"account",
						update_modified=False,
					)
					repaired += 1
				continue
			doc = frappe.get_doc("Salary Component", component)
			doc.append("accounts", {"company": company_name, "account": account})
			doc.save(ignore_permissions=True)
			repaired += 1
	return repaired


def _seed_salary_components() -> None:
	components = [
		*read_packaged_json("za_local_payroll", "setup", "data", "salary_components.json"),
		*TERMINATION_COMPONENTS,
	]
	for values in components:
		component = dict(values)
		component.pop("doctype", None)
		name = component.get("salary_component")
		if not name:
			frappe.throw(_("A packaged Salary Component is missing salary_component."))
		if frappe.db.exists("Salary Component", name):
			if name in GOVERNED_COMPONENT_CLASSIFICATIONS:
				governed_fields = [
					fieldname for fieldname in component if fieldname in GOVERNED_COMPONENT_FIELDS
				]
				current = frappe.db.get_value("Salary Component", name, governed_fields, as_dict=True) or {}
				updates = {
					fieldname: value
					for fieldname, value in component.items()
					if fieldname in GOVERNED_COMPONENT_FIELDS and current.get(fieldname) != value
				}
				if updates:
					frappe.db.set_value("Salary Component", name, updates, update_modified=False)
			continue
		frappe.get_doc(doctype="Salary Component", **component).insert(ignore_permissions=True)


def _seed_sars_codes() -> None:
	if not frappe.db.exists("DocType", "SARS Payroll Code"):
		return
	for values in DEFAULT_SARS_PAYROLL_CODES:
		code = values["code"]
		if frappe.db.exists("SARS Payroll Code", code):
			continue
		frappe.get_doc(doctype="SARS Payroll Code", active=1, **values).insert(ignore_permissions=True)


def _seed_component_links() -> None:
	fields = set(frappe.db.get_table_columns("Salary Component"))
	if "za_sars_payroll_code" in fields:
		for component, code in DEFAULT_SALARY_COMPONENT_SARS_CODES.items():
			if not frappe.db.exists("Salary Component", component):
				continue
			if not frappe.db.get_value("Salary Component", component, "za_sars_payroll_code"):
				frappe.db.set_value(
					"Salary Component",
					component,
					"za_sars_payroll_code",
					code,
					update_modified=False,
				)
	if "za_exclude_from_irp5" in fields:
		for component in DEFAULT_IRP5_EXCLUDED_SALARY_COMPONENTS:
			if frappe.db.exists("Salary Component", component):
				frappe.db.set_value(
					"Salary Component",
					component,
					"za_exclude_from_irp5",
					1,
					update_modified=False,
				)


def _seed_component_treatments() -> None:
	fields = set(frappe.db.get_table_columns("Salary Component"))
	for component, desired in DEFAULT_SALARY_COMPONENT_TREATMENTS.items():
		if not frappe.db.exists("Salary Component", component):
			continue
		available = [field for field in desired if field in fields]
		if not available:
			continue
		current = frappe.db.get_value("Salary Component", component, available, as_dict=True) or {}
		missing = {
			field: desired[field]
			for field in available
			if component in GOVERNED_COMPONENT_CLASSIFICATIONS or current.get(field) in (None, "")
		}
		if missing:
			frappe.db.set_value(
				"Salary Component",
				component,
				missing,
				update_modified=False,
			)


def _seed_single_defaults() -> None:
	if not frappe.db.exists("DocType", "Payroll Settings"):
		return
	meta = frappe.get_meta("Payroll Settings")
	settings = frappe.get_single("Payroll Settings")
	changed = False
	defaults = [
		("za_calculate_annual_taxable_amount_based_on", "Payroll Period"),
		("za_eti_unregulated_minimum_monthly_wage", 2500),
	]
	for fieldname, component in (
		("za_paye_salary_component", "PAYE"),
		("za_uif_employee_salary_component", "UIF Employee Contribution"),
		("za_uif_employer_salary_component", "UIF Employer Contribution"),
		("za_sdl_salary_component", "SDL Contribution"),
		("za_coida_salary_component", "COIDA Contribution"),
	):
		if frappe.db.exists("Salary Component", component):
			defaults.append((fieldname, component))

	for fieldname, value in defaults:
		if meta.has_field(fieldname) and settings.get(fieldname) in (None, ""):
			settings.set(fieldname, value)
			changed = True
	if changed:
		settings.save(ignore_permissions=True)
