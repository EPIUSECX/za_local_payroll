"""Desk permission helpers for the payroll localisation app."""

import frappe


def has_app_permission() -> bool:
	"""Show payroll features only to users who may read salary slips."""
	return bool(frappe.has_permission("Salary Slip", "read"))
