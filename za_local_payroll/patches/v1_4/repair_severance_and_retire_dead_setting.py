"""Repair the shipped Severance Benefit classification and retire a dead setting.

Severance Benefit was installed as UIF, SDL and COIDA applicable because the
applicability fields default to 1 and seeding only filled blank fields. A
severance benefit is not remuneration for SDL (gross income paragraph (d)) or
UIF, nor COIDA earnings. Only components still carrying that untouched default
combination are corrected; a deliberate configuration is left alone.

Payroll Settings "Official Interest Rate" was never read: the rate is resolved
by date from the governed statutory rates. Its description invited
administrators to maintain it, so the field is removed.
"""

import frappe


def execute() -> None:
	if frappe.db.exists("Salary Component", "Severance Benefit"):
		columns = set(frappe.db.get_table_columns("Salary Component"))
		flags = [f for f in ("za_uif_applicable", "za_sdl_applicable", "za_coida_applicable") if f in columns]
		if flags:
			current = frappe.db.get_value("Salary Component", "Severance Benefit", flags, as_dict=True) or {}
			if all(int(current.get(f) or 0) == 1 for f in flags):
				frappe.db.set_value(
					"Salary Component", "Severance Benefit", dict.fromkeys(flags, 0), update_modified=False
				)
	custom_field = frappe.db.exists(
		"Custom Field", {"dt": "Payroll Settings", "fieldname": "za_official_interest_rate"}
	)
	if custom_field:
		frappe.delete_doc("Custom Field", custom_field, ignore_permissions=True, force=True)
