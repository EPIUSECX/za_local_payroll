"""Stage 6: payroll foundations, Salary Components, structures and employee personas."""

import json
from datetime import date, timedelta
from pathlib import Path

import frappe
from frappe.utils import getdate

from za_local_payroll.reference_company import constants as C
from za_local_payroll.reference_company import paths
from za_local_payroll.reference_company.foundation import ensure_address
from za_local_payroll.reference_company.guard import commit_stage, require_reference_site

HOLIDAY_LIST = "ZA Reference Working Calendar 2025-2027"
EMPLOYEE_TYPE = "ZA Reference Permanent"
SLAB_2026 = "South Africa 2026-2027"
SLAB_2025 = "South Africa 2025-2026"

# BRS v25.3.0 codes the seeded master lacks. Adding a code is practitioner
# configuration; the wrongly labelled seeded codes are a product defect (SARS-1..8).
# The app ships the BRS v25.3.0 code master; nothing extra is needed.
EXTRA_SARS_CODES = ()


def a(name: str) -> str:
	value = frappe.db.get_value(
		"Account", {"company": C.COMPANY, "account_name": name, "is_group": 0}, "name"
	)
	if not value:
		frappe.throw(f"Account {name} missing")
	return value


# name: (type, abbr, code, treatment, paye%, uif, sdl, coida, variable, extra fields, account)
COMPONENTS = {
	# Regular allowances are COIDA earnings per the 25 April 2025 Ministerial notice on
	# calculating the return of earnings (practitioner decision, recorded in the register).
	# Earnings
	"Basic": (
		"Earning",
		"B",
		"3601",
		"Regular Remuneration",
		100,
		1,
		1,
		1,
		"Recurring Annualised",
		{"za_eti_wage_component": 1},
		"Salaries and Wages",
	),
	"Hourly Wages": (
		"Earning",
		"HW",
		"3601",
		"Regular Remuneration",
		100,
		1,
		1,
		1,
		"Recurring Annualised",
		{"za_eti_wage_component": 1},
		"Salaries and Wages",
	),
	"Overtime": (
		"Earning",
		"OT",
		"3607",
		"Overtime",
		100,
		1,
		1,
		1,
		"Recurring Annualised",
		{},
		"Salaries and Wages",
	),
	"Commission": (
		"Earning",
		"COMM",
		"3606",
		"Commission",
		100,
		1,
		1,
		1,
		"Recurring Annualised",
		{},
		"Commission Expense",
	),
	"Performance Bonus": (
		"Earning",
		"PBON",
		"3605",
		"Annual Payment",
		100,
		1,
		1,
		1,
		"Once-Off Full Tax",
		{},
		"Salaries and Wages",
	),
	"13th Cheque": (
		"Earning",
		"THIR",
		"3605",
		"Annual Payment",
		100,
		1,
		1,
		1,
		"Once-Off Full Tax",
		{"za_is_annual_bonus": 1},
		"Salaries and Wages",
	),
	"Fixed Travel Allowance": (
		"Earning",
		"TRAV",
		"3701",
		"Fixed Travel Allowance",
		80,
		1,
		1,
		1,
		"Recurring Annualised",
		{},
		"Travel Allowance Expense",
	),
	"Reimbursive Travel": (
		"Earning",
		"RTRAV",
		"3703",
		"Reimbursive Travel",
		0,
		0,
		0,
		0,
		"Recurring Annualised",
		{"za_is_reimbursement": 1, "is_tax_applicable": 0},
		"Travel Allowance Expense",
	),
	"Business Expense Reimbursement": (
		"Earning",
		"BREIMB",
		"3714",
		"Non-Taxable Reimbursement",
		0,
		0,
		0,
		0,
		"Recurring Annualised",
		{"za_is_reimbursement": 1, "za_exclude_from_irp5": 1, "is_tax_applicable": 0},
		"Administrative Expenses",
	),
	"Cellphone Allowance": (
		"Earning",
		"CELL",
		"3713",
		"Regular Remuneration",
		100,
		1,
		1,
		1,
		"Recurring Annualised",
		{},
		"Salaries and Wages",
	),
	"Uniform Allowance": (
		"Earning",
		"UNIF",
		"3714",
		"Regular Remuneration",
		0,
		0,
		0,
		1,
		"Recurring Annualised",
		{"is_tax_applicable": 0},
		"Salaries and Wages",
	),
	"Leave Payout": (
		"Earning",
		"LEAVE",
		"3605",
		"Leave Payout",
		100,
		1,
		1,
		1,
		"Once-Off Full Tax",
		{},
		"Salaries and Wages",
	),
	"Notice Pay": (
		"Earning",
		"NOTICE",
		"3601",
		"Notice Pay",
		100,
		1,
		1,
		1,
		"Once-Off Full Tax",
		{},
		"Salaries and Wages",
	),
	"Severance Benefit": (
		"Earning",
		"SEV",
		"3901",
		"Severance Benefit",
		100,
		0,
		0,
		0,
		"Manual Review",
		{},
		"Salaries and Wages",
	),
	# Deductions
	"Tax on Lump Sum": (
		"Deduction",
		"LSTAX",
		"4115",
		"PAYE",
		0,
		0,
		0,
		0,
		"Recurring Annualised",
		{},
		"PAYE Payable - SARS",
	),
	"Pension Fund Employee": (
		"Deduction",
		"PFEE",
		"4001",
		"Retirement Fund",
		0,
		0,
		0,
		0,
		"Recurring Annualised",
		{},
		"Pension Fund Payable",
	),
	"Provident Fund Employee": (
		"Deduction",
		"PVEE",
		"4003",
		"Retirement Fund",
		0,
		0,
		0,
		0,
		"Recurring Annualised",
		{},
		"Provident Fund Payable",
	),
	"Retirement Annuity": (
		"Deduction",
		"RAEE",
		"4006",
		"Retirement Fund",
		0,
		0,
		0,
		0,
		"Recurring Annualised",
		{},
		"Retirement Annuity Payable",
	),
	"Medical Aid Employee": (
		"Deduction",
		"MEDEE",
		"4005",
		"Medical Aid",
		0,
		0,
		0,
		0,
		"Recurring Annualised",
		{},
		"Medical Aid Payable",
	),
	# PAY-CFG-1 fixed: a deduction excluded from the IRP5 needs no SARS code. Union dues
	# stay in Payroll Payable until paid to the union (a configuration choice).
	"Union Subscription": (
		"Deduction",
		"UNION",
		"",
		"Working Paper Only",
		0,
		0,
		0,
		0,
		"Recurring Annualised",
		{"za_exclude_from_irp5": 1},
		"Payroll Payable",
	),
	# Company contributions
	"Employer Pension Contribution": (
		"Company Contribution",
		"PFER",
		"4472",
		"Retirement Fund",
		0,
		0,
		0,
		0,
		"Recurring Annualised",
		{},
		"Pension Fund Employer Expense",
	),
}


def stage_payroll_setup() -> dict:
	require_reference_site()
	_ensure_sars_codes()
	holiday_list = _ensure_holiday_list()
	_ensure_payroll_settings()
	_ensure_employee_type()
	components = {name: _ensure_component(name, *spec) for name, spec in COMPONENTS.items()}
	from za_local_payroll.setup.masters import repair_salary_component_accounts

	repair_salary_component_accounts(C.COMPANY)
	# Employer pension accrues to the fund liability (the shipped UIF/SDL defaults are
	# seeded by the app); see ACC-1.
	frappe.db.set_value(
		"Salary Component Account",
		{"parent": "Employer Pension Contribution", "company": C.COMPANY},
		"za_liability_account",
		a("Pension Fund Payable"),
	)
	_align_seeded_components()
	from za_local_payroll.setup.masters import repair_salary_component_accounts

	repair_salary_component_accounts(C.COMPANY)
	structures = _ensure_structures()
	commit_stage()
	return {"holiday_list": holiday_list, "components": list(components), "structures": structures}


def _ensure_sars_codes():
	for code, description, category, treatment in EXTRA_SARS_CODES:
		if not frappe.db.exists("SARS Payroll Code", code):
			frappe.get_doc(
				{
					"doctype": "SARS Payroll Code",
					"code": code,
					"description": description,
					"category": category,
					"tax_treatment": treatment,
					"active": 1,
				}
			).insert(ignore_permissions=True)
		else:
			frappe.db.set_value("SARS Payroll Code", code, "tax_treatment", treatment)


def _ensure_holiday_list() -> str:
	if not frappe.db.exists("Holiday List", HOLIDAY_LIST):
		start, end = date(2025, 3, 1), date(2027, 2, 28)
		public = frappe.get_all(
			"Holiday",
			filters={
				"parent": ["like", "South Africa 20%"],
				"weekly_off": 0,
				"holiday_date": ["between", [start, end]],
			},
			fields=["holiday_date", "description"],
		)
		holidays = {getdate(h.holiday_date): h.description for h in public}
		day = start
		while day <= end:
			if day.weekday() >= 5 and day not in holidays:
				holidays[day] = "Weekly off"
			day += timedelta(days=1)
		doc = frappe.get_doc(
			{
				"doctype": "Holiday List",
				"holiday_list_name": HOLIDAY_LIST,
				"from_date": start,
				"to_date": end,
				"holidays": [
					{"holiday_date": d, "description": desc, "weekly_off": int(desc == "Weekly off")}
					for d, desc in sorted(holidays.items())
				],
			}
		)
		doc.insert(ignore_permissions=True)
	frappe.db.set_value("Company", C.COMPANY, "default_holiday_list", HOLIDAY_LIST)
	if not frappe.db.exists(
		"Holiday List Assignment", {"assigned_to": C.COMPANY, "holiday_list": HOLIDAY_LIST, "docstatus": 1}
	):
		hla = frappe.get_doc(
			{
				"doctype": "Holiday List Assignment",
				"applicable_for": "Company",
				"assigned_to": C.COMPANY,
				"holiday_list": HOLIDAY_LIST,
				"from_date": "2025-03-01",
			}
		)
		hla.insert(ignore_permissions=True)
		hla.submit()
	return HOLIDAY_LIST


def _ensure_payroll_settings():
	values = {
		"za_paye_salary_component": "PAYE",
		"za_uif_employee_salary_component": "UIF Employee Contribution",
		"za_uif_employer_salary_component": "UIF Employer Contribution",
		"za_sdl_salary_component": "SDL Contribution",
		"za_disable_eti_calculation": 0,
		"za_eti_unregulated_minimum_monthly_wage": 2500,
		"payroll_based_on": "Leave",
		"email_salary_slip_to_employee": 0,
		"process_payroll_accounting_entry_based_on_employee": 0,
		"include_holidays_in_total_working_days": 1,
	}
	for field, value in values.items():
		frappe.db.set_single_value("Payroll Settings", field, value)
	payable = a("Payroll Payable")
	frappe.db.set_value("Account", payable, "account_type", "Payable")
	frappe.db.set_value(
		"Company",
		C.COMPANY,
		{"default_payroll_payable_account": payable},
	)


def _ensure_employee_type():
	if not frappe.db.exists("Employee Type", EMPLOYEE_TYPE):
		frappe.get_doc(
			{
				"doctype": "Employee Type",
				"employee_type": EMPLOYEE_TYPE,
				"payroll_payable_account": a("Payroll Payable"),
			}
		).insert(ignore_permissions=True)


def _ensure_component(name, ctype, abbr, code, treatment, paye, uif, sdl, coida, variable, extra, account):
	values = {
		"type": ctype,
		"za_sars_payroll_code": code,
		"za_payroll_treatment": treatment,
		"za_paye_inclusion_percentage": paye,
		"za_uif_applicable": uif,
		"za_sdl_applicable": sdl,
		"za_coida_applicable": coida,
		"za_variable_pay_treatment": variable,
		"depends_on_payment_days": 1 if name in ("Basic",) else 0,
		**({"is_tax_applicable": 1} if ctype == "Earning" else {}),
		**extra,
	}
	if frappe.db.exists("Salary Component", name):
		frappe.db.set_value("Salary Component", name, values)
		doc = frappe.get_doc("Salary Component", name)
	else:
		doc = frappe.get_doc(
			{"doctype": "Salary Component", "salary_component": name, "salary_component_abbr": abbr, **values}
		)
		doc.insert(ignore_permissions=True)
	if not any(row.company == C.COMPANY for row in doc.accounts):
		doc.append("accounts", {"company": C.COMPANY, "account": a(account)})
		doc.save(ignore_permissions=True)
	return doc.name


def _align_seeded_components():
	# Seeded statutory components keep their codes; make treatment explicit.
	frappe.db.set_value("Salary Component", "PAYE", {"za_sars_payroll_code": "4102"})
	frappe.db.set_value("Salary Component", "UIF Employee Contribution", {"za_sars_payroll_code": "4141"})
	frappe.db.set_value("Salary Component", "UIF Employer Contribution", {"za_sars_payroll_code": "4141"})
	frappe.db.set_value("Salary Component", "SDL Contribution", {"za_sars_payroll_code": "4142"})


STRUCTURES = {
	# name: (frequency, earnings[(component, formula)], deductions[(component, formula)], company[(component, formula)], timesheet)
	"ZA Ref Monthly Standard": ("Monthly", [("Basic", "base")], [("PAYE", None)], [], False),
	"ZA Ref Monthly Pension": (
		"Monthly",
		[("Basic", "base")],
		[("PAYE", None), ("Pension Fund Employee", "B * 0.075")],
		[("Employer Pension Contribution", "B * 0.10")],
		False,
	),
	"ZA Ref Monthly Retirement Cap": (
		"Monthly",
		[("Basic", "base")],
		[("PAYE", None), ("Provident Fund Employee", "B * 0.20"), ("Retirement Annuity", "10000")],
		[],
		False,
	),
	"ZA Ref Monthly Medical": (
		"Monthly",
		[("Basic", "base")],
		[("PAYE", None), ("Medical Aid Employee", "variable")],
		[],
		False,
	),
	"ZA Ref Monthly Medical Employer": (
		"Monthly",
		[("Basic", "base"), ("Medical Aid Company Contribution", "2000")],
		[("PAYE", None), ("Medical Aid Employee", "variable")],
		[],
		False,
	),
	"ZA Ref Monthly Travel": (
		"Monthly",
		[("Basic", "base"), ("Fixed Travel Allowance", "variable")],
		[("PAYE", None)],
		[],
		False,
	),
	"ZA Ref Monthly Allowances": (
		"Monthly",
		[("Basic", "base"), ("Cellphone Allowance", "500"), ("Uniform Allowance", "300")],
		[("PAYE", None), ("Union Subscription", "150")],
		[],
		False,
	),
	"ZA Ref Weekly": ("Weekly", [("Basic", "base")], [("PAYE", None)], [], False),
	"ZA Ref Fortnightly": ("Fortnightly", [("Basic", "base")], [("PAYE", None)], [], False),
	"ZA Ref Hourly Timesheet": ("Monthly", [], [("PAYE", None)], [], True),
}


def _ensure_structures() -> list[str]:
	names = []
	for name, (frequency, earnings, deductions, company, timesheet) in STRUCTURES.items():
		if frappe.db.exists("Salary Structure", name):
			names.append(name)
			continue

		def row(component, formula):
			r = {
				"salary_component": component,
				"abbr": frappe.db.get_value("Salary Component", component, "salary_component_abbr"),
			}
			if formula:
				r.update({"amount_based_on_formula": 1, "formula": formula})
			return r

		doc = frappe.get_doc(
			{
				"doctype": "Salary Structure",
				"name": name,
				"__newname": name,
				"company": C.COMPANY,
				"payroll_frequency": frequency,
				"currency": "ZAR",
				"is_active": "Yes",
				"payroll_payable_account": a("Payroll Payable"),
				"earnings": [row(c, f) for c, f in earnings],
				"deductions": [row(c, f) for c, f in deductions],
				"company_contribution": [row(c, f) for c, f in company],
				"salary_slip_based_on_timesheet": int(timesheet),
				**({"salary_component": "Hourly Wages", "hour_rate": 150} if timesheet else {}),
			}
		)
		doc.insert(ignore_permissions=True)
		doc.submit()
		names.append(doc.name)
	return names


def write_config_evidence():
	paths.payroll().mkdir(parents=True, exist_ok=True)
	fields = [
		"name",
		"type",
		"salary_component_abbr",
		"za_sars_payroll_code",
		"za_payroll_treatment",
		"za_paye_inclusion_percentage",
		"za_uif_applicable",
		"za_sdl_applicable",
		"za_coida_applicable",
		"za_variable_pay_treatment",
		"za_exclude_from_irp5",
		"za_is_reimbursement",
		"za_is_annual_bonus",
		"za_eti_wage_component",
		"is_tax_applicable",
		"do_not_include_in_total",
		"do_not_include_in_accounts",
		"statistical_component",
		"depends_on_payment_days",
		"variable_based_on_taxable_salary",
		"disabled",
	]
	comps = frappe.get_all("Salary Component", fields=fields, order_by="type, name")
	for c in comps:
		c["account"] = frappe.db.get_value(
			"Salary Component Account", {"parent": c["name"], "company": C.COMPANY}, "account"
		)
	(paths.payroll() / "salary_component_matrix.json").write_text(json.dumps(comps, indent=1, default=str))
	return len(comps)
