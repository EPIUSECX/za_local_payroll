"""Stage 7: synthetic employee personas, assignments and benefit records.

Every person, ID number, tax reference and bank account here is fictional. ID
numbers are generated to pass the Luhn check so validation runs as in production.
"""

import json

import frappe
from frappe.utils import getdate

from za_local_payroll.reference_company import constants as C
from za_local_payroll.reference_company.foundation import ensure_address
from za_local_payroll.reference_company.guard import require_reference_site
from za_local_payroll.reference_company.payroll_setup import (
	EMPLOYEE_TYPE,
	EVIDENCE,
	HOLIDAY_LIST,
	SLAB_2026,
	a,
)

# key: (first, last, gender, dob, joining, structure, base, variable, hours, race, level, extra)
PERSONAS = {
	"P01_below_threshold": (
		"Thabo",
		"Below",
		"Male",
		"1990-04-10",
		"2024-03-01",
		"ZA Ref Monthly Standard",
		7500,
		0,
		173.33,
		"African",
		"Unskilled",
		{},
	),
	"P02_normal": (
		"Lerato",
		"Normal",
		"Female",
		"1988-06-15",
		"2022-01-10",
		"ZA Ref Monthly Standard",
		25000,
		0,
		173.33,
		"African",
		"Skilled Technical",
		{"salary_change": ("2026-09-01", 27500)},
	),
	"P03_high_income": (
		"Johan",
		"High",
		"Male",
		"1975-02-20",
		"2018-05-01",
		"ZA Ref Monthly Pension",
		140000,
		0,
		173.33,
		"White",
		"Top Management",
		{},
	),
	"P04_secondary_rebate": (
		"Grace",
		"Senior",
		"Female",
		"1960-05-05",
		"2015-01-01",
		"ZA Ref Monthly Standard",
		30000,
		0,
		173.33,
		"Coloured",
		"Professionally Qualified",
		{},
	),
	"P05_tertiary_rebate": (
		"Pieter",
		"Elder",
		"Male",
		"1950-01-01",
		"2010-02-01",
		"ZA Ref Monthly Standard",
		22000,
		0,
		173.33,
		"White",
		"Skilled Technical",
		{},
	),
	"P06_medical_no_dependants": (
		"Ayesha",
		"Medical",
		"Female",
		"1985-09-09",
		"2021-03-01",
		"ZA Ref Monthly Medical",
		35000,
		2500,
		173.33,
		"Indian",
		"Professionally Qualified",
		{"medical": ("2026-06-01", 2500, 0)},
	),
	"P07_medical_multi_dependants": (
		"Sipho",
		"Family",
		"Male",
		"1983-11-23",
		"2020-07-01",
		"ZA Ref Monthly Medical Employer",
		45000,
		4000,
		173.33,
		"African",
		"Senior Management",
		{"medical": ("2026-03-01", 4000, 3)},
	),
	"P08_retirement": (
		"Naledi",
		"Pension",
		"Female",
		"1987-03-30",
		"2019-04-01",
		"ZA Ref Monthly Pension",
		40000,
		0,
		173.33,
		"African",
		"Professionally Qualified",
		{},
	),
	"P09_retirement_cap": (
		"Kobus",
		"Capped",
		"Male",
		"1970-08-08",
		"2012-06-01",
		"ZA Ref Monthly Retirement Cap",
		160000,
		0,
		173.33,
		"White",
		"Top Management",
		{},
	),
	"P10_eti_eligible": (
		"Zanele",
		"Youth",
		"Female",
		"2003-06-01",
		"2026-04-01",
		"ZA Ref Monthly Standard",
		5000,
		0,
		160,
		"African",
		"Semi-Skilled",
		{"eti": "National or Regulated Minimum Wage"},
	),
	"P11_eti_age_fail": (
		"Brian",
		"Older",
		"Male",
		"1990-02-02",
		"2026-04-01",
		"ZA Ref Monthly Standard",
		5000,
		0,
		160,
		"Coloured",
		"Semi-Skilled",
		{"eti": "National or Regulated Minimum Wage"},
	),
	"P12_eti_part_time": (
		"Lindiwe",
		"Parttime",
		"Female",
		"2004-01-15",
		"2026-05-01",
		"ZA Ref Monthly Standard",
		2500,
		0,
		80,
		"African",
		"Unskilled",
		{"eti": "National or Regulated Minimum Wage"},
	),
	"P13_overtime": (
		"Kagiso",
		"Overtime",
		"Male",
		"1992-12-12",
		"2023-02-01",
		"ZA Ref Monthly Standard",
		18000,
		0,
		173.33,
		"African",
		"Skilled Technical",
		{},
	),
	"P14_commission": (
		"Megan",
		"Commission",
		"Female",
		"1991-07-07",
		"2021-08-01",
		"ZA Ref Monthly Standard",
		15000,
		0,
		173.33,
		"White",
		"Skilled Technical",
		{},
	),
	"P15_bonus": (
		"Ravi",
		"Bonus",
		"Male",
		"1986-05-19",
		"2019-09-01",
		"ZA Ref Monthly Standard",
		30000,
		0,
		173.33,
		"Indian",
		"Professionally Qualified",
		{},
	),
	"P16_travel_allowance": (
		"Andile",
		"Traveller",
		"Male",
		"1984-10-02",
		"2017-01-16",
		"ZA Ref Monthly Travel",
		38000,
		6000,
		173.33,
		"African",
		"Professionally Qualified",
		{},
	),
	"P17_reimbursive_travel": (
		"Chantal",
		"Mileage",
		"Female",
		"1989-04-04",
		"2020-02-01",
		"ZA Ref Monthly Allowances",
		28000,
		0,
		173.33,
		"Coloured",
		"Skilled Technical",
		{},
	),
	"P18_fringe_benefits": (
		"Werner",
		"Fringe",
		"Male",
		"1979-01-27",
		"2016-03-01",
		"ZA Ref Monthly Standard",
		55000,
		0,
		173.33,
		"White",
		"Senior Management",
		{"fringe": True},
	),
	"P19_termination": (
		"Nomsa",
		"Leaver",
		"Female",
		"1982-02-14",
		"2014-07-01",
		"ZA Ref Monthly Standard",
		32000,
		0,
		173.33,
		"African",
		"Skilled Technical",
		{"relieving": "2026-11-30"},
	),
	"P20_it3a_no_paye": (
		"Tumi",
		"Junior",
		"Female",
		"2000-08-20",
		"2026-06-01",
		"ZA Ref Monthly Standard",
		6500,
		0,
		173.33,
		"African",
		"Semi-Skilled",
		{},
	),
	"W01_weekly": (
		"Jacob",
		"Weekly",
		"Male",
		"1993-03-03",
		"2025-01-06",
		"ZA Ref Weekly",
		6000,
		0,
		173.33,
		"African",
		"Semi-Skilled",
		{},
	),
	"F01_fortnightly": (
		"Precious",
		"Fortnight",
		"Female",
		"1994-04-14",
		"2025-01-06",
		"ZA Ref Fortnightly",
		12000,
		0,
		173.33,
		"African",
		"Semi-Skilled",
		{},
	),
	"H01_hourly": (
		"Dylan",
		"Hourly",
		"Male",
		"1996-06-16",
		"2025-06-01",
		"ZA Ref Hourly Timesheet",
		0,
		0,
		120,
		"White",
		"Semi-Skilled",
		{},
	),
}


def sa_id(dob: str, sequence: int, gender: str) -> str:
	"""Build a synthetic 13-digit SA ID that passes the Luhn check."""
	d = getdate(dob)
	gender_seq = (5000 if gender == "Male" else 0) + sequence % 5000
	body = f"{d.year % 100:02d}{d.month:02d}{d.day:02d}{gender_seq:04d}08"
	total = 0
	for i, ch in enumerate(reversed(body)):
		n = int(ch)
		if i % 2 == 0:
			n *= 2
			n = n - 9 if n > 9 else n
		total += n
	return body + str((10 - total % 10) % 10)


def tax_reference(sequence: int) -> str:
	"""Synthetic 10-digit income tax number starting 0 with a modulus-10 check digit."""
	first9 = f"0{sequence:08d}"
	digits = [int(c) for c in first9]
	total = 0
	for i, x in enumerate(digits):
		if i % 2 == 0:
			y = x * 2
			total += y // 10 + y % 10
		else:
			total += x
	return first9 + str((10 - total % 10) % 10)


def stage_personas() -> dict:
	require_reference_site()
	_ensure_bank()
	employees = {}
	for index, (key, spec) in enumerate(PERSONAS.items(), start=1):
		employees[key] = _ensure_employee(index, key, *spec)
	frappe.db.commit()
	EVIDENCE.mkdir(parents=True, exist_ok=True)
	matrix = []
	for key, name in employees.items():
		emp = frappe.db.get_value(
			"Employee",
			name,
			[
				"name",
				"employee_name",
				"date_of_birth",
				"date_of_joining",
				"relieving_date",
				"za_id_number",
				"za_income_tax_reference_number",
				"za_hours_per_month",
				"za_eti_minimum_wage_basis",
				"za_eti_minimum_wage_rate",
				"za_race",
				"za_occupational_level",
				"gender",
			],
			as_dict=True,
		)
		ssa = frappe.get_all(
			"Salary Structure Assignment",
			filters={"employee": name, "docstatus": 1},
			fields=["salary_structure", "base", "variable", "from_date", "income_tax_slab"],
			order_by="from_date",
		)
		matrix.append({"persona": key, **emp, "assignments": ssa})
	(EVIDENCE / "employee_persona_matrix.json").write_text(json.dumps(matrix, indent=1, default=str))
	return employees


def _ensure_bank():
	for gender in ("Male", "Female"):
		if not frappe.db.exists("Gender", gender):
			frappe.get_doc({"doctype": "Gender", "gender": gender}).insert(ignore_permissions=True)
	if not frappe.db.exists("Bank Account Type", "Cheque"):
		frappe.get_doc({"doctype": "Bank Account Type", "account_type": "Cheque"}).insert(
			ignore_permissions=True
		)


def _ensure_employee(
	index, key, first, last, gender, dob, joining, structure, base, variable, hours, race, level, extra
):
	name = frappe.db.get_value("Employee", {"za_id_number": sa_id(dob, index, gender)}, "name")
	if not name:
		emp = frappe.get_doc(
			{
				"doctype": "Employee",
				"first_name": first,
				"last_name": f"{last} (Synthetic)",
				"gender": gender,
				"date_of_birth": dob,
				"date_of_joining": joining,
				"company": C.COMPANY,
				"status": "Active",
				"holiday_list": HOLIDAY_LIST,
				"department": None,
				"designation": None,
				"personal_email": f"{key.lower()}@cohenix-ref.test",
				"za_employee_type": EMPLOYEE_TYPE,
				"za_identity_type": "South African ID",
				"za_id_number": sa_id(dob, index, gender),
				"za_nationality": "South Africa",
				"za_income_tax_reference_number": tax_reference(1000 + index),
				"za_nature_of_person": "Individual",
				"za_hours_per_month": hours,
				"za_race": race,
				"za_occupational_level": level,
				"za_is_disabled": 0,
				"za_eti_minimum_wage_basis": extra.get("eti") or "National or Regulated Minimum Wage",
				"za_eti_minimum_wage_rate": 30.23,
				"za_working_hours_per_week": 40 if hours >= 160 else hours / 4.33,
			}
		).insert(ignore_permissions=True)
		name = emp.name
		addr = ensure_address(
			f"{first} {last} Residential",
			"Employee",
			name,
			address_type="Personal",
			address_line1=f"{index} Synthetic Lane",
			city="Johannesburg",
			state="Gauteng",
			pincode="2000",
		)
		bank = frappe.get_doc(
			{
				"doctype": "Bank Account",
				"account_name": f"{first} {last} Salary",
				"bank": "First National Bank",
				"account_type": "Cheque",
				"party_type": "Employee",
				"party": name,
				"bank_account_no": f"620{index:08d}",
				"branch_code": "250655",
			}
		).insert(ignore_permissions=True)
		frappe.db.set_value(
			"Employee",
			name,
			{
				"za_residential_address": addr,
				"za_postal_address": addr,
				"za_payroll_payable_bank_account": bank.name,
				"za_bank_account_type": "Cheque",
				"za_bank_account_holder_name": f"{first} {last}",
				"za_bank_account_holder_relationship": "Employee",
				"za_not_paid_electronically": 0,
			},
		)
	from_date = max(getdate(joining), getdate("2026-03-01"))
	_ensure_assignment(name, structure, base, variable, from_date)
	if change := extra.get("salary_change"):
		_ensure_assignment(name, structure, change[1], variable, getdate(change[0]))
	if medical := extra.get("medical"):
		_ensure_medical(name, *medical)
	if extra.get("fringe"):
		_ensure_fringe_benefits(name)
	return name


def _ensure_assignment(employee, structure, base, variable, from_date):
	if frappe.db.exists(
		"Salary Structure Assignment", {"employee": employee, "from_date": from_date, "docstatus": 1}
	):
		return
	doc = frappe.get_doc(
		{
			"doctype": "Salary Structure Assignment",
			"employee": employee,
			"salary_structure": structure,
			"company": C.COMPANY,
			"currency": "ZAR",
			"from_date": from_date,
			"base": base,
			"variable": variable,
			"income_tax_slab": SLAB_2026,
			"payroll_payable_account": a("Payroll Payable"),
		}
	)
	doc.insert(ignore_permissions=True)
	doc.submit()


def _ensure_medical(employee, effective_from, contribution, dependants):
	if frappe.db.exists("Employee Private Benefit", {"employee": employee, "disable": 0}):
		return
	frappe.get_doc(
		{
			"doctype": "Employee Private Benefit",
			"employee": employee,
			"effective_from": effective_from,
			"private_medical_aid": contribution,
			"medical_aid_dependant": dependants,
		}
	).insert(ignore_permissions=True)


def _ensure_fringe_benefits(employee):
	if frappe.db.exists("Fringe Benefit", {"employee": employee, "docstatus": 1}):
		return
	car = frappe.get_doc(
		{
			"doctype": "Company Car Benefit",
			"employee": employee,
			"company": C.COMPANY,
			"vehicle_registration": "SYNTH-001-GP",
			"vehicle_make_model": "Synthetic Sedan 2.0",
			"purchase_price": 450000,
			"purchase_date": "2025-01-15",
			"has_maintenance_plan": 1,
			"employee_consideration": 0,
			"private_km_per_month": 800,
			"business_km_per_month": 1200,
			"business_use_at_least_80_percent": 0,
		}
	)
	car.insert(ignore_permissions=True)
	car.submit()
	loan = frappe.get_doc(
		{
			"doctype": "Low Interest Loan Benefit",
			"employee": employee,
			"loan_start_date": "2026-03-01",
			"calculation_date": "2026-03-31",
			"loan_amount": 100000,
			"current_balance": 100000,
			"interest_rate": 2,
		}
	)
	loan.insert(ignore_permissions=True)
	loan.submit()
	for benefit_type, link_field, link in (
		("Company Car", "company_car_details", car.name),
		("Low Interest Loan", "loan_details", loan.name),
	):
		fb = frappe.get_doc(
			{
				"doctype": "Fringe Benefit",
				"employee": employee,
				"company": C.COMPANY,
				"benefit_type": benefit_type,
				"from_date": "2026-03-01",
				link_field: link,
			}
		)
		fb.insert(ignore_permissions=True)
		fb.submit()
