"""Rebuild the whole synthetic reference company, stage by stage, on a fresh .test site.

    bench --site za-rebuild.test set-config za_reference_evidence_dir /path/to/evidence
    bench --site za-rebuild.test execute za_local_payroll.reference_company.run_all.run_all

The evidence directory must already hold ``sources/`` (archived official
documents) and ``golden/golden_statutory_2026_27.json``. Each stage is
idempotent; a re-run resumes after the last stage recorded as complete.
The run stops at the first failing stage and records the error.
"""

import json
import time
import traceback

import frappe

from za_local_payroll.reference_company import (
	coida,
	config_evidence,
	ee_skills,
	foundation,
	golden_compare,
	governance,
	labour,
	multicompany,
	paths,
	payroll_reconcile,
	payroll_run,
	payroll_setup,
	permissions,
	personas,
	privacy,
	vat,
	vat201,
	vat_cycle,
)
from za_local_payroll.reference_company.guard import commit_stage, require_reference_site
from za_local_payroll.reference_company.schedule import MONTHS

BEFORE_TERMINATION = [m for m in MONTHS if m < "2026-11"]
FROM_TERMINATION = [m for m in MONTHS if m >= "2026-11"]


def _months(months):
	def run():
		return {month: payroll_run.run_month(month) for month in months}

	return run


def _termination():
	"""Leaver inputs and the SARS directive, then November to February as installed."""
	inputs = payroll_run.stage_termination_inputs()
	return {"inputs": inputs, **_months(FROM_TERMINATION)()}


STAGES = (
	("01 foundation", foundation.stage_foundation),
	("02 governance", governance.stage_governance),
	("03 vat setup", vat.stage_vat_setup),
	("04 vat transactions", vat_cycle.stage_vat_transactions),
	("05 vat purchase correction", vat_cycle.correct_zero_and_exempt_purchases),
	("06 vat invoice pdfs", vat_cycle.render_invoice_pdfs),
	("07 vat201", vat201.stage_vat201),
	("08 vat201 amendment", vat201.stage_vat201_amendment),
	("09 payroll setup", payroll_setup.stage_payroll_setup),
	("10 personas", personas.stage_personas),
	("11 additional salary", payroll_run.stage_additional_salaries),
	("12 payroll Mar-Oct", _months(BEFORE_TERMINATION)),
	("13 termination and Nov-Feb", _termination),
	("14 weekly fortnightly hourly", payroll_run.run_frequencies),
	("15 golden comparison monthly", golden_compare.compare_year),
	("16 golden comparison frequencies", golden_compare.compare_frequencies),
	("17 payroll gl reconciliation", payroll_reconcile.reconcile_payroll_gl),
	("18 payment batch", payroll_reconcile.stage_payment_batch),
	("19 emp201", payroll_reconcile.stage_emp201),
	("20 certificates", payroll_reconcile.stage_certificates),
	("21 emp501", payroll_reconcile.stage_emp501),
	("21b certificate pdfs", payroll_reconcile.render_certificate_pdfs),
	("22 leave", labour.stage_leave_tests),
	("23 sick-leave occasions", labour.stage_sick_occasion_retest),
	("24 labour rates", labour.stage_rate_tests),
	("25 termination calculations", labour.stage_termination_tests),
	("26 employment equity", ee_skills.stage_employment_equity),
	("27 skills", ee_skills.stage_skills),
	("28 coida return", coida.stage_coida_return),
	("29 injury and oid claim", coida.stage_injury_claim),
	("30 privacy registers", privacy.stage_privacy_registers),
	("31 privacy cases", privacy.stage_privacy_cases),
	("32 multi-company", multicompany.stage_multicompany),
	("33 permission matrix", permissions.stage_permission_matrix),
	("34 configuration evidence", config_evidence.stage_config_evidence),
)


def _summary(value):
	text = json.dumps(value, default=str)
	return text if len(text) <= 400 else text[:400] + "..."


def run_all(restart: bool = False) -> dict:
	require_reference_site()
	log_file = paths.root() / "run_all.json"
	log = {} if restart or not log_file.exists() else json.loads(log_file.read_text())
	log.setdefault("site", frappe.local.site)
	stages = log.setdefault("stages", {})
	for label, fn in STAGES:
		if stages.get(label, {}).get("status") == "complete":
			continue
		started = time.time()
		try:
			result = fn()
			commit_stage()
			stages[label] = {
				"status": "complete",
				"seconds": round(time.time() - started, 1),
				"summary": _summary(result),
			}
		except Exception as exc:
			frappe.db.rollback()
			stages[label] = {
				"status": "failed",
				"seconds": round(time.time() - started, 1),
				"error": str(exc)[:500],
				"traceback": traceback.format_exc()[-3000:],
			}
			log_file.write_text(json.dumps(log, indent=1, default=str))
			raise
		log_file.write_text(json.dumps(log, indent=1, default=str))
	log["complete"] = all(stages.get(label, {}).get("status") == "complete" for label, _fn in STAGES)
	log_file.write_text(json.dumps(log, indent=1, default=str))
	return {label: stages[label]["status"] for label, _fn in STAGES}
