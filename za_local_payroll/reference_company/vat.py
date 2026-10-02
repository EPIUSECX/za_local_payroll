"""Stage 3: South African VAT configuration for the reference company."""

import frappe

from za_local_payroll.reference_company import constants as C
from za_local_payroll.reference_company.foundation import ensure_address
from za_local_payroll.reference_company.guard import require_reference_site

CONTROL_DATE = "2026-04-01"
FILING_CATEGORY = "Category B"

ITEMS = (
	# code, name, category, item_group, income/expense account name
	("REF-SVC-STD", "Consulting services (standard-rated)", "Standard Rated", "Services", "Sales"),
	(
		"REF-ZR-FOOD",
		"Brown bread (zero-rated basic foodstuff)",
		"Zero Rated",
		"Products",
		"Sales - Zero Rated",
	),
	(
		"REF-EXPORT",
		"Exported software licence (zero-rated export)",
		"Export Zero Rated",
		"Services",
		"Sales - Zero Rated",
	),
	("REF-EXEMPT", "Residential letting (exempt supply)", "Exempt", "Services", "Sales - Exempt"),
	("REF-CAPEX", "Office server (capital goods)", "Capital Goods", "Products", "Office Equipment"),
	(
		"REF-IMP-CAP",
		"Imported packaging machine (imported capital)",
		"Imported Capital Goods",
		"Products",
		"Office Equipment",
	),
	("REF-IMP-OTH", "Imported stationery (imported other goods)", "Imported Other Goods", "Products", None),
	("REF-PUR-STD", "Office supplies (standard-rated input)", "Standard Rated", "Products", None),
	("REF-PUR-ZR", "Canteen produce (zero-rated input)", "Zero Rated", "Products", None),
	("REF-PUR-EX", "Bank charges (exempt financial service)", "Exempt", "Services", None),
	("REF-ENT", "Client entertainment (blocked input)", "Standard Rated", "Services", None),
)


def account(name: str) -> str:
	value = frappe.db.get_value("Account", {"company": C.COMPANY, "account_name": name}, "name")
	if not value:
		frappe.throw(f"Reference account {name} is missing")
	return value


def stage_vat_setup() -> dict:
	require_reference_site()
	settings = _ensure_vat_settings()
	templates = _ensure_extra_templates()
	items = {code: _ensure_item(code, *rest) for code, *rest in ITEMS}
	parties = _ensure_parties()
	frappe.db.commit()
	return {"settings": settings, "templates": templates, "items": items, "parties": parties}


def _ensure_vat_settings() -> dict:
	from za_local_core.sa_vat.setup import bootstrap_company_vat_setup

	obligation = frappe.db.get_value(
		"ZA Compliance Obligation", {"obligation_code": "ZA-VAT201", "docstatus": 1}, "name"
	)
	name = frappe.db.get_value("South Africa VAT Settings", {"company": C.COMPANY}, "name")
	doc = (
		frappe.get_doc("South Africa VAT Settings", name)
		if name
		else frappe.new_doc("South Africa VAT Settings")
	)
	doc.update(
		{
			"company": C.COMPANY,
			"statutory_control_date": CONTROL_DATE,
			"vat_vendor_type": "Standard",
			"vat_filing_category": FILING_CATEGORY,
			"vat_filing_day": 25,
			"vat_registration_number": C.VAT_NUMBER,
			"output_vat_account": account("VAT Collected - Sales"),
			"input_vat_account": account("VAT Paid - Purchases"),
			# VAT-2: capital-goods and import VAT kept in their own ledgers.
			"capital_input_vat_account": account("VAT Paid - Capital Goods"),
			"import_input_vat_account": account("VAT Paid - Imports"),
			"vat201_compliance_obligation": obligation,
			"enable_zero_rated_items": 1,
			"enable_exempt_items": 1,
		}
	)
	doc.flags.ignore_permissions = True
	doc.save()
	# System Manager-only bootstrap (run as Administrator).
	feedback = bootstrap_company_vat_setup(C.COMPANY, CONTROL_DATE)
	frappe.db.commit()
	saved = frappe.get_doc("South Africa VAT Settings", doc.name)
	return {
		"name": saved.name,
		"standard_vat_rate": saved.standard_vat_rate,
		"statutory_rate_pack": saved.statutory_rate_pack,
		"statutory_source": saved.statutory_source,
		"templates": feedback.get("templates"),
		"warnings": feedback.get("warnings"),
	}


def _ensure_extra_templates() -> dict:
	"""Templates the bootstrap does not create: 0% and exempt purchases, blocked input."""
	from za_local_core.sa_vat.setup import ensure_tax_template

	input_account = account("VAT Paid - Purchases")
	return {
		"zero_purchase": ensure_tax_template(
			"Purchase Taxes and Charges Template",
			f"SA Zero Rated Purchases 0% - {C.COMPANY}",
			C.COMPANY,
			input_account,
			0,
		),
		"exempt_purchase": ensure_tax_template(
			"Purchase Taxes and Charges Template",
			f"SA Exempt Purchases 0% - {C.COMPANY}",
			C.COMPANY,
			input_account,
			0,
		),
	}


def _ensure_item(code, item_name, category, group, account_name) -> str:
	if not frappe.db.exists("Item Group", group):
		frappe.get_doc(
			{"doctype": "Item Group", "item_group_name": group, "parent_item_group": "All Item Groups"}
		).insert(ignore_permissions=True)
	if frappe.db.exists("Item", code):
		frappe.db.set_value("Item", code, "custom_sa_vat_category", category)
		return code
	doc = frappe.get_doc(
		{
			"doctype": "Item",
			"item_code": code,
			"item_name": item_name,
			"description": item_name,
			"item_group": group,
			"stock_uom": "Nos",
			"is_stock_item": 0,
			"is_sales_item": 1,
			"is_purchase_item": 1,
			"custom_sa_vat_category": category,
		}
	)
	if account_name:
		target = "income_account" if account_name.startswith("Sales") else "expense_account"
		doc.append("item_defaults", {"company": C.COMPANY, target: account(account_name)})
	doc.insert(ignore_permissions=True)
	return doc.name


def _ensure_parties() -> dict:
	parties = {}
	for name, tax_id, vendor, currency in (
		("Ref Customer VAT Vendor (Pty) Ltd", "4900000025", 1, "ZAR"),
		("Ref Customer Individual", None, 0, "ZAR"),
		("Ref Export Customer Inc", None, 0, "USD"),
	):
		if not frappe.db.exists("Customer", name):
			frappe.get_doc(
				{
					"doctype": "Customer",
					"customer_name": name,
					"customer_type": "Company" if vendor or currency != "ZAR" else "Individual",
					"customer_group": frappe.db.get_value("Customer Group", {"is_group": 0}, "name"),
					"territory": frappe.db.get_value("Territory", {"is_group": 0}, "name"),
					"tax_id": tax_id,
					"za_is_vat_vendor": vendor,
					"default_currency": currency,
				}
			).insert(ignore_permissions=True)
		parties[name] = name
	ensure_address(
		"Ref Customer VAT Vendor Address",
		"Customer",
		"Ref Customer VAT Vendor (Pty) Ltd",
		address_line1="10 Synthetic Street",
		city="Cape Town",
		state="Western Cape",
		pincode="8001",
	)
	ensure_address(
		"Ref Customer Individual Address",
		"Customer",
		"Ref Customer Individual",
		address_line1="22 Example Avenue",
		city="Durban",
		state="KwaZulu-Natal",
		pincode="4001",
	)
	for name, tax_id, currency in (
		("Ref Supplier VAT Vendor (Pty) Ltd", "4900000033", "ZAR"),
		("Ref Overseas Supplier GmbH", None, "EUR"),
	):
		if not frappe.db.exists("Supplier", name):
			frappe.get_doc(
				{
					"doctype": "Supplier",
					"supplier_name": name,
					"supplier_group": frappe.db.get_value("Supplier Group", {"is_group": 0}, "name"),
					"tax_id": tax_id,
					"default_currency": currency,
				}
			).insert(ignore_permissions=True)
		parties[name] = name
	return parties


def template(doctype: str, title_prefix: str) -> str:
	name = frappe.db.get_value(doctype, {"company": C.COMPANY, "title": ["like", f"{title_prefix}%"]}, "name")
	if not name:
		frappe.throw(f"Template {title_prefix} missing")
	return name


def vat_settings():
	return frappe.get_doc("South Africa VAT Settings", {"company": C.COMPANY})
