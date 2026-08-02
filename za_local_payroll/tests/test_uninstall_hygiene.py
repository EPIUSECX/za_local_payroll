"""Uninstall must not orphan schema customisations on core DocTypes.

Frappe's ``remove_app`` deletes records whose DocType links to Module Def. Any
artefact this app writes onto a core Frappe, ERPNext or HRMS DocType must
therefore carry an owning module, or it survives the app and leaves a field
pointing at a DocType that no longer exists.
"""

import frappe
from frappe.tests.classes import IntegrationTestCase

from za_local_payroll.setup.property_setters import (
	OWNING_MODULE,
	_property_setters,
	apply_payroll_property_setters,
)

SUITE_MODULES = ("SA Localisation Core", "SA Localisation Finance", "SA Payroll", "SA Labour", "SA COIDA")


class TestUninstallHygiene(IntegrationTestCase):
	def test_every_payroll_property_setter_declares_its_module(self):
		"""Untagged Property Setters would survive uninstall on core DocTypes."""
		apply_payroll_property_setters()
		untagged = []
		for doctype, fieldname, property_name, _value in _property_setters():
			if not frappe.db.exists("DocType", doctype):
				continue
			filters = {"doc_type": doctype, "property": property_name}
			filters["field_name"] = fieldname if fieldname else ["in", [None, ""]]
			for row in frappe.get_all("Property Setter", filters=filters, fields=["name", "module"]):
				if row.module != OWNING_MODULE:
					untagged.append((doctype, fieldname, property_name, row.module))
		self.assertEqual([], untagged, f"Property Setters missing module {OWNING_MODULE!r}: {untagged}")

	def test_no_suite_custom_field_is_left_without_a_module(self):
		"""Custom Fields are removed by module, so every za_ field must carry one."""
		orphans = frappe.get_all(
			"Custom Field",
			filters={"module": ["is", "not set"], "fieldname": ["like", "za[_]%"]},
			fields=["name", "dt", "fieldname"],
		)
		self.assertEqual([], orphans, f"za_ Custom Fields with no owning module: {orphans}")

	def test_suite_custom_fields_are_owned_by_suite_modules(self):
		"""A field tagged to a foreign module would not be removed with this app."""
		wrong_owner = frappe.get_all(
			"Custom Field",
			filters={
				"fieldname": ["like", "za[_]%"],
				"module": ["not in", SUITE_MODULES],
			},
			fields=["name", "dt", "fieldname", "module"],
		)
		self.assertEqual([], wrong_owner, f"za_ Custom Fields owned by a foreign module: {wrong_owner}")
