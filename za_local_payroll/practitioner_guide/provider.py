"""Payroll pages for the federated localisation guides."""


def get_guide_sections() -> dict:
	return {
		"practitioner": [
			{
				"key": "full-suite-payroll-foundations",
				"title": "Payroll Foundations",
				"order": 30,
				"pages": _pages(
					("payroll-prerequisites-settings", "Payroll Prerequisites and Settings", "30_payroll_prerequisites_settings.md"),
					("statutory-rate-data", "Statutory Rate Data", "31_statutory_rate_data.md"),
					("sars-payroll-codes", "SARS Payroll Codes", "32_sars_payroll_codes.md"),
					("salary-components", "Salary Components", "33_salary_components.md"),
					("salary-structures", "Salary Structures", "34_salary_structures.md"),
					("retirement-and-benefits", "Retirement and Benefits", "35_retirement_and_benefits.md"),
				),
			},
			{
				"key": "full-suite-employees",
				"title": "Employees",
				"order": 35,
				"pages": _pages(("employee-master", "Employee Master", "40_employee_master.md")),
			},
			{
				"key": "full-suite-running-payroll",
				"title": "Payroll Operations",
				"order": 40,
				"pages": _pages(
					("payroll-entry-salary-slips", "Payroll Entry and Salary Slips", "50_payroll_entry.md"),
					("understanding-the-salary-slip", "Understanding the Salary Slip", "51_understanding_salary_slip.md"),
					("review-submit-post", "Review, Submit and Post", "52_review_submit_post.md"),
					("payments-and-reports", "Payments and Reports", "53_payments_and_reports.md"),
				),
			},
			{
				"key": "full-suite-statutory-submissions",
				"title": "Payroll Statutory Working Papers",
				"order": 50,
				"pages": _pages(
					("emp201", "EMP201", "60_emp201.md"),
					("irp5-it3", "IRP5 and IT3(a)", "61_irp5_it3.md"),
					("emp501", "EMP501", "62_emp501.md"),
					("directives-and-final-settlements", "Directives and Final Settlements", "63_directives_final_settlements.md"),
				),
			},
			{
				"key": "reference-operations",
				"title": "Reference and Operations",
				"order": 80,
				"pages": _pages(("annual-statutory-update", "Annual Statutory Update", "81_annual_statutory_update.md")),
			},
		],
		"user": [
			{
				"key": "running-payroll",
				"title": "Running Payroll",
				"order": 30,
				"pages": _pages(
					("monthly-payroll-run", "Run Monthly Payroll", "u30_monthly_payroll_run.md"),
					("reviewing-a-payslip", "Review a Payslip", "u31_reviewing_a_payslip.md"),
					("pay-employees", "Pay Employees", "u32_pay_employees.md"),
					("emp201-monthly", "EMP201 Monthly", "u33_emp201_monthly.md"),
					("year-end-irp5-emp501", "IRP5 and EMP501", "u34_year_end.md"),
				),
			},
			{
				"key": "reports",
				"title": "Reports",
				"order": 35,
				"pages": _pages(("payroll-reports", "Payroll Reports", "u42_payroll_reports.md")),
			},
		],
	}


def _pages(*definitions: tuple[str, str, str]) -> list[dict]:
	return [{"slug": slug, "title": title, "file": filename} for slug, title, filename in definitions]
