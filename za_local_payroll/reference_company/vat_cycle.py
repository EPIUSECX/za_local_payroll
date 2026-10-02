"""Stage 4: VAT transaction cycle, invoice readiness, PDFs and GL reconciliation."""

import json
from pathlib import Path

import frappe
from frappe.utils import flt

from za_local_payroll.reference_company import constants as C
from za_local_payroll.reference_company import paths
from za_local_payroll.reference_company.guard import require_reference_site
from za_local_payroll.reference_company.vat import account, template

EVIDENCE = paths.VAT
VAT_CUSTOMER = "Ref Customer VAT Vendor (Pty) Ltd"
INDIVIDUAL = "Ref Customer Individual"
EXPORT_CUSTOMER = "Ref Export Customer Inc"
VAT_SUPPLIER = "Ref Supplier VAT Vendor (Pty) Ltd"

ST = "Sales Taxes and Charges Template"
PT = "Purchase Taxes and Charges Template"


def _key(label):
	return f"REFVAT:{label}"


def _existing(doctype, label):
	return frappe.db.get_value(doctype, {"remarks": _key(label), "docstatus": 1}, "name")


def _gross(net: float, rate: float = 15) -> float:
	return round(net + round(net * rate / 100, 2), 2)


def _net_for_gross(gross: float, rate: float = 15, above: bool = False) -> float:
	"""Net amount whose ERPNext-rounded gross equals ``gross``.

	Not every cent value is reachable at 15% with rounded VAT (R5,000.01 is not), so
	an ``above`` boundary case uses the smallest reachable gross strictly above it.
	"""
	net = round(gross / (1 + rate / 100), 2)
	candidates = [round(net + delta / 100, 2) for delta in range(-3, 4)]
	if above:
		return min(c for c in candidates if _gross(c, rate) > round(gross - 0.01, 2))
	for candidate in candidates:
		if _gross(candidate, rate) == round(gross, 2):
			return candidate
	frappe.throw(f"No net amount produces gross {gross}")


def sales_invoice(
	label,
	posting_date,
	customer,
	item,
	rate,
	tax_template,
	*,
	qty=1,
	currency=None,
	conversion_rate=None,
	is_return=0,
	return_against=None,
	reason=None,
	line_category=None,
	line_category_reason=None,
):
	if name := _existing("Sales Invoice", label):
		return name
	doc = frappe.get_doc(
		{
			"doctype": "Sales Invoice",
			"company": C.COMPANY,
			"customer": customer,
			"posting_date": posting_date,
			"set_posting_time": 1,
			"due_date": posting_date,
			"currency": currency or "ZAR",
			"conversion_rate": conversion_rate or 1,
			"is_return": is_return,
			"return_against": return_against,
			"za_adjustment_reason": reason,
			"taxes_and_charges": template(ST, tax_template) if tax_template else None,
			"remarks": _key(label),
			"items": [
				{
					"item_code": item,
					"qty": -qty if is_return else qty,
					"rate": rate,
					"income_account": frappe.db.get_value(
						"Item Default", {"parent": item, "company": C.COMPANY}, "income_account"
					)
					or account("Sales"),
					"cost_center": f"Sales - {C.ABBR}",
					"custom_sa_vat_category": line_category,
					"za_vat_category_reason": line_category_reason,
				}
			],
		}
	)
	if doc.taxes_and_charges:
		doc.set_taxes()
	doc.set_missing_values()
	doc.insert(ignore_permissions=True)
	doc.submit()
	return doc.name


def purchase_invoice(
	label,
	posting_date,
	supplier,
	item,
	rate,
	tax_template,
	*,
	qty=1,
	treatment=None,
	evidence=None,
	percentage=None,
	is_return=0,
	return_against=None,
	bill_no=None,
):
	if name := _existing("Purchase Invoice", label):
		return name
	row = {
		"item_code": item,
		"qty": -qty if is_return else qty,
		"rate": rate,
		"expense_account": frappe.db.get_value(
			"Item Default", {"parent": item, "company": C.COMPANY}, "expense_account"
		)
		or account("Administrative Expenses"),
		"cost_center": f"Head Office - {C.ABBR}",
	}
	if treatment:
		row.update(
			{
				"za_vat_input_treatment": treatment,
				"za_vat_treatment_evidence": evidence,
				"za_vat_deduction_percentage": percentage,
			}
		)
	doc = frappe.get_doc(
		{
			"doctype": "Purchase Invoice",
			"company": C.COMPANY,
			"supplier": supplier,
			"posting_date": posting_date,
			"set_posting_time": 1,
			"bill_no": bill_no or label,
			"bill_date": posting_date,
			"due_date": posting_date,
			"is_return": is_return,
			"return_against": return_against,
			"taxes_and_charges": template(PT, tax_template) if tax_template else None,
			"remarks": _key(label),
			"items": [row],
		}
	)
	if doc.taxes_and_charges:
		doc.set_taxes()
	doc.set_missing_values()
	doc.insert(ignore_permissions=True)
	doc.submit()
	return doc.name


def _ensure_exchange_rates():
	for from_c, rate in (("USD", 18.20), ("EUR", 19.80)):
		if not frappe.db.exists(
			"Currency Exchange", {"from_currency": from_c, "to_currency": "ZAR", "date": "2026-07-01"}
		):
			frappe.get_doc(
				{
					"doctype": "Currency Exchange",
					"date": "2026-07-01",
					"from_currency": from_c,
					"to_currency": "ZAR",
					"exchange_rate": rate,
					"for_buying": 1,
					"for_selling": 1,
				}
			).insert(ignore_permissions=True)
		frappe.db.set_value("Currency", from_c, "enabled", 1)


def stage_vat_transactions() -> dict:
	require_reference_site()
	_ensure_exchange_rates()
	ar_usd = _ensure_usd_receivable()
	docs = {}
	# Sales (period Jul-Aug 2026, Category B)
	docs["S1 standard full"] = sales_invoice(
		"S1", "2026-07-03", VAT_CUSTOMER, "REF-SVC-STD", 10000, "SA Standard Rated Sales"
	)
	docs["S2 zero-rated local"] = sales_invoice(
		"S2", "2026-07-05", VAT_CUSTOMER, "REF-ZR-FOOD", 3000, "SA Zero Rated Sales"
	)
	docs["S3 export USD"] = sales_invoice(
		"S3",
		"2026-07-08",
		EXPORT_CUSTOMER,
		"REF-EXPORT",
		1000,
		"SA Export Zero Rated Sales",
		currency="USD",
		conversion_rate=18.20,
	)
	docs["S4 exempt"] = sales_invoice("S4", "2026-07-10", INDIVIDUAL, "REF-EXEMPT", 8000, "SA Exempt Sales")
	for label, gross, above in (
		("T1 below 50", 49.99, False),
		("T2 at 50", 50.00, False),
		("T3 above 50", 50.01, True),
		("T4 below 5000", 4999.99, False),
		("T5 at 5000", 5000.00, False),
		("T6 above 5000", 5000.01, True),
	):
		docs[label] = sales_invoice(
			label,
			"2026-07-20",
			INDIVIDUAL,
			"REF-SVC-STD",
			_net_for_gross(gross, above=above),
			"SA Standard Rated Sales",
		)
	docs["S5 capital sale"] = sales_invoice(
		"S5", "2026-08-02", VAT_CUSTOMER, "REF-CAPEX", 12000, "SA Capital Goods Sales"
	)
	# VAT-3: the locally zero-rated food item exported directly. The line overrides the
	# item's category; without a recorded reason the override is refused.
	frappe.db.savepoint("s6_negative")
	try:
		sales_invoice(
			"S6-NEG",
			"2026-08-14",
			EXPORT_CUSTOMER,
			"REF-ZR-FOOD",
			2000,
			"SA Export Zero Rated Sales",
			line_category="Export Zero Rated",
		)
		docs["S6 negative: line category changed without reason"] = "ALLOWED (unexpected)"
	except frappe.ValidationError as exc:
		frappe.db.rollback(save_point="s6_negative")
		docs["S6 negative: line category changed without reason"] = (
			f"blocked: {frappe.utils.strip_html(str(exc))[:120]}"
		)
	docs["S6 export of a local item"] = sales_invoice(
		"S6",
		"2026-08-14",
		EXPORT_CUSTOMER,
		"REF-ZR-FOOD",
		2000,
		"SA Export Zero Rated Sales",
		line_category="Export Zero Rated",
		line_category_reason="Direct export; SYNTHETIC bill of entry REF-EXP-0814",
	)
	docs["CN1 credit note"] = sales_invoice(
		"CN1",
		"2026-08-12",
		VAT_CUSTOMER,
		"REF-SVC-STD",
		2000,
		"SA Standard Rated Sales",
		is_return=1,
		return_against=docs["S1 standard full"],
		reason="SYNTHETIC: two of ten consulting days not delivered; fee reduced accordingly.",
	)
	# A credit note without the s21(3) explanation is refused on submit.
	frappe.db.savepoint("cn_negative")
	try:
		sales_invoice(
			"CN-NEG",
			"2026-08-12",
			VAT_CUSTOMER,
			"REF-SVC-STD",
			100,
			"SA Standard Rated Sales",
			is_return=1,
			return_against=docs["S1 standard full"],
		)
		docs["CN negative: no reason"] = "ALLOWED (unexpected)"
	except frappe.ValidationError as exc:
		frappe.db.rollback(save_point="cn_negative")
		docs["CN negative: no reason"] = f"blocked: {frappe.utils.strip_html(str(exc))[:120]}"
	# Purchases
	docs["P1 standard"] = purchase_invoice(
		"P1", "2026-07-04", VAT_SUPPLIER, "REF-PUR-STD", 4000, "SA Standard Rated Purchases"
	)
	docs["P2 capital"] = purchase_invoice(
		"P2", "2026-07-15", VAT_SUPPLIER, "REF-CAPEX", 60000, "SA Capital Purchases"
	)
	docs["P3 zero-rated"] = purchase_invoice(
		"P3", "2026-07-20", VAT_SUPPLIER, "REF-PUR-ZR", 1200, "SA Zero Rated Purchases"
	)
	docs["P4 exempt"] = purchase_invoice(
		"P4", "2026-07-31", VAT_SUPPLIER, "REF-PUR-EX", 350, "SA Exempt Purchases"
	)
	# Blocked input VAT (s17(2)) stays in the cost: R2,000 + R300 VAT captured gross,
	# with no input VAT template. Posting it to Input VAT is refused (VAT-8).
	frappe.db.savepoint("p5_negative")
	try:
		purchase_invoice(
			"P5-NEG",
			"2026-08-05",
			VAT_SUPPLIER,
			"REF-ENT",
			2000,
			"SA Standard Rated Purchases",
			treatment="Blocked",
			evidence="VAT Act s17(2)(a) entertainment - memo REF-17-2A",
		)
		docs["P5 negative: blocked VAT to input account"] = "ALLOWED (unexpected)"
	except frappe.ValidationError as exc:
		frappe.db.rollback(save_point="p5_negative")
		docs["P5 negative: blocked VAT to input account"] = (
			f"blocked: {frappe.utils.strip_html(str(exc))[:120]}"
		)
	docs["P5 blocked entertainment"] = purchase_invoice(
		"P5",
		"2026-08-05",
		VAT_SUPPLIER,
		"REF-ENT",
		2300,
		None,
		treatment="Blocked",
		evidence="VAT Act s17(2)(a) entertainment - memo REF-17-2A",
	)
	docs["P6 import clearing (other)"] = purchase_invoice(
		"P6", "2026-08-10", VAT_SUPPLIER, "REF-IMP-OTH", 5000, "SA Other Imports"
	)
	docs["DN1 purchase return"] = purchase_invoice(
		"DN1",
		"2026-08-14",
		VAT_SUPPLIER,
		"REF-PUR-STD",
		500,
		"SA Standard Rated Purchases",
		is_return=1,
		return_against=docs["P1 standard"],
	)
	docs["PE1 receipt S1"] = _payment_entry(
		"PE1", "Receive", "Customer", VAT_CUSTOMER, docs["S1 standard full"], "Sales Invoice", "2026-08-20"
	)
	docs["PE2 payment P1"] = _payment_entry(
		"PE2", "Pay", "Supplier", VAT_SUPPLIER, docs["P1 standard"], "Purchase Invoice", "2026-08-21"
	)
	frappe.db.commit()
	result = {
		"documents": docs,
		"usd_receivable": ar_usd,
		"readiness": readiness_report(docs),
		"gl_reconciliation": gl_reconciliation("2026-07-01", "2026-08-31"),
	}
	EVIDENCE.mkdir(parents=True, exist_ok=True)
	(EVIDENCE / "vat_transactions.json").write_text(json.dumps(result, indent=1, default=str))
	return result


def _ensure_usd_receivable():
	name = frappe.db.get_value("Account", {"company": C.COMPANY, "account_name": "Debtors USD"}, "name")
	if not name:
		parent = frappe.db.get_value(
			"Account", {"company": C.COMPANY, "account_name": "Accounts Receivable"}, "name"
		)
		name = (
			frappe.get_doc(
				{
					"doctype": "Account",
					"company": C.COMPANY,
					"account_name": "Debtors USD",
					"parent_account": parent,
					"account_type": "Receivable",
					"account_currency": "USD",
				}
			)
			.insert(ignore_permissions=True)
			.name
		)
	cust = frappe.get_doc("Customer", EXPORT_CUSTOMER)
	if not any(row.company == C.COMPANY for row in cust.accounts):
		cust.append("accounts", {"company": C.COMPANY, "account": name})
		cust.save(ignore_permissions=True)
	return name


def _payment_entry(label, payment_type, party_type, party, ref, ref_doctype, posting_date):
	if name := frappe.db.get_value("Payment Entry", {"remarks": _key(label), "docstatus": 1}, "name"):
		return name
	from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry

	ledger = account("FNB Business Cheque")
	frappe.db.set_value("Company", C.COMPANY, "default_bank_account", ledger)
	pe = get_payment_entry(ref_doctype, ref, bank_account=ledger)
	pe.posting_date = posting_date
	pe.reference_no = label
	pe.reference_date = posting_date
	pe.remarks = _key(label)
	pe.insert(ignore_permissions=True)
	pe.submit()
	return pe.name


def readiness_report(docs) -> dict:
	from za_local_core.sa_vat.tax_invoice import check_tax_invoice_readiness

	report = {}
	for label, name in docs.items():
		if not frappe.db.exists("Sales Invoice", name):
			continue
		result = check_tax_invoice_readiness(name)
		inv = frappe.db.get_value(
			"Sales Invoice",
			name,
			["base_grand_total", "grand_total", "currency", "total_taxes_and_charges"],
			as_dict=True,
		)
		report[label] = {
			"invoice": name,
			"grand_total": inv.grand_total,
			"base_grand_total": inv.base_grand_total,
			"currency": inv.currency,
			"vat": inv.total_taxes_and_charges,
			"status": result["status"],
			"invoice_type": result["invoice_type"],
			"print_format": result["recommended_print_format"],
			"missing": result["missing"],
			"threshold_basis": result["threshold_guidance"]["basis"],
			"rate_pack": result["threshold_guidance"]["statutory_rate_pack"],
		}
	return report


def gl_reconciliation(from_date, to_date) -> dict:
	"""Prove source tax rows = VAT control-account GL for the period."""
	out_acc = account("VAT Collected - Sales")
	in_accounts = [
		account(name) for name in ("VAT Paid - Purchases", "VAT Paid - Capital Goods", "VAT Paid - Imports")
	]

	def gl(acc):
		row = frappe.db.sql(
			"""select sum(credit)-sum(debit) from `tabGL Entry` where account=%s and is_cancelled=0
			and posting_date between %s and %s""",
			(acc, from_date, to_date),
		)[0][0]
		return flt(row, 2)

	def source(doctype, child, acc):
		return flt(
			frappe.db.sql(
				f"""select sum(t.base_tax_amount * if(p.is_return and p.base_net_total>0,-1,1)) from `tab{child}` t
			join `tab{doctype}` p on p.name=t.parent where p.docstatus=1 and p.company=%s and t.account_head=%s
			and p.posting_date between %s and %s""",
				(C.COMPANY, acc, from_date, to_date),
			)[0][0],
			2,
		)

	output_src = source("Sales Invoice", "Sales Taxes and Charges", out_acc)
	by_account = {
		acc: {
			"source_rows": source("Purchase Invoice", "Purchase Taxes and Charges", acc),
			"gl": -gl(acc),
		}
		for acc in in_accounts
	}
	input_src = flt(sum(v["source_rows"] for v in by_account.values()), 2)
	input_gl = flt(sum(v["gl"] for v in by_account.values()), 2)
	output_gl = gl(out_acc)
	return {
		"output_vat_source_rows": output_src,
		"output_vat_gl": output_gl,
		"output_difference": flt(output_src - output_gl, 2),
		"input_vat_source_rows": input_src,
		"input_vat_gl": input_gl,
		"input_difference": flt(input_src - input_gl, 2),
		"input_vat_by_account": by_account,
	}


def render_invoice_pdfs(docs: dict | None = None) -> list[str]:
	"""Render each Sales Invoice with its recommended SA print format for visual inspection."""
	from frappe.utils.pdf import get_pdf
	from za_local_core.sa_vat.tax_invoice import check_tax_invoice_readiness

	EVIDENCE.mkdir(parents=True, exist_ok=True)
	written = []
	names = frappe.get_all(
		"Sales Invoice",
		filters={"company": C.COMPANY, "docstatus": 1, "remarks": ["like", "REFVAT:%"]},
		fields=["name", "remarks"],
		order_by="posting_date, name",
	)
	for row in names:
		fmt = check_tax_invoice_readiness(row.name)["recommended_print_format"] or "Standard"
		html = frappe.get_print("Sales Invoice", row.name, print_format=fmt)
		path = EVIDENCE / f"{row.remarks.split(':')[1].replace(' ', '_')}_{fmt.replace(' ', '_')}.pdf"
		path.write_bytes(get_pdf(html))
		written.append(str(path))
	return written


def correct_zero_and_exempt_purchases() -> dict:
	"""Replace P3/P4, first posted with 0% input templates, with template-free invoices.

	Finding: a 0% row on the input VAT account has no VAT201 mapping and is held as
	Needs Review. The supported treatment is no tax template on zero-rated or
	exempt purchases; the item category then classifies the line with nil VAT.
	"""
	require_reference_site()
	out = {}
	for label in ("P3", "P4"):
		name = _existing("Purchase Invoice", label)
		if name:
			frappe.get_doc("Purchase Invoice", name).cancel()
			out[f"cancelled {label}"] = name
	out["P3b zero-rated (no template)"] = purchase_invoice(
		"P3b", "2026-07-20", VAT_SUPPLIER, "REF-PUR-ZR", 1200, None
	)
	out["P4b exempt (no template)"] = purchase_invoice(
		"P4b", "2026-07-31", VAT_SUPPLIER, "REF-PUR-EX", 350, None
	)
	for je in frappe.get_all(
		"Journal Entry", filters={"user_remark": "REFVAT:stale-ledger probe", "docstatus": 1}, pluck="name"
	):
		frappe.get_doc("Journal Entry", je).cancel()
		out.setdefault("cancelled probes", []).append(je)
	frappe.db.commit()
	return out
