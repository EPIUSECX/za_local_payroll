"""SARS reference-number check digits (PAYE BRS v25.3.0, Appendix B 8.1 and 8.2)."""

import re

import frappe
from frappe import _

REFERENCE_PREFIXES = {"PAYE": "7", "SDL": "L", "UIF": "U"}


def modulus_10_valid(digits: str) -> bool:
	"""BRS 8.1: double digits 1, 3, 5, 7 and 9 (summing the digits of a two-digit
	result), add digits 2, 4, 6 and 8; the tenth digit is 10 minus the last digit of
	the total, or 0 when that last digit is 0."""
	if not re.fullmatch(r"\d{10}", digits or ""):
		return False
	total = 0
	for index, char in enumerate(digits[:9]):
		value = int(char) * (2 if index % 2 == 0 else 1)
		total += value - 9 if value > 9 else value
	check = (10 - total % 10) % 10
	return check == int(digits[9])


def is_valid_employer_reference(reference: str, kind: str) -> bool:
	"""BRS 8.2: PAYE (7...), SDL (L...) and UIF (U...) references, first character read as 4."""
	reference = (reference or "").strip().upper()
	if len(reference) != 10 or reference[0] != REFERENCE_PREFIXES[kind]:
		return False
	return modulus_10_valid("4" + reference[1:])


def is_valid_income_tax_number(reference: str) -> bool:
	return modulus_10_valid((reference or "").strip())


def validate_company_references(doc, method=None):
	"""Refuse SARS employer references that fail the BRS check digit."""
	for fieldname, kind, label in (
		("za_paye_reference_number", "PAYE", _("PAYE Reference Number")),
		("za_sdl_reference_number", "SDL", _("SDL Reference Number")),
		("za_uif_reference_number", "UIF", _("UIF Reference Number")),
	):
		value = (doc.get(fieldname) or "").strip()
		if value and not is_valid_employer_reference(value, kind):
			frappe.throw(
				_(
					"{0} {1} is not a valid SARS reference: it must start with {2}, have 10 characters and pass "
					"the SARS check digit."
				).format(label, frappe.bold(value), REFERENCE_PREFIXES[kind]),
				title=_("Invalid SARS Reference"),
			)
	income_tax = (doc.get("za_income_tax_reference_number") or "").strip()
	if income_tax and not is_valid_income_tax_number(income_tax):
		frappe.throw(
			_("Income Tax Reference Number {0} fails the SARS check digit.").format(frappe.bold(income_tax)),
			title=_("Invalid SARS Reference"),
		)
