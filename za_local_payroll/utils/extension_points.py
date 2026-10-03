"""Hooks other installed apps can use to extend South African payroll.

Each extension point is a Frappe hook name. When no installed app declares it, payroll
behaves exactly as it does without the hook. Hooks are called in app install order.

``za_payroll_after_calculate_net_pay``
	``callable(salary_slip) -> None``. Runs after PAYE, UIF, SDL, ETI and company
	contributions are calculated. A hook that changes rows must leave the slip's totals
	consistent (call ``salary_slip.set_net_pay()`` or the HRMS totals helpers).

``za_payroll_supplementary_entry``
	``callable(payroll_entry_name) -> bool``. True marks a sanctioned supplementary run:
	its employees may already have a submitted slip for the same pay period.

``za_payroll_prior_period_count``
	``callable(salary_slip, count) -> int``. Adjusts the number of pay periods already
	paid in the tax year (for example periods paid by a previous payroll system).

``za_payroll_bank_formats``
	``callable() -> dict[str, str]``. Maps a bank file format name to the dotted path of a
	renderer object with ``validate_company_account(account)`` and
	``render(snapshot) -> dict(content=str, control_total=str, filename=str)``. Registered
	names are added to the Payroll Payment Batch bank format list by
	``sync_bank_format_options()``, which runs on migrate; an app whose formats change at
	run time calls it after the change.

``za_payroll_payment_recipients``
	``callable(recipients: list, batch) -> list``. May replace one recipient with several
	(split pay). The total paid per Salary Slip must not change.
"""

from __future__ import annotations

import frappe


def _hooks(name: str) -> list:
	return [frappe.get_attr(path) for path in frappe.get_hooks(name) or []]


def after_calculate_net_pay(salary_slip) -> None:
	for hook in _hooks("za_payroll_after_calculate_net_pay"):
		hook(salary_slip)


def is_supplementary_entry(payroll_entry: str | None) -> bool:
	if not payroll_entry:
		return False
	return any(hook(payroll_entry) for hook in _hooks("za_payroll_supplementary_entry"))


def prior_period_count(salary_slip, count: int) -> int:
	for hook in _hooks("za_payroll_prior_period_count"):
		count = hook(salary_slip, count)
	return count


def bank_formats() -> dict[str, str]:
	formats = {}
	for hook in _hooks("za_payroll_bank_formats"):
		formats.update(hook() or {})
	return formats


def bank_format_renderer(bank_format: str):
	path = bank_formats().get(bank_format)
	return frappe.get_attr(path) if path else None


BANK_FORMAT_DOCTYPE = "Payroll Payment Batch"


def sync_bank_format_options() -> list[str]:
	"""Offer the standard bank formats plus every registered one on Payroll Payment Batch."""
	if not frappe.db.exists("DocType", BANK_FORMAT_DOCTYPE):
		return []
	standard = (
		frappe.db.get_value(
			"DocField", {"parent": BANK_FORMAT_DOCTYPE, "fieldname": "bank_format"}, "options"
		)
		or ""
	)
	options = [line for line in standard.splitlines() if line]
	options += [name for name in sorted(bank_formats()) if name not in options]
	from frappe.custom.doctype.property_setter.property_setter import make_property_setter

	if options == [line for line in standard.splitlines() if line]:
		frappe.db.delete(
			"Property Setter",
			{"doc_type": BANK_FORMAT_DOCTYPE, "field_name": "bank_format", "property": "options"},
		)
	else:
		make_property_setter(
			BANK_FORMAT_DOCTYPE,
			"bank_format",
			"options",
			"\n".join(options),
			"Text",
			validate_fields_for_doctype=False,
		)
	frappe.clear_cache(doctype=BANK_FORMAT_DOCTYPE)
	return options


@frappe.whitelist(methods=["GET"])
def registered_bank_format_names() -> list[str]:
	"""Bank formats an installed app has registered (they are automated, not manual onboarding)."""
	return sorted(bank_formats())


def payment_recipients(recipients: list, batch) -> list:
	for hook in _hooks("za_payroll_payment_recipients"):
		recipients = hook(recipients, batch)
	return recipients
