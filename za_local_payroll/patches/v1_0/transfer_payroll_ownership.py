"""Transfer the existing SA Payroll module to its dedicated app."""

import frappe


def execute() -> None:
	"""Set canonical app ownership without renaming DocTypes or database tables."""
	if frappe.db.exists("Module Def", "SA Payroll"):
		frappe.db.set_value(
			"Module Def",
			"SA Payroll",
			"app_name",
			"za_local_payroll",
			update_modified=False,
		)
	if frappe.db.exists("Workspace", "SA Payroll"):
		meta = frappe.get_meta("Workspace")
		if meta.has_field("app"):
			frappe.db.set_value(
				"Workspace",
				"SA Payroll",
				"app",
				"za_local_payroll",
				update_modified=False,
			)
