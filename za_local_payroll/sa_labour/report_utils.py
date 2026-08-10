"""Shared validation for sensitive SA Labour reports."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import cint, getdate, today


def get_controlled_manual_message() -> str:
	"""Build the working-paper banner at call time.

	Translating at module level would resolve the string once per process, in
	whichever language happened to import it first, and then serve that to every
	site and user the worker handles afterwards.
	"""
	return _(
		"Controlled Manual working paper: review the reporting basis, effective source, privacy suppression, "
		"and current Department of Employment and Labour submission requirements before external use."
	)


def get_permitted_company(filters):
	filters = filters or {}
	company = filters.get("company")
	if not company:
		frappe.throw(_("Company is required to run this report."))
	frappe.has_permission("Company", "read", company, throw=True)
	frappe.has_permission("Employee", "read", throw=True)
	return company


def validate_employee_fields(required_fields):
	meta = frappe.get_meta("Employee")
	missing_fields = sorted(field for field in required_fields if not meta.has_field(field))
	if missing_fields:
		frappe.throw(
			_("Employment Equity setup is incomplete. Missing Employee fields: {0}").format(
				", ".join(missing_fields)
			),
			title=_("Setup Required"),
		)


def get_reporting_date(filters):
	value = (filters or {}).get("reporting_date")
	if not value:
		frappe.throw(_("Reporting Date is required to run this report."))
	return getdate(value)


def get_small_cell_control(filters, company: str, target_plan: str | None = None) -> tuple[int, bool]:
	threshold = 5
	if target_plan:
		threshold = cint(
			frappe.db.get_value("Employment Equity Target Plan", target_plan, "small_cell_threshold") or 5
		)
	elif frappe.get_meta("Company").has_field("za_ee_small_cell_threshold"):
		threshold = cint(frappe.get_cached_value("Company", company, "za_ee_small_cell_threshold") or 5)
	threshold = max(threshold, 1)

	show_small_cells = cint((filters or {}).get("show_small_cells")) == 1
	if show_small_cells and not can_view_small_cells():
		frappe.throw(
			_("You are not permitted to reveal suppressed Employment Equity cells."),
			frappe.PermissionError,
		)
	return threshold, show_small_cells


def can_view_small_cells() -> bool:
	return bool(
		{"ZA Compliance Reviewer", "ZA Compliance Manager", "System Manager"}.intersection(frappe.get_roles())
	)


def suppress_count(value, threshold: int, show_small_cells: bool):
	count = cint(value)
	if show_small_cells or count == 0 or count >= threshold:
		return count
	return f"<{threshold}"


def is_small_cell(value, threshold: int, show_small_cells: bool) -> bool:
	count = cint(value)
	return not show_small_cells and 0 < count < threshold


def default_reporting_date():
	return today()
