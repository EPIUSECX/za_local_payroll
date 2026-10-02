"""Stage 5: VAT201 working paper - snapshot, reconciliation, controls and filing evidence."""

import hashlib
import json

import frappe
from frappe.utils import flt
from frappe.utils.file_manager import save_file

from za_local_payroll.reference_company import constants as C
from za_local_payroll.reference_company.governance import acting_as, user
from za_local_payroll.reference_company.guard import require_reference_site
from za_local_payroll.reference_company.vat import account
from za_local_payroll.reference_company.vat_cycle import EVIDENCE, gl_reconciliation

PERIOD = ("2026-07-01", "2026-08-31")


def _expect_failure(label, fn, results):
	frappe.db.commit()
	try:
		fn()
	except Exception as exc:
		frappe.db.rollback()
		results[label] = {"blocked": True, "message": frappe.utils.strip_html(str(exc))[:300]}
		return
	results[label] = {"blocked": False, "message": "NOT BLOCKED"}


def _new_return(amended_from=None):
	doc = frappe.get_doc(
		{
			"doctype": "VAT201 Return",
			"company": C.COMPANY,
			"filing_category": "Category B",
			"from_date": PERIOD[0],
			"to_date": PERIOD[1],
			"submission_date": "2026-09-25",
			"filing_due_date": "2026-09-30",
			"filing_reviewer": user("reviewer"),
			"filing_approver": user("approver"),
			"amended_from": amended_from,
			"notes": "Reference company Jul-Aug 2026 VAT201 working paper (synthetic).",
		}
	)
	doc.insert()
	return doc


def stage_vat201() -> dict:
	require_reference_site()
	results = {"controls": {}}
	existing = frappe.db.get_value(
		"VAT201 Return", {"company": C.COMPANY, "from_date": PERIOD[0], "docstatus": 1}, "name"
	)
	if existing and frappe.db.get_value("VAT201 Return", existing, "status") == "Accepted":
		return {"vat201": existing, "note": "already submitted"}

	with acting_as(user("preparer")):
		draft = frappe.db.get_value(
			"VAT201 Return", {"company": C.COMPANY, "from_date": PERIOD[0], "docstatus": 0}, "name"
		)
		doc = frappe.get_doc("VAT201 Return", draft) if draft else _new_return()
		feedback = doc.get_vat_transactions()
		doc.reload()
		results["fetch_feedback"] = feedback
		results["review_items"] = [
			{
				"voucher": r.voucher_no,
				"classification": r.classification,
				"status": r.classification_status,
				"issue": r.classification_issue,
				"tax": r.tax_amount,
				"gl": r.gl_tax_amount,
			}
			for r in doc.transactions
			if r.classification_status != "Classified"
		]

		# Duplicate period must be refused while this paper is active.
		_expect_failure("duplicate_period", _new_return, results["controls"])

		doc.reload()

	results["box_totals"] = _boxes(doc)
	results["reconciliation"] = {
		"source_vat_total": doc.source_vat_total,
		"gl_vat_total": doc.gl_vat_total,
		"reconciliation_difference": doc.reconciliation_difference,
		"reconciliation_status": doc.reconciliation_status,
		"live_ledger_sha256": doc.live_ledger_sha256,
		"source_snapshot_sha256": doc.source_snapshot_sha256,
		"gl_snapshot_sha256": doc.gl_snapshot_sha256,
		"independent_gl": gl_reconciliation(*PERIOD),
	}
	unresolved = [r for r in doc.transactions if r.classification_status == "Needs Review"]
	results["unresolved_before_submit"] = len(unresolved)

	# Reviewer cannot submit the VAT201 itself (Accounts Manager owns submission).
	with acting_as(user("reviewer")):
		_expect_failure(
			"reviewer_submits_vat201",
			lambda: frappe.get_doc("VAT201 Return", doc.name).submit(),
			results["controls"],
		)

	with acting_as(user("preparer")):
		doc = frappe.get_doc("VAT201 Return", doc.name)
		if unresolved:
			results["submit_with_review_items"] = "skipped - review items outstanding"
			_expect_failure("submit_with_open_review_items", doc.submit, results["controls"])
			return _write(results | {"vat201": doc.name})
		# Stale ledger: a VAT-account journal posted after the snapshot must block submit.
		je = _vat_journal("2026-08-30", 100)
		results["stale_journal"] = je
		_expect_failure(
			"submit_after_live_ledger_change",
			frappe.get_doc("VAT201 Return", doc.name).submit,
			results["controls"],
		)
		_cancel_as_admin("Journal Entry", je)
		doc = frappe.get_doc("VAT201 Return", doc.name)
		doc.submit()
		doc.reload()
	results["vat201"] = doc.name
	results["filing"] = doc.za_filing
	results["working_paper"] = {"file": doc.working_paper_file, "sha256": doc.working_paper_sha256}
	results["filing_lifecycle"] = _filing_lifecycle(doc, results["controls"])
	frappe.db.commit()
	return _write(results)


def _vat_journal(posting_date, amount):
	je = frappe.get_doc(
		{
			"doctype": "Journal Entry",
			"company": C.COMPANY,
			"posting_date": posting_date,
			"user_remark": "REFVAT:stale-ledger probe",
			"accounts": [
				{"account": account("VAT Collected - Sales"), "credit_in_account_currency": amount},
				{
					"account": account("Administrative Expenses"),
					"debit_in_account_currency": amount,
					"cost_center": f"Head Office - {C.ABBR}",
				},
			],
		}
	)
	je.insert(ignore_permissions=True)
	je.submit()
	return je.name


def _cancel_as_admin(doctype, name):
	with acting_as("Administrator"):
		frappe.get_doc(doctype, name).cancel()
	frappe.db.commit()


def _boxes(doc):
	fields = [
		"standard_rated_supplies_non_capital",
		"standard_rated_supplies_capital",
		"zero_rated_supplies_local",
		"zero_rated_supplies_exported",
		"exempt_supplies",
		"total_supplies",
		"standard_rated_output_non_capital",
		"standard_rated_output_capital",
		"total_output_tax",
		"capital_goods_input_local",
		"capital_goods_input_imported",
		"other_goods_services_input_local",
		"other_goods_services_input_imported",
		"other_input_adjustment",
		"total_input_tax",
		"vat_payable",
		"vat_refundable",
		"total_amount_payable",
	]
	return {f: flt(doc.get(f), 2) for f in fields}


def _filing_lifecycle(vat201, controls):
	filing = vat201.za_filing
	out = {}
	# The preparer may not review; the approver may not review on someone's behalf.
	with acting_as(user("preparer")):
		_expect_failure(
			"preparer_marks_filing_reviewed",
			lambda: frappe.get_doc("ZA Filing", filing).mark_reviewed(),
			controls,
		)
	with acting_as(user("approver")):
		_expect_failure(
			"approver_before_review", lambda: frappe.get_doc("ZA Filing", filing).submit(), controls
		)
	with acting_as(user("reviewer")):
		frappe.get_doc("ZA Filing", filing).mark_reviewed()
	with acting_as(user("reviewer")):
		_expect_failure(
			"reviewer_approves_own_review", lambda: frappe.get_doc("ZA Filing", filing).submit(), controls
		)
	with acting_as(user("approver")):
		frappe.get_doc("ZA Filing", filing).submit()
	f = frappe.get_doc("ZA Filing", filing)
	out["filing"] = {
		"status": f.status,
		"declared_amount": f.declared_amount,
		"ledger_amount": f.ledger_amount,
		"unexplained_difference": f.unexplained_difference,
		"capability": f.capability,
	}

	evidence = (
		f"SYNTHETIC SARS eFiling acknowledgement - {vat201.name} Jul-Aug 2026 - not a real SARS receipt"
	).encode()
	evidence_sha = hashlib.sha256(evidence).hexdigest()
	with acting_as(user("reviewer")):
		file_url = save_file(
			"vat201-efiling-ack-synthetic.txt", evidence, "VAT201 Return", vat201.name, is_private=1
		).file_url
		kwargs = dict(
			authority_reference=f"SYNTH-EFILING-{vat201.name}",
			response_status="Accepted",
			evidence_file=file_url,
			sha256_checksum=evidence_sha,
			submitted_by=user("submitter"),
			submitted_at="2026-09-28 10:00:00",
		)
		receipt = frappe.get_doc("VAT201 Return", vat201.name).record_submission_receipt(**kwargs)
		again = frappe.get_doc("VAT201 Return", vat201.name).record_submission_receipt(**kwargs)
		out["receipt_idempotent"] = receipt == again
		_expect_failure(
			"receipt_preparer_is_submitter",
			lambda: frappe.get_doc("VAT201 Return", vat201.name).record_submission_receipt(
				**{**kwargs, "submitted_by": user("reviewer"), "sha256_checksum": "0" * 64}
			),
			controls,
		)
	with acting_as(user("reviewer")):
		_expect_failure(
			"receipt_submitted_by_wrong_user",
			lambda: frappe.get_doc("ZA Submission Receipt", receipt).submit(),
			controls,
		)
	with acting_as(user("submitter")):
		frappe.get_doc("ZA Submission Receipt", receipt).submit()
	out["receipt"] = receipt
	out["after_receipt"] = {
		"filing_status": frappe.db.get_value("ZA Filing", filing, "status"),
		"vat201_status": frappe.db.get_value("VAT201 Return", vat201.name, "status"),
	}
	# Cancellation order: receipt -> VAT201 -> filing; wrong order must be refused.
	with acting_as(user("preparer")):
		_expect_failure(
			"cancel_vat201_before_receipt",
			lambda: frappe.get_doc("VAT201 Return", vat201.name).cancel(),
			controls,
		)
	return out


def stage_vat201_amendment() -> dict:
	"""Cancel the accepted paper in the enforced order and amend it with a new snapshot."""
	require_reference_site()
	original = frappe.db.get_value(
		"VAT201 Return",
		{
			"company": C.COMPANY,
			"from_date": PERIOD[0],
			"docstatus": ("<", 3),
			"amended_from": ("is", "not set"),
		},
		"name",
	)
	doc = frappe.get_doc("VAT201 Return", original)
	receipt = frappe.db.get_value("ZA Submission Receipt", {"filing": doc.za_filing, "docstatus": 1}, "name")
	out = {"original": original}
	if receipt:
		with acting_as(user("submitter")):
			frappe.get_doc("ZA Submission Receipt", receipt).cancel()
	out["after_receipt_cancel"] = {
		"filing_status": frappe.db.get_value("ZA Filing", doc.za_filing, "status"),
		"vat201_status": frappe.db.get_value("VAT201 Return", original, "status"),
	}
	if frappe.db.get_value("VAT201 Return", original, "docstatus") == 1:
		with acting_as(user("preparer")):
			frappe.get_doc("VAT201 Return", original).cancel()
	if frappe.db.get_value("ZA Filing", doc.za_filing, "docstatus") == 1:
		with acting_as(user("approver")):
			frappe.get_doc("ZA Filing", doc.za_filing).cancel()
	with acting_as(user("preparer")):
		amended = frappe.copy_doc(frappe.get_doc("VAT201 Return", original), ignore_no_copy=False)
		amended.amended_from = original
		amended.insert()
		amended.get_vat_transactions()
		amended.reload()
	out["amended"] = amended.name
	out["original_snapshot_sha256"] = doc.source_snapshot_sha256
	out["amended_snapshot_sha256"] = amended.source_snapshot_sha256
	out["amended_snapshot_generated_on"] = str(amended.snapshot_generated_on)
	out["amended_filing_link_cleared"] = not amended.za_filing
	out["amended_status"] = amended.status
	out["amended_reconciliation"] = amended.reconciliation_status
	frappe.db.commit()
	(EVIDENCE / "vat201_amendment.json").write_text(json.dumps(out, indent=1, default=str))
	return out


def _write(results):
	EVIDENCE.mkdir(parents=True, exist_ok=True)
	(EVIDENCE / "vat201.json").write_text(json.dumps(results, indent=1, default=str))
	return results
