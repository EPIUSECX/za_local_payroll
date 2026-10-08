"""Stage 13: multi-company isolation (UK company, non-VAT South African company).

Proves ZA rules stay inside South African companies, and that a user scoped to
another company cannot read the reference company's statutory records.
"""

import json

import frappe
from frappe.utils import flt

from za_local_payroll.reference_company import constants as C
from za_local_payroll.reference_company import paths
from za_local_payroll.reference_company.governance import acting_as, user
from za_local_payroll.reference_company.guard import commit_stage, require_reference_site
from za_local_payroll.reference_company.labour import outcome

UK = "Cohenix UK Reference Ltd"
UK_ABBR = "CUKREF"
NONVAT = "Cohenix ZA Non-VAT Reference (Pty) Ltd"
NONVAT_ABBR = "CZANV"


def _company(name, abbr, country, currency):
	if not frappe.db.exists("Company", name):
		frappe.get_doc(
			{
				"doctype": "Company",
				"company_name": name,
				"abbr": abbr,
				"country": country,
				"default_currency": currency,
				"create_chart_of_accounts_based_on": "Standard Template",
				"chart_of_accounts": "Standard",
			}
		).insert(ignore_permissions=True)
		commit_stage()
	return name


def _uk_vat_setup():
	parent = frappe.db.get_value(
		"Account", {"company": UK, "account_name": "Duties and Taxes", "is_group": 1}, "name"
	)
	vat = frappe.db.get_value("Account", {"company": UK, "account_name": "UK VAT"}, "name")
	if not vat:
		vat = (
			frappe.get_doc(
				{
					"doctype": "Account",
					"account_name": "UK VAT",
					"company": UK,
					"parent_account": parent,
					"account_type": "Tax",
					"tax_rate": 20,
				}
			)
			.insert(ignore_permissions=True)
			.name
		)
	tmpl = frappe.db.get_value(
		"Sales Taxes and Charges Template", {"company": UK, "title": "UK VAT 20%"}, "name"
	)
	if not tmpl:
		tmpl = (
			frappe.get_doc(
				{
					"doctype": "Sales Taxes and Charges Template",
					"title": "UK VAT 20%",
					"company": UK,
					"taxes": [
						{
							"charge_type": "On Net Total",
							"account_head": vat,
							"description": "VAT 20%",
							"rate": 20,
						}
					],
				}
			)
			.insert(ignore_permissions=True)
			.name
		)
	item_tmpl = frappe.db.get_value("Item Tax Template", {"company": UK, "title": "UK Reduced 5%"}, "name")
	if not item_tmpl:
		item_tmpl = (
			frappe.get_doc(
				{
					"doctype": "Item Tax Template",
					"title": "UK Reduced 5%",
					"company": UK,
					"taxes": [{"tax_type": vat, "tax_rate": 5}],
				}
			)
			.insert(ignore_permissions=True)
			.name
		)
	for code, template in (("UK-STD-SERVICE", None), ("UK-REDUCED-ENERGY", item_tmpl)):
		if not frappe.db.exists("Item", code):
			frappe.get_doc(
				{
					"doctype": "Item",
					"item_code": code,
					"item_name": code,
					"item_group": "Services",
					"stock_uom": "Nos",
					"is_stock_item": 0,
					"taxes": [{"item_tax_template": template}] if template else [],
				}
			).insert(ignore_permissions=True)
	if not frappe.db.exists("Customer", "UK Reference Customer Ltd"):
		frappe.get_doc(
			{
				"doctype": "Customer",
				"customer_name": "UK Reference Customer Ltd",
				"customer_type": "Company",
				"tax_id": "GB123456789",
			}
		).insert(ignore_permissions=True)
	commit_stage()
	return vat, tmpl


def _uk_invoice(item_code, submit=False):
	vat, _tmpl = _uk_vat_setup()
	doc = frappe.get_doc(
		{
			"doctype": "Sales Invoice",
			"company": UK,
			"customer": "UK Reference Customer Ltd",
			"currency": "GBP",
			"posting_date": "2026-09-15",
			"set_posting_time": 1,
			"due_date": "2026-10-15",
			"debit_to": frappe.db.get_value("Company", UK, "default_receivable_account"),
			"items": [
				{
					"item_code": item_code,
					"qty": 1,
					"rate": 1000,
					"income_account": frappe.db.get_value("Company", UK, "default_income_account"),
					"cost_center": frappe.db.get_value("Company", UK, "cost_center"),
				}
			],
			"taxes": [
				{"charge_type": "On Net Total", "account_head": vat, "description": "VAT 20%", "rate": 20}
			],
		}
	)
	doc.insert(ignore_permissions=True)
	if submit:
		doc.submit()
	return doc


def stage_multicompany() -> dict:
	require_reference_site()
	_company(UK, UK_ABBR, "United Kingdom", "GBP")
	_company(NONVAT, NONVAT_ABBR, "South Africa", "ZAR")
	r, facts = {}, {}
	std = _uk_invoice("UK-STD-SERVICE")
	reduced = _uk_invoice("UK-REDUCED-ENERGY")
	facts["uk_standard_invoice"] = {
		"net": std.net_total,
		"tax": std.total_taxes_and_charges,
		"expected_tax": 200.0,
	}
	facts["uk_reduced_invoice"] = {
		"net": reduced.net_total,
		"tax": reduced.total_taxes_and_charges,
		"expected_tax": 50.0,
		"note": "ERPNext item tax template semantics: item rate replaces row rate",
	}
	r["uk_standard_rate_unaffected"] = {"pass": flt(std.total_taxes_and_charges) == 200.0}
	r["uk_item_tax_template_rate_applied"] = {
		"pass": flt(reduced.total_taxes_and_charges) == 50.0,
		"actual": reduced.total_taxes_and_charges,
	}
	frappe.db.rollback()

	readiness = {c: frappe.db.count("ZA Feature Readiness", {"company": c}) for c in (UK, NONVAT, C.COMPANY)}
	facts["readiness_rows"] = readiness
	facts["uk_tax_slabs"] = (
		frappe.db.count("Income Tax Slab", {"company": UK})
		if frappe.get_meta("Income Tax Slab").has_field("company")
		else None
	)

	outcome(
		r,
		"vat201_for_uk_company",
		lambda: frappe.get_doc(
			{
				"doctype": "VAT201 Return",
				"company": UK,
				"from_date": "2026-08-01",
				"to_date": "2026-09-30",
				"submission_date": "2026-09-30",
			}
		).insert(),
		True,
	)
	outcome(
		r,
		"vat201_for_non_vat_sa_company",
		lambda: frappe.get_doc(
			{
				"doctype": "VAT201 Return",
				"company": NONVAT,
				"from_date": "2026-08-01",
				"to_date": "2026-09-30",
				"submission_date": "2026-09-30",
			}
		).insert(),
		True,
	)
	outcome(
		r,
		"privacy_register_for_uk_company",
		lambda: frappe.get_doc(
			{
				"doctype": "ZA Retention Schedule",
				"company": UK,
				"record_class": "X",
				"business_owner": "X",
				"retention_trigger": "X",
				"retention_period_value": 1,
				"retention_period_unit": "Years",
				"legal_basis": "X",
				"disposal_method": "Secure Destruction",
				"disposal_instructions": "X",
				"legal_hold_process": "X",
				"effective_from": "2026-03-01",
			}
		).insert(),
		True,
	)
	outcome(
		r,
		"coida_return_for_uk_company",
		lambda: frappe.get_doc(
			{
				"doctype": "COIDA Annual Return",
				"company": UK,
				"industry_class": "9",
				"employer_category": "General Employer",
				"fiscal_year": frappe.db.get_value("Fiscal Year", {"year_start_date": "2026-03-01"}, "name"),
				"total_employees": 0,
				"total_annual_earnings": 1,
				"status": "Draft",
			}
		).insert(),
		True,
	)
	outcome(
		r,
		"ee_plan_for_uk_company",
		lambda: frappe.get_doc(
			{
				"doctype": "Employment Equity Target Plan",
				"company": UK,
				"plan_start_date": "2026-03-01",
				"plan_end_date": "2027-02-28",
				"source_basis": "Approved Employer Plan",
				"sector": "Finance and Business Services",
				"source_reference": "X",
				"small_cell_threshold": 5,
				"reviewed_by": user("reviewer"),
				"review_evidence": frappe.get_attr("za_local_payroll.reference_company.ee_skills._private")(
					"uk-ee-review.txt"
				),
				"targets": [
					{
						"effective_date": "2026-03-01",
						"occupational_level": "Top Management",
						"race": "African",
						"gender": "All",
						"disability_status": "All",
						"target_percentage": 40,
					}
				],
			}
		).insert(),
		True,
	)
	outcome(
		r,
		"uk_company_rate_pack_resolution",
		lambda: (
			frappe.get_attr("za_local_payroll.services.statutory_rates.resolve_coida_industry_rate")(
				UK, "9", "2026-09-30"
			).value
		),
		True,
	)

	# Cross-company read isolation: foreign user restricted to the UK company.
	foreign = user("foreign_accounts")
	if not frappe.db.exists("User Permission", {"user": foreign, "allow": "Company", "for_value": UK}):
		frappe.get_doc(
			{
				"doctype": "User Permission",
				"user": foreign,
				"allow": "Company",
				"for_value": UK,
				"apply_to_all_doctypes": 1,
			}
		).insert(ignore_permissions=True)
		commit_stage()
	with acting_as(foreign):
		facts["foreign_visible_sales_invoices"] = frappe.get_list(
			"Sales Invoice", filters={"company": C.COMPANY}, pluck="name"
		)
		facts["foreign_visible_purchase_invoices"] = frappe.get_list(
			"Purchase Invoice", filters={"company": C.COMPANY}, pluck="name"
		)
		facts["foreign_visible_gl"] = len(
			frappe.get_list("GL Entry", filters={"company": C.COMPANY}, pluck="name", limit=5)
		)

		def visible(doctype):
			rows = frappe.get_list(doctype, filters={"company": C.COMPANY}, pluck="name", limit=5)
			if rows:
				return rows
			raise frappe.PermissionError(f"no {doctype} rows visible")

		for doctype in (
			"VAT201 Return",
			"Salary Slip",
			"EMP201 Submission",
			"IRP5 Certificate",
			"Employee",
			"COIDA Annual Return",
			"ZA Processing Activity",
			"Workplace Injury",
		):
			outcome(
				r,
				f"foreign_user_reads_{doctype.lower().replace(' ', '_')}",
				lambda dt=doctype: visible(dt),
				True,
			)
		sinv = frappe.db.get_value("Sales Invoice", {"company": C.COMPANY, "docstatus": 1}, "name")
		outcome(
			r,
			"foreign_user_opens_za_sales_invoice",
			lambda: frappe.get_doc("Sales Invoice", sinv).check_permission("read"),
			True,
		)
	r["foreign_user_list_isolation"] = {
		"pass": not facts["foreign_visible_sales_invoices"]
		and not facts["foreign_visible_purchase_invoices"]
		and not facts["foreign_visible_gl"]
	}
	out = {"tests": r, "facts": facts}
	(paths.payroll() / "multicompany.json").write_text(json.dumps(out, indent=1, default=str))
	return out
