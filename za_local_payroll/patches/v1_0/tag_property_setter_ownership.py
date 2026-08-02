"""Tag already-installed payroll Property Setters with their owning module.

Earlier releases created these through ``make_property_setter``, which leaves
``module`` empty. Frappe removes records by module during uninstall, so without
this backfill they would survive on core HRMS DocTypes after the app is gone.
"""

import frappe

from za_local_payroll.setup.property_setters import OWNING_MODULE, _property_setters


def execute() -> None:
	for doctype, fieldname, property_name, _value in _property_setters():
		filters = {"doc_type": doctype, "property": property_name, "module": ["is", "not set"]}
		filters["field_name"] = fieldname if fieldname else ["in", [None, ""]]
		for name in frappe.get_all("Property Setter", filters=filters, pluck="name"):
			frappe.db.set_value("Property Setter", name, "module", OWNING_MODULE, update_modified=False)
