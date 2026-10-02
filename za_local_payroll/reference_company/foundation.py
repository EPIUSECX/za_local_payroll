"""Stage 1: ERPNext company foundation for the synthetic reference company."""

import frappe
from frappe.utils import getdate

from za_local_payroll.reference_company import constants as C
from za_local_payroll.reference_company.guard import require_reference_site

EXTRA_ACCOUNTS = (
	# (account_name, account_type, parent_account_name, root_type)
	("VAT Paid - Capital Goods", "Tax", "Tax Assets", "Asset"),
	("VAT Paid - Imports", "Tax", "Tax Assets", "Asset"),
	("Pension Fund Payable", "Payable", "Current Liabilities", "Liability"),
	("Provident Fund Payable", "Payable", "Current Liabilities", "Liability"),
	("Medical Aid Payable", "Payable", "Current Liabilities", "Liability"),
	("Retirement Annuity Payable", "Payable", "Current Liabilities", "Liability"),
	("Staff Loans Receivable", "Receivable", "Current Assets", "Asset"),
	("Employee Benefit Expense", "Expense Account", "Indirect Expenses", "Expense"),
	("Commission Expense", "Expense Account", "Indirect Expenses", "Expense"),
	("Travel Allowance Expense", "Expense Account", "Indirect Expenses", "Expense"),
	("Sales - Zero Rated", "Income Account", "Direct Income", "Income"),
	("Sales - Exempt", "Income Account", "Direct Income", "Income"),
	("Office Equipment", "Fixed Asset", "Fixed Assets", "Asset"),
)


def stage_foundation() -> dict:
	require_reference_site()
	_ensure_setup_wizard()
	_ensure_fiscal_year("2025-2026", *C.FY_2025)
	_ensure_fiscal_year("2026-2027", *C.FY_2026)
	_ensure_company_identity()

	from za_local_core.accounts.setup_chart import load_sa_chart_of_accounts

	load_sa_chart_of_accounts(C.COMPANY)
	accounts = {name: _ensure_account(name, *rest) for name, *rest in EXTRA_ACCOUNTS}
	_ensure_cost_centres()
	bank_account = _ensure_company_bank_account()
	users = _ensure_users()
	frappe.db.commit()
	return {
		"company": C.COMPANY,
		"accounts": accounts,
		"bank_account": bank_account,
		"users": users,
	}


def _ensure_setup_wizard() -> None:
	if not frappe.db.get_single_value("System Settings", "language"):
		frappe.db.set_single_value("System Settings", "language", "en")
	if not frappe.db.exists("Company", C.COMPANY):
		from erpnext.setup.setup_wizard.setup_wizard import setup_complete

		args = frappe._dict(
			{
				"fy_start_date": C.FY_2026[0],
				"fy_end_date": C.FY_2026[1],
				"company_name": C.COMPANY,
				"company_abbr": C.ABBR,
				"currency": "ZAR",
				"country": "South Africa",
				"timezone": "Africa/Johannesburg",
				"language": "en",
				"chart_of_accounts": "Standard",
				"domain": "Services",
				"bank_account": "FNB Business Cheque",
			}
		)
		setup_complete(args)
		# The Desk wizard (rebuild.sh drives it in a browser) runs every app's
		# setup_wizard_complete hook. This fallback must too, or the suite's
		# workspace metrics keep the installer's currency.
		for method in frappe.get_hooks("setup_wizard_complete"):
			frappe.get_attr(method)(args)
	frappe.db.set_value(
		"Installed Application",
		{"app_name": ["in", ["frappe", "erpnext"]]},
		"is_setup_complete",
		1,
		update_modified=False,
	)
	frappe.db.set_single_value("System Settings", "setup_complete", 1)
	frappe.db.set_single_value("System Settings", "time_zone", "Africa/Johannesburg")


def _ensure_fiscal_year(name: str, start: str, end: str) -> str:
	existing = frappe.db.get_value("Fiscal Year", {"year_start_date": start, "year_end_date": end}, "name")
	if existing:
		return existing
	doc = frappe.get_doc(
		{
			"doctype": "Fiscal Year",
			"year": name,
			"year_start_date": start,
			"year_end_date": end,
			"companies": [{"company": C.COMPANY}],
		}
	).insert(ignore_permissions=True)
	return doc.name


def _ensure_company_identity() -> None:
	address = ensure_address(
		"Cohenix Reference Head Office",
		"Company",
		C.COMPANY,
		address_line1="Unit 4, Synthetic Office Park",
		address_line2="1 Example Road",
		city="Sandton",
		state="Gauteng",
		pincode="2196",
		address_type="Billing",
		is_your_company_address=1,
	)
	frappe.db.set_value(
		"Company",
		C.COMPANY,
		{
			"tax_id": C.VAT_NUMBER,
			"za_vat_number": C.VAT_NUMBER,
			"za_trading_name": C.TRADING_NAME,
			"za_paye_reference_number": C.PAYE_REFERENCE,
			"za_sdl_reference_number": C.SDL_REFERENCE,
			"za_uif_reference_number": C.UIF_REFERENCE,
			"za_coida_registration_number": C.COIDA_REFERENCE,
			"za_income_tax_reference_number": C.INCOME_TAX_REFERENCE,
			"za_business_address": address,
			# ERPNext has no company-registration field; record it in the standard
			# free-text registration details.
			"registration_details": (
				f"CIPC registration number: {C.REGISTRATION_NUMBER}\n"
				"SYNTHETIC TEST DATA - not issued registrations"
			),
			"email": "finance@cohenix-ref.test",
			"phone_no": "+27 10 000 0000",
		},
	)


def ensure_address(title, link_doctype, link_name, **values) -> str:
	name = frappe.db.get_value("Address", {"address_title": title}, "name")
	if name:
		return name
	doc = frappe.get_doc(
		{
			"doctype": "Address",
			"address_title": title,
			"address_type": values.pop("address_type", "Billing"),
			"country": "South Africa",
			"links": [{"link_doctype": link_doctype, "link_name": link_name}],
			**values,
		}
	).insert(ignore_permissions=True)
	return doc.name


def _company_account(account_name: str) -> str | None:
	return frappe.db.get_value("Account", {"company": C.COMPANY, "account_name": account_name}, "name")


def _ensure_account(account_name, account_type, parent_name, root_type) -> str:
	existing = _company_account(account_name)
	if existing:
		return existing
	parent = _company_account(parent_name)
	if not parent:
		parent = frappe.db.get_value(
			"Account", {"company": C.COMPANY, "is_group": 1, "root_type": root_type}, "name"
		)
	doc = frappe.get_doc(
		{
			"doctype": "Account",
			"company": C.COMPANY,
			"account_name": account_name,
			"account_type": account_type,
			"parent_account": parent,
			"root_type": root_type,
			"is_group": 0,
			"account_currency": "ZAR",
		}
	).insert(ignore_permissions=True)
	return doc.name


def _ensure_cost_centres() -> None:
	root = frappe.db.get_value("Cost Center", {"company": C.COMPANY, "is_group": 1}, "name")
	for name in ("Head Office", "Operations", "Sales"):
		if not frappe.db.exists("Cost Center", f"{name} - {C.ABBR}"):
			frappe.get_doc(
				{
					"doctype": "Cost Center",
					"cost_center_name": name,
					"parent_cost_center": root,
					"company": C.COMPANY,
					"is_group": 0,
				}
			).insert(ignore_permissions=True)


def _ensure_company_bank_account() -> str:
	if not frappe.db.exists("Bank", "First National Bank"):
		frappe.get_doc(
			{"doctype": "Bank", "bank_name": "First National Bank", "swift_number": "FIRNZAJJ"}
		).insert(ignore_permissions=True)
	ledger = _company_account("FNB Business Cheque") or _ensure_account(
		"FNB Business Cheque", "Bank", "Bank Accounts", "Asset"
	)
	name = frappe.db.get_value("Bank Account", {"account": ledger, "is_company_account": 1}, "name")
	if name:
		return name
	doc = frappe.get_doc(
		{
			"doctype": "Bank Account",
			"account_name": "Reference Payroll Account",
			"bank": "First National Bank",
			"account": ledger,
			"company": C.COMPANY,
			"is_company_account": 1,
			"is_default": 1,
			# Synthetic account number; 250655 is FNB's published universal branch code.
			"bank_account_no": "62000000001",
			"branch_code": "250655",
			"account_type": None,
		}
	).insert(ignore_permissions=True)
	return doc.name


def _ensure_users() -> dict:
	created = {}
	for key, (email, full_name, roles) in C.USERS.items():
		if not frappe.db.exists("User", email):
			first, _sep, last = full_name.partition(" ")
			frappe.get_doc(
				{
					"doctype": "User",
					"email": email,
					"first_name": first,
					"last_name": last,
					"send_welcome_email": 0,
					"user_type": "System User",
					"new_password": "Reference#2026!",
				}
			).insert(ignore_permissions=True)
		user = frappe.get_doc("User", email)
		missing = [role for role in roles if role not in frappe.get_roles(email)]
		if missing:
			user.add_roles(*missing)
		created[key] = email
	return created


def fiscal_year_contains(date_value) -> bool:
	date_value = getdate(date_value)
	return bool(
		frappe.db.exists(
			"Fiscal Year", {"year_start_date": ["<=", date_value], "year_end_date": [">=", date_value]}
		)
	)
