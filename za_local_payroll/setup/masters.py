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
			field: desired[field] for field in available if current.get(field) in (None, "")
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
	for fieldname, value in (
		("za_calculate_annual_taxable_amount_based_on", "Payroll Period"),
		("za_eti_unregulated_minimum_monthly_wage", 2500),
	):
		if meta.has_field(fieldname) and settings.get(fieldname) in (None, ""):
			settings.set(fieldname, value)
			changed = True
	if changed:
		settings.save(ignore_permissions=True)
