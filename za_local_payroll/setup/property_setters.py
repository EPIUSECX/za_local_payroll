"""Payroll-owned property setters for standard HRMS DocTypes."""

import frappe
from frappe.custom.doctype.customize_form.customize_form import (
	docfield_properties,
	doctype_properties,
)
from frappe.custom.doctype.property_setter.property_setter import make_property_setter

OWNING_MODULE = "SA Payroll"

PROTECTED_PAYROLL_DOCTYPES = (
	"Salary Slip",
	"Payroll Entry",
	"Additional Salary",
	"IRP5 Certificate",
	"EMP201 Submission",
	"EMP501 Reconciliation",
	"Tax Directive",
	"Employee Final Settlement",
	"UIF U19 Declaration",
	"Payroll Payment Batch",
)


def apply_payroll_property_setters() -> None:
	"""Apply statutory UI and attachment invariants without changing site preferences."""
	for doctype, fieldname, property_name, value in _property_setters():
		if not frappe.db.exists("DocType", doctype):
			continue
		if fieldname and not frappe.get_meta(doctype).has_field(fieldname):
			continue
		for_doctype = fieldname is None
		property_type = (
			doctype_properties[property_name] if for_doctype else docfield_properties[property_name]
		)
		property_setter = make_property_setter(
			doctype=doctype,
			fieldname=fieldname,
			property=property_name,
			value=value,
			property_type=property_type,
			for_doctype=for_doctype,
			validate_fields_for_doctype=False,
		)
		_claim_ownership(property_setter.name)


def _claim_ownership(property_setter_name: str) -> None:
	"""Tag the Property Setter with this app's module.

	``make_property_setter`` leaves ``module`` empty. Frappe removes records by
	module during uninstall, so an untagged Property Setter would survive on a
	core HRMS DocType after the app is gone.
	"""
	frappe.db.set_value(
		"Property Setter", property_setter_name, "module", OWNING_MODULE, update_modified=False
	)


def _property_setters() -> list[tuple[str, str | None, str, object]]:
	rows = [
		("Salary Structure", "employee_benefits", "hidden", 1),
		("Salary Structure", "max_benefits", "hidden", 1),
		("Salary Structure Assignment", "employee_benefits_section", "hidden", 1),
		("Salary Structure Assignment", "employee_benefits", "hidden", 1),
		("Salary Structure Assignment", "max_benefits", "hidden", 1),
		("Salary Component", "type", "options", "Earning\nDeduction\nCompany Contribution"),
	]
	rows.extend((doctype, None, "protect_attached_files", 1) for doctype in PROTECTED_PAYROLL_DOCTYPES)
	return rows
