"""Align the SARS payroll code master and shipped component mappings with BRS v25.3.0.

The code master is statutory reference data, so it is re-seeded in place. A
component is re-mapped only where it still carries the old shipped default for
its name; a code a practitioner chose deliberately is left alone.
"""

import frappe

from za_local_payroll.setup.masters import _seed_sars_codes

CORRECTED_DEFAULTS = {
	"Commission": ("3605", "3606"),
	"Housing Allowance": ("3702", "3713"),
	"Accommodation Allowance": ("3702", "3713"),
	"Cell Phone Allowance": ("3702", "3713"),
	"Provident Fund": ("4001", "4003"),
	"Medical Aid Company Contribution": ("4474", "3810"),
	"Leave Payout": ("3907", "3605"),
}


def execute() -> None:
	if not frappe.db.exists("DocType", "SARS Payroll Code"):
		return
	_seed_sars_codes()
	if "za_sars_payroll_code" not in frappe.db.get_table_columns("Salary Component"):
		return
	for component, (old, new) in CORRECTED_DEFAULTS.items():
		if frappe.db.get_value("Salary Component", component, "za_sars_payroll_code") == old:
			frappe.db.set_value(
				"Salary Component", component, "za_sars_payroll_code", new, update_modified=False
			)
