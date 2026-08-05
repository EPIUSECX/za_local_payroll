"""Approved statutory-rate resolution for workplace calculations."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt, getdate
from za_local_core.governance import validate_private_evidence
from za_local_core.services.rates import resolve_rate

from za_local_payroll.services.tax import (
	get_coida_annual_earnings_cap as _get_legacy_coida_cap,
)
from za_local_payroll.services.tax import (
	get_reimbursive_travel_rate as _get_reimbursive_travel_rate,
)

COIDA_CAP_RULE = "coida.annual_earnings_cap"
COIDA_MINIMUM_RULE = "coida.minimum_assessment"
COIDA_DOMESTIC_MINIMUM_RULE = "coida.domestic_minimum_assessment"
BCEA_THRESHOLD_RULE = "bcea.earnings_threshold.annual"
NMW_RULES = {
	"General NMW": "nmw.general.hourly",
	"EPWP": "nmw.epwp.hourly",
	"Learnership Schedule 2": "nmw.learnership.schedule_2_reference",
}

# Verification anchors only. Calculations still require independently approved
# ZA Statutory Rate Packs and never fall back to these constants.
OFFICIAL_2026_REFERENCE_VALUES = {
	COIDA_CAP_RULE: {
		"value": 668000,
		"effective_from": "2026-03-01",
		"source": "COIDA-GAZETTE-54577-NOTICE-3910",
	},
	COIDA_MINIMUM_RULE: {
		"value": 1621,
		"effective_from": "2026-03-01",
		"source": "COIDA-GAZETTE-54577-NOTICE-3910",
	},
	COIDA_DOMESTIC_MINIMUM_RULE: {
		"value": 560,
		"effective_from": "2026-03-01",
		"source": "COIDA-GAZETTE-54577-NOTICE-3910",
	},
	BCEA_THRESHOLD_RULE: {
		"value": 269900.90,
		"effective_from": "2026-05-01",
		"source": "DEL-BCEA-EARNINGS-THRESHOLD-2026",
	},
	"nmw.general.hourly": {
		"value": 30.23,
		"effective_from": "2026-03-01",
		"source": "DEL-NMW-GAZETTE-54075-NOTICE-7083",
	},
	"nmw.epwp.hourly": {
		"value": 16.62,
		"effective_from": "2026-03-01",
		"source": "DEL-NMW-GAZETTE-54075-NOTICE-7083",
	},
	"nmw.learnership.schedule_2_reference": {
		"value": "Schedule 2 allowances",
		"effective_from": "2026-03-01",
		"source": "DEL-NMW-GAZETTE-54075-NOTICE-7083",
	},
}


def get_coida_annual_earnings_cap(date_value=None) -> float:
	"""Return the approved COIDA annual earnings ceiling for a date."""
	return flt(resolve_coida_cap(date_value).value)


def resolve_coida_cap(date_value=None) -> frappe._dict:
	"""Resolve the COIDA cap from core governance or an approved migration fallback."""
	on_date = getdate(date_value)
	approved = _get_core_rate("COIDA", COIDA_CAP_RULE, on_date)
	if approved:
		return approved

	settings = _get_approved_legacy_fallback(on_date)
	return frappe._dict(
		value=flt(_get_legacy_coida_cap(on_date)),
		source="Approved controlled legacy fallback",
		rule_key=COIDA_CAP_RULE,
		source_reference=settings.legacy_rate_source_reference,
	)


def resolve_coida_industry_rate(company: str, industry_class: str, date_value=None) -> frappe._dict:
	"""Resolve a company/class assessment rate with an explicit rule-key hierarchy."""
	if not company or not industry_class:
		frappe.throw(_("Company and Industry Class are required to resolve a COIDA assessment rate."))

	on_date = getdate(date_value)
	for rule_key in _industry_rate_rule_keys(company, industry_class):
		approved = _get_core_rate("COIDA", rule_key, on_date)
		if approved:
			return approved

	settings = _get_approved_legacy_fallback(on_date)
	rows = list(settings.get("industry_rates") or [])
	company_rows = [
		row for row in rows if row.get("company") == company and row.industry_class == industry_class
	]
	legacy_rows = [row for row in rows if not row.get("company") and row.industry_class == industry_class]
	matches = company_rows or legacy_rows
	if len(matches) != 1:
		frappe.throw(
			_(
				"The approved legacy fallback must contain exactly one COIDA rate for company {0} "
				"and industry class {1}."
			).format(frappe.bold(company), frappe.bold(industry_class)),
			title=_("Ambiguous COIDA Assessment Rate"),
		)
	rate = flt(matches[0].assessment_rate)
	if rate <= 0:
		frappe.throw(_("The approved COIDA assessment rate must be greater than zero."))
	return frappe._dict(
		value=rate,
		source="Approved controlled legacy fallback",
		rule_key=_industry_rate_rule_keys(company, industry_class)[0],
		source_reference=settings.legacy_rate_source_reference,
	)


def get_reimbursive_travel_rate(date_value=None) -> float:
	"""Return the approved reimbursive travel rate for a trip date."""
	return _get_reimbursive_travel_rate(date_value)


def resolve_coida_minimum_assessment(employer_category: str, date_value=None) -> frappe._dict:
	"""Resolve the applicable general or domestic-employer minimum assessment."""
	on_date = getdate(date_value)
	if employer_category == "Domestic Employer":
		rule_key = COIDA_DOMESTIC_MINIMUM_RULE
		legacy_field = "legacy_domestic_minimum_assessment"
	elif employer_category == "General Employer":
		rule_key = COIDA_MINIMUM_RULE
		legacy_field = "legacy_minimum_assessment"
	else:
		frappe.throw(_("Select General Employer or Domestic Employer for the COIDA minimum."))
	approved = _get_core_rate("COIDA", rule_key, on_date)
	if approved:
		return approved
	settings = _get_approved_legacy_fallback(on_date)
	value = flt(settings.get(legacy_field))
	if value <= 0:
		frappe.throw(_("The approved legacy COIDA fallback has no value for {0}.").format(rule_key))
	return frappe._dict(
		value=value,
		source="Approved controlled legacy fallback",
		rule_key=rule_key,
		source_reference=settings.legacy_rate_source_reference,
	)


def resolve_bcea_earnings_threshold(date_value) -> frappe._dict:
	"""Resolve the annual BCEA threshold; no guessed/current-date fallback is allowed."""
	return _require_core_rate("Labour", BCEA_THRESHOLD_RULE, date_value)


def resolve_nmw_rate(worker_category: str, date_value) -> frappe._dict:
	"""Resolve an exact NMW category without applying the general rate to special categories."""
	if worker_category not in NMW_RULES:
		frappe.throw(
			_(
				"No automated NMW rate is defined for category {0}; complete a controlled manual review."
			).format(frappe.bold(worker_category or _("Not specified")))
		)
	return _require_core_rate("Labour", NMW_RULES[worker_category], date_value)


def _get_core_rate(domain: str, rule_key: str, on_date) -> frappe._dict | None:
	try:
		resolved = resolve_rate(domain, rule_key, str(on_date))
	except frappe.ValidationError as exc:
		if "No approved" not in str(exc):
			raise
		return None
	return frappe._dict(
		value=resolved["value"],
		source="ZA Statutory Rate Pack",
		rule_key=rule_key,
		source_reference=resolved["source"],
		rate_pack=resolved["rate_pack"],
		source_sha256=resolved["source_sha256"],
	)


def _require_core_rate(domain: str, rule_key: str, date_value) -> frappe._dict:
	on_date = getdate(date_value)
	resolution = _get_core_rate(domain, rule_key, on_date)
	if not resolution:
		frappe.throw(
			_("Configure and approve {0} in a source-backed ZA Statutory Rate Pack for {1}.").format(
				rule_key, on_date
			),
			title=_("Missing Approved Labour Rule"),
		)
	return resolution


def _get_approved_legacy_fallback(on_date):
	settings = frappe.get_single("COIDA Settings")
	if not settings.get("allow_legacy_rate_fallback"):
		frappe.throw(
			_(
				"No approved core COIDA rate applies on {0}. Configure and submit a ZA Statutory Rate Pack, "
				"or complete the independently approved legacy-rate migration control in COIDA Settings."
			).format(on_date),
			title=_("Missing Approved COIDA Rate"),
		)
	if settings.get("legacy_rate_fallback_status") != "Approved":
		frappe.throw(
			_("The COIDA legacy-rate fallback is not independently approved."),
			title=_("Unapproved COIDA Rate Fallback"),
		)
	if not settings.get("legacy_rate_effective_from") or not settings.get("legacy_rate_effective_to"):
		frappe.throw(_("Set the effective dates for the COIDA legacy-rate fallback."))
	if not (
		getdate(settings.legacy_rate_effective_from) <= on_date <= getdate(settings.legacy_rate_effective_to)
	):
		frappe.throw(_("The approved COIDA legacy-rate fallback does not apply on {0}.").format(on_date))
	if not settings.get("legacy_rate_source_reference") or not settings.get("legacy_rate_reviewed_by"):
		frappe.throw(_("The approved COIDA legacy-rate fallback is missing source or reviewer evidence."))
	if settings.get("legacy_rate_prepared_by") == settings.get("legacy_rate_reviewed_by"):
		frappe.throw(_("The COIDA legacy-rate preparer and reviewer must be different users."))
	validate_private_evidence(settings, "legacy_rate_evidence", required=True)
	return settings


def _industry_rate_rule_keys(company: str, industry_class: str) -> tuple[str, str]:
	return (
		f"coida.assessment_rate.{company}.{industry_class}",
		f"coida.assessment_rate.{industry_class}",
	)
