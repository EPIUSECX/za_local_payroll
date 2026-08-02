"""Payroll-owned Custom Fields for HRMS and statutory reporting."""

from copy import deepcopy

from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

PAYROLL_CUSTOM_FIELDS = {
	"HR Settings": [
		{
			"module": "SA Payroll",
			"label": "Amount Per Kilometer",
			"fieldname": "za_amount_per_kilometer",
			"fieldtype": "Currency",
			"insert_after": "emp_created_by",
			"description": "Reimbursement rate per kilometer for mileage claims",
		}
	],
	"Payroll Settings": [
		{
			"module": "SA Payroll",
			"label": "South African Settings",
			"fieldname": "za_south_african_settings_section",
			"fieldtype": "Section Break",
			"insert_after": "daily_wages_fraction_for_half_day",
			"collapsible": 1,
		},
		{
			"module": "SA Payroll",
			"label": "Calculate Annual Taxable Amount Based On",
			"fieldname": "za_calculate_annual_taxable_amount_based_on",
			"fieldtype": "Select",
			"options": "\nJoining and Relieving Date\nPayroll Period",
			"default": "Payroll Period",
			"insert_after": "za_south_african_settings_section",
			"description": "Method for calculating annual taxable income",
		},
		{
			"module": "SA Payroll",
			"fieldname": "za_payroll_column_break",
			"fieldtype": "Column Break",
			"insert_after": "za_calculate_annual_taxable_amount_based_on",
		},
		{
			"module": "SA Payroll",
			"label": "Disable ETI Calculation",
			"fieldname": "za_disable_eti_calculation",
			"fieldtype": "Check",
			"insert_after": "za_payroll_column_break",
			"description": "Disable automatic Employment Tax Incentive calculations",
		},
		{
			"module": "SA Payroll",
			"label": "South African Statutory Components",
			"fieldname": "za_statutory_components_section",
			"fieldtype": "Section Break",
			"insert_after": "za_disable_eti_calculation",
			"collapsible": 1,
		},
		{
			"module": "SA Payroll",
			"label": "PAYE Salary Component",
			"fieldname": "za_paye_salary_component",
			"fieldtype": "Link",
			"options": "Salary Component",
			"insert_after": "za_statutory_components_section",
			"description": "Salary Component used for Pay As You Earn (PAYE) tax",
		},
		{
			"module": "SA Payroll",
			"label": "UIF Employee Salary Component",
			"fieldname": "za_uif_employee_salary_component",
			"fieldtype": "Link",
			"options": "Salary Component",
			"insert_after": "za_paye_salary_component",
			"description": "Salary Component for UIF employee contribution",
		},
		{
			"module": "SA Payroll",
			"label": "UIF Employer Salary Component",
			"fieldname": "za_uif_employer_salary_component",
			"fieldtype": "Link",
			"options": "Salary Component",
			"insert_after": "za_uif_employee_salary_component",
			"description": "Salary Component for UIF employer contribution",
		},
		{
			"module": "SA Payroll",
			"fieldname": "za_statutory_column_break",
			"fieldtype": "Column Break",
			"insert_after": "za_uif_employer_salary_component",
		},
		{
			"module": "SA Payroll",
			"label": "SDL Salary Component",
			"fieldname": "za_sdl_salary_component",
			"fieldtype": "Link",
			"options": "Salary Component",
			"insert_after": "za_statutory_column_break",
			"description": "Salary Component for Skills Development Levy (SDL)",
		},
		{
			"module": "SA Payroll",
			"label": "COIDA Salary Component",
			"fieldname": "za_coida_salary_component",
			"fieldtype": "Link",
			"options": "Salary Component",
			"insert_after": "za_sdl_salary_component",
			"description": "Salary Component for Compensation for Occupational Injuries and "
			"Diseases Act (COIDA)",
		},
		{
			"module": "SA Payroll",
			"label": "ETI Unregulated Minimum Monthly Wage",
			"fieldname": "za_eti_unregulated_minimum_monthly_wage",
			"fieldtype": "Currency",
			"insert_after": "za_disable_eti_calculation",
			"default": "2500",
			"description": "ETI Act section 4 monthly floor for an employee with 160 ordinary "
			"hours where no wage regulating measure applies or the employee is "
			"NMW-exempt. Verify after legislative changes.",
		},
		{
			"module": "SA Payroll",
			"label": "Official Interest Rate",
			"fieldname": "za_official_interest_rate",
			"fieldtype": "Percent",
			"insert_after": "za_coida_salary_component",
			"description": "Date-sensitive SARS official interest rate used for low-interest loan "
			"fringe benefits. Review whenever the repo rate changes.",
		},
	],
	"Employee": [
		{
			"module": "SA Payroll",
			"label": "South African Details",
			"fieldname": "za_south_african_details_section",
			"fieldtype": "Section Break",
			"insert_after": "passport_number",
			"collapsible": 1,
		},
		{
			"module": "SA Payroll",
			"label": "SA ID Number",
			"fieldname": "za_id_number",
			"fieldtype": "Data",
			"insert_after": "za_south_african_details_section",
			"description": "South African ID Number (13 digits)",
			"length": 13,
		},
		{
			"module": "SA Payroll",
			"label": "Employee Type",
			"fieldname": "za_employee_type",
			"fieldtype": "Link",
			"options": "Employee Type",
			"insert_after": "za_id_number",
			"description": "South African employee classification. Required during payroll processing.",
			"reqd": 0,
		},
		{
			"module": "SA Payroll",
			"label": "Special Economic Zone",
			"fieldname": "za_special_economic_zone",
			"fieldtype": "Check",
			"insert_after": "za_employee_type",
			"description": "Employee works in a Special Economic Zone (SEZ)",
		},
		{
			"module": "SA Payroll",
			"fieldname": "za_payroll_column_break",
			"fieldtype": "Column Break",
			"insert_after": "za_special_economic_zone",
		},
		{
			"module": "SA Payroll",
			"label": "Hours Per Month",
			"fieldname": "za_hours_per_month",
			"fieldtype": "Float",
			"insert_after": "za_payroll_column_break",
			"description": "Standard working hours per month for ETI calculations",
		},
		{
			"module": "SA Payroll",
			"label": "Payroll Payable Bank Account",
			"fieldname": "za_payroll_payable_bank_account",
			"fieldtype": "Link",
			"options": "Bank Account",
			"insert_after": "za_hours_per_month",
			"description": "Bank account for payroll disbursement",
		},
		{
			"module": "SA Payroll",
			"label": "Additional Information",
			"fieldname": "za_personal_information_section",
			"fieldtype": "Section Break",
			"insert_after": "za_payroll_payable_bank_account",
			"collapsible": 1,
		},
		{
			"module": "SA Payroll",
			"label": "Nationality",
			"fieldname": "za_nationality",
			"fieldtype": "Link",
			"options": "Country",
			"insert_after": "za_personal_information_section",
			"description": "Employee's nationality (for work permit tracking)",
		},
		{
			"module": "SA Payroll",
			"fieldname": "za_additional_column_break",
			"fieldtype": "Column Break",
			"insert_after": "za_nationality",
		},
		{
			"module": "SA Payroll",
			"label": "Has Other Employments",
			"fieldname": "za_has_other_employments",
			"fieldtype": "Check",
			"insert_after": "za_additional_column_break",
			"description": "Employee has multiple employers (for PAYE tax directive scenarios)",
		},
		{
			"module": "SA Payroll",
			"label": "Number of Dependants",
			"fieldname": "za_number_of_dependants",
			"fieldtype": "Int",
			"insert_after": "za_has_other_employments",
			"description": "Number of dependants for medical tax credit calculation",
		},
		{
			"module": "SA Payroll",
			"label": "South African Tax Certificate",
			"fieldname": "za_tax_certificate_section",
			"fieldtype": "Section Break",
			"insert_after": "za_number_of_dependants",
			"collapsible": 1,
		},
		{
			"module": "SA Payroll",
			"label": "Identity Type",
			"fieldname": "za_identity_type",
			"fieldtype": "Select",
			"options": "\nSouth African ID\nPassport\nAsylum Seeker\nPermit\nOther",
			"insert_after": "za_tax_certificate_section",
		},
		{
			"module": "SA Payroll",
			"label": "Income Tax Reference Number",
			"fieldname": "za_income_tax_reference_number",
			"fieldtype": "Data",
			"insert_after": "za_identity_type",
		},
		{
			"module": "SA Payroll",
			"label": "Passport Country of Issue",
			"fieldname": "za_passport_country_of_issue",
			"fieldtype": "Link",
			"options": "Country",
			"insert_after": "za_income_tax_reference_number",
		},
		{
			"module": "SA Payroll",
			"label": "Nature of Person",
			"fieldname": "za_nature_of_person",
			"fieldtype": "Select",
			"options": "\n"
			"Individual\n"
			"Director\n"
			"Trust Beneficiary\n"
			"Labour Broker\n"
			"Personal Service Provider\n"
			"Foreign Employee\n"
			"Other",
			"insert_after": "za_passport_country_of_issue",
		},
		{
			"module": "SA Payroll",
			"fieldname": "za_tax_certificate_column_break",
			"fieldtype": "Column Break",
			"insert_after": "za_nature_of_person",
		},
		{
			"module": "SA Payroll",
			"label": "Residential Address",
			"fieldname": "za_residential_address",
			"fieldtype": "Link",
			"options": "Address",
			"insert_after": "za_tax_certificate_column_break",
		},
		{
			"module": "SA Payroll",
			"label": "Postal Address",
			"fieldname": "za_postal_address",
			"fieldtype": "Link",
			"options": "Address",
			"insert_after": "za_residential_address",
		},
		{
			"module": "SA Payroll",
			"label": "Business Address Override",
			"fieldname": "za_business_address_override",
			"fieldtype": "Link",
			"options": "Address",
			"insert_after": "za_postal_address",
			"description": "Optional alternate business address for SARS certificates",
		},
		{
			"module": "SA Payroll",
			"label": "Not Paid Electronically",
			"fieldname": "za_not_paid_electronically",
			"fieldtype": "Check",
			"insert_after": "za_business_address_override",
			"description": "Tick if remuneration is not paid through electronic banking",
		},
		{
			"module": "SA Payroll",
			"label": "Bank Account for Tax Certificate",
			"fieldname": "za_tax_certificate_bank_section",
			"fieldtype": "Section Break",
			"insert_after": "za_not_paid_electronically",
			"collapsible": 1,
		},
		{
			"module": "SA Payroll",
			"label": "Bank Account Type",
			"fieldname": "za_bank_account_type",
			"fieldtype": "Select",
			"options": "\nCheque\nSavings\nTransmission\nCredit Card\nBond\nOther",
			"insert_after": "za_tax_certificate_bank_section",
		},
		{
			"module": "SA Payroll",
			"label": "Bank Account Holder Name",
			"fieldname": "za_bank_account_holder_name",
			"fieldtype": "Data",
			"insert_after": "za_bank_account_type",
		},
		{
			"module": "SA Payroll",
			"label": "Account Holder Relationship",
			"fieldname": "za_bank_account_holder_relationship",
			"fieldtype": "Select",
			"options": "\nEmployee\nSpouse\nParent\nGuardian\nTrust\nOther",
			"insert_after": "za_bank_account_holder_name",
		},
		{
			"module": "SA Payroll",
			"label": "Employment Tax Incentive Eligibility",
			"fieldname": "za_eti_eligibility_section",
			"fieldtype": "Section Break",
			"insert_after": "za_hours_per_month",
			"collapsible": 1,
		},
		{
			"module": "SA Payroll",
			"label": "Domestic Worker",
			"fieldname": "za_is_domestic_worker",
			"fieldtype": "Check",
			"insert_after": "za_eti_eligibility_section",
			"default": "0",
			"description": "Select when the employee is a domestic worker and therefore excluded from ETI.",
		},
		{
			"module": "SA Payroll",
			"label": "Connected Person to Employer",
			"fieldname": "za_is_connected_person_to_employer",
			"fieldtype": "Check",
			"insert_after": "za_is_domestic_worker",
			"default": "0",
			"description": "Select only after applying the Income Tax Act connected-person definition. "
			"Connected persons are excluded from ETI.",
		},
		{
			"module": "SA Payroll",
			"label": "ETI Minimum Wage Basis",
			"fieldname": "za_eti_minimum_wage_basis",
			"fieldtype": "Select",
			"options": "\nNational or Regulated Minimum Wage\nNo Regulating Measure or NMW Exempt",
			"insert_after": "za_is_connected_person_to_employer",
			"description": "Select the legal basis used for the employee's ETI Act section 4 wage test.",
		},
		{
			"module": "SA Payroll",
			"label": "Applicable ETI Minimum Hourly Wage",
			"fieldname": "za_eti_minimum_wage_rate",
			"fieldtype": "Currency",
			"insert_after": "za_eti_minimum_wage_basis",
			"depends_on": "eval:doc.za_eti_minimum_wage_basis=='National or Regulated Minimum Wage'",
			"mandatory_depends_on": "eval:doc.za_eti_minimum_wage_basis=='National or Regulated Minimum "
			"Wage'",
			"description": "Highest applicable hourly minimum under the NMW Act, collective agreement, "
			"sectoral determination or bargaining council agreement.",
		},
	],
	"Salary Structure": [
		{
			"module": "SA Payroll",
			"label": "Company Contribution Section",
			"fieldname": "company_contribution_section",
			"fieldtype": "Section Break",
			"insert_after": "deductions",
		},
		{
			"module": "SA Payroll",
			"label": "Company Contribution",
			"fieldname": "company_contribution",
			"fieldtype": "Table",
			"options": "Company Contribution",
			"insert_after": "company_contribution_section",
		},
	],
	"Salary Slip": [
		{
			"module": "SA Payroll",
			"label": "Company Contribution Section",
			"fieldname": "company_contribution_section",
			"fieldtype": "Section Break",
			"insert_after": "deductions",
		},
		{
			"module": "SA Payroll",
			"label": "Company Contribution",
			"fieldname": "company_contribution",
			"fieldtype": "Table",
			"options": "Company Contribution",
			"insert_after": "company_contribution_section",
		},
		{
			"module": "SA Payroll",
			"label": "Total Company Contribution",
			"fieldname": "total_company_contribution",
			"fieldtype": "Currency",
			"read_only": 1,
			"insert_after": "company_contribution",
		},
		{
			"module": "SA Payroll",
			"label": "Retirement Fund Taxable Excess",
			"fieldname": "za_retirement_fund_taxable_excess",
			"fieldtype": "Currency",
			"read_only": 1,
			"insert_after": "total_company_contribution",
			"description": "Annual retirement fund deduction amount added back to taxable remuneration "
			"after applying the South African retirement contribution cap.",
		},
		{
			"module": "SA Payroll",
			"label": "Monthly ETI",
			"fieldname": "za_monthly_eti",
			"fieldtype": "Currency",
			"insert_after": "total_deduction",
			"read_only": 1,
			"allow_on_submit": 1,
			"description": "Employment Tax Incentive calculated for this salary slip and used by EMP201.",
		},
		{
			"module": "SA Payroll",
			"label": "PAYE Inclusion Adjustment",
			"fieldname": "za_paye_inclusion_adjustment",
			"fieldtype": "Currency",
			"insert_after": "za_monthly_eti",
			"read_only": 1,
			"allow_on_submit": 1,
			"description": "Audit value for the remuneration excluded from PAYE by South African "
			"component classification.",
		},
		{
			"module": "SA Payroll",
			"label": "ETI Ordinary Hours",
			"fieldname": "za_eti_hours",
			"fieldtype": "Float",
			"insert_after": "za_paye_inclusion_adjustment",
			"description": "Actual ordinary hours employed and paid in this month for ETI gross-up, "
			"apportionment and minimum-wage testing. Unpaid leave hours must be "
			"excluded.",
		},
	],
	"Company": [
		{
			"module": "SA Payroll",
			"label": "South African Payroll Registration",
			"fieldname": "za_south_african_registration_section",
			"fieldtype": "Section Break",
			"insert_after": "tax_id",
			"collapsible": 1,
		},
		{
			"module": "SA Payroll",
			"fieldname": "za_registration_column_break",
			"fieldtype": "Column Break",
			"insert_after": "za_south_african_registration_section",
		},
		{
			"module": "SA Payroll",
			"label": "SDL Reference Number",
			"fieldname": "za_sdl_reference_number",
			"fieldtype": "Data",
			"insert_after": "za_registration_column_break",
			"description": "Skills Development Levy Reference Number",
		},
		{
			"module": "SA Payroll",
			"label": "UIF Reference Number",
			"fieldname": "za_uif_reference_number",
			"fieldtype": "Data",
			"insert_after": "za_sdl_reference_number",
			"description": "Unemployment Insurance Fund Reference Number",
		},
		{
			"module": "SA Payroll",
			"label": "PAYE Reference Number",
			"fieldname": "za_paye_reference_number",
			"fieldtype": "Data",
			"insert_after": "za_uif_reference_number",
			"description": "South African PAYE employer reference number",
		},
		{
			"module": "SA Payroll",
			"label": "Trading Name",
			"fieldname": "za_trading_name",
			"fieldtype": "Data",
			"insert_after": "za_paye_reference_number",
		},
		{
			"module": "SA Payroll",
			"label": "Business Address",
			"fieldname": "za_business_address",
			"fieldtype": "Link",
			"options": "Address",
			"insert_after": "za_trading_name",
			"description": "Structured business address for SARS certificates. Falls back to the primary "
			"company address.",
		},
	],
	"Additional Salary": [
		{
			"module": "SA Payroll",
			"label": "Is Company Contribution",
			"fieldname": "za_is_company_contribution",
			"fieldtype": "Check",
			"insert_after": "column_break_8",
			"description": "Mark as company contribution for payroll processing",
		}
	],
	"Salary Structure Assignment": [
		{
			"module": "SA Payroll",
			"label": "Annual Bonus",
			"fieldname": "za_annual_bonus",
			"fieldtype": "Currency",
			"insert_after": "base",
			"allow_on_submit": 1,
			"description": "Annual bonus amount for tax calculations",
		}
	],
	"Payroll Employee Detail": [
		{
			"module": "SA Payroll",
			"label": "Is Bank Entry Created",
			"fieldname": "za_is_bank_entry_created",
			"fieldtype": "Check",
			"insert_after": "employee_name",
			"read_only": 1,
			"description": "Indicates if bank entry has been created",
		},
		{
			"module": "SA Payroll",
			"label": "Is Company Contribution Created",
			"fieldname": "za_is_company_contribution_created",
			"fieldtype": "Check",
			"insert_after": "za_is_bank_entry_created",
			"read_only": 1,
			"description": "Indicates if company contribution entry has been created",
		},
	],
	"Journal Entry Account": [
		{
			"module": "SA Payroll",
			"label": "Is Payroll Entry",
			"fieldname": "za_is_payroll_entry",
			"fieldtype": "Check",
			"insert_after": "reference_name",
			"description": "Mark as payroll-related journal entry",
		},
		{
			"module": "SA Payroll",
			"label": "Is Company Contribution",
			"fieldname": "za_is_company_contribution",
			"fieldtype": "Check",
			"insert_after": "za_is_payroll_entry",
			"description": "Mark as company contribution entry",
		},
	],
	"Journal Entry": [
		{
			"module": "SA Payroll",
			"label": "SA Payroll Entry",
			"fieldname": "za_is_payroll_entry",
			"fieldtype": "Check",
			"insert_after": "user_remark",
			"read_only": 1,
			"hidden": 1,
			"description": "Internal marker for journal entries generated by South African payroll.",
		},
		{
			"module": "SA Payroll",
			"label": "SA Company Contribution Entry",
			"fieldname": "za_is_company_contribution",
			"fieldtype": "Check",
			"insert_after": "za_is_payroll_entry",
			"read_only": 1,
			"hidden": 1,
			"description": "Internal marker for employer-contribution accrual journal entries.",
		},
	],
	"Salary Component": [
		{
			"module": "SA Payroll",
			"label": "SARS Payroll Code",
			"fieldname": "za_sars_payroll_code",
			"fieldtype": "Link",
			"options": "SARS Payroll Code",
			"insert_after": "type",
			"description": "SARS payroll code used for IRP5 / IT3(a) certificate mapping",
		},
		{
			"module": "SA Payroll",
			"label": "Exclude from IRP5 / IT3(a)",
			"fieldname": "za_exclude_from_irp5",
			"fieldtype": "Check",
			"insert_after": "za_sars_payroll_code",
			"default": 0,
			"description": "Use only for payroll-only deductions or reimbursements that must not "
			"be reported on the employee tax certificate.",
		},
		{
			"module": "SA Payroll",
			"label": "SA Payroll Treatment",
			"fieldname": "za_payroll_treatment",
			"fieldtype": "Select",
			"options": "\n"
			"Regular Remuneration\n"
			"Annual Payment\n"
			"Overtime\n"
			"Commission\n"
			"Fixed Travel Allowance\n"
			"Reimbursive Travel\n"
			"Non-Taxable Reimbursement\n"
			"PAYE\n"
			"UIF\n"
			"SDL\n"
			"Retirement Fund\n"
			"Medical Aid\n"
			"Severance Benefit\n"
			"Leave Payout\n"
			"Notice Pay\n"
			"Working Paper Only",
			"insert_after": "za_exclude_from_irp5",
			"description": "South African payroll treatment used for PAYE, UIF, SDL, COIDA, "
			"EMP201 and IRP5 classification.",
		},
		{
			"module": "SA Payroll",
			"label": "PAYE Inclusion %",
			"fieldname": "za_paye_inclusion_percentage",
			"fieldtype": "Percent",
			"default": "100",
			"insert_after": "za_payroll_treatment",
			"description": "Percentage of this component included in PAYE remuneration. Fixed "
			"travel allowance defaults to 80%, or 20% when the statutory reduced "
			"inclusion rule applies.",
		},
		{
			"module": "SA Payroll",
			"label": "South African Statutory Bases",
			"fieldname": "za_statutory_bases_section",
			"fieldtype": "Section Break",
			"insert_after": "za_paye_inclusion_percentage",
			"collapsible": 1,
		},
		{
			"module": "SA Payroll",
			"label": "UIF Applicable",
			"fieldname": "za_uif_applicable",
			"fieldtype": "Check",
			"default": "1",
			"insert_after": "za_statutory_bases_section",
			"description": "Include this component in UIF remuneration when it is an earning.",
		},
		{
			"module": "SA Payroll",
			"label": "SDL Applicable",
			"fieldname": "za_sdl_applicable",
			"fieldtype": "Check",
			"default": "1",
			"insert_after": "za_uif_applicable",
			"description": "Include this component in SDL leviable remuneration when it is an earning.",
		},
		{
			"module": "SA Payroll",
			"label": "COIDA Applicable",
			"fieldname": "za_coida_applicable",
			"fieldtype": "Check",
			"default": "1",
			"insert_after": "za_sdl_applicable",
			"description": "Include this component in COIDA assessable earnings when it is an earning.",
		},
		{
			"module": "SA Payroll",
			"label": "Reimbursement",
			"fieldname": "za_is_reimbursement",
			"fieldtype": "Check",
			"default": "0",
			"insert_after": "za_coida_applicable",
			"description": "Marks a reimbursement or reimbursive allowance so statutory bases can "
			"exclude it where appropriate.",
		},
		{
			"module": "SA Payroll",
			"label": "Variable Pay Treatment",
			"fieldname": "za_variable_pay_treatment",
			"fieldtype": "Select",
			"options": "\nRecurring Annualised\nOnce-Off Full Tax\nManual Review",
			"default": "Recurring Annualised",
			"insert_after": "za_is_reimbursement",
			"description": "PAYE treatment for variable remuneration such as bonus, commission and overtime.",
		},
		{
			"module": "SA Payroll",
			"label": "Annual Bonus Component",
			"fieldname": "za_is_annual_bonus",
			"fieldtype": "Check",
			"insert_after": "za_variable_pay_treatment",
			"default": "0",
			"description": "Identifies the component used to pay the annual bonus configured on a "
			"Salary Structure Assignment.",
		},
		{
			"module": "SA Payroll",
			"label": "ETI Wage Component",
			"fieldname": "za_eti_wage_component",
			"fieldtype": "Check",
			"insert_after": "za_is_annual_bonus",
			"default": "0",
			"description": "Include this earning in actual wage paid for the ETI Act section 4 "
			"minimum-wage test. Do not select allowances that are remuneration but "
			"not wage.",
		},
	],
	"Address": [
		{
			"module": "SA Payroll",
			"label": "South African Address Detail",
			"fieldname": "za_south_african_address_section",
			"fieldtype": "Section Break",
			"insert_after": "pincode",
			"collapsible": 1,
		},
		{
			"module": "SA Payroll",
			"label": "Unit No",
			"fieldname": "za_unit_no",
			"fieldtype": "Data",
			"insert_after": "za_south_african_address_section",
		},
		{
			"module": "SA Payroll",
			"label": "Complex Name",
			"fieldname": "za_complex_name",
			"fieldtype": "Data",
			"insert_after": "za_unit_no",
		},
		{
			"module": "SA Payroll",
			"label": "Street No",
			"fieldname": "za_street_no",
			"fieldtype": "Data",
			"insert_after": "za_complex_name",
		},
		{
			"module": "SA Payroll",
			"label": "Suburb or District",
			"fieldname": "za_suburb_or_district",
			"fieldtype": "Data",
			"insert_after": "za_street_no",
		},
		{
			"module": "SA Payroll",
			"label": "Country Code",
			"fieldname": "za_country_code",
			"fieldtype": "Data",
			"insert_after": "za_suburb_or_district",
			"default": "ZA",
		},
		{
			"module": "SA Payroll",
			"fieldname": "za_address_column_break",
			"fieldtype": "Column Break",
			"insert_after": "za_country_code",
		},
		{
			"module": "SA Payroll",
			"label": "Postal Address Type",
			"fieldname": "za_postal_address_type",
			"fieldtype": "Select",
			"options": "\nStreet\nPO Box\nPrivate Bag\nPost Office\nCare Of\nOther",
			"insert_after": "za_address_column_break",
		},
		{
			"module": "SA Payroll",
			"label": "Care Of",
			"fieldname": "za_care_of",
			"fieldtype": "Data",
			"insert_after": "za_postal_address_type",
		},
		{
			"module": "SA Payroll",
			"label": "Postal Service Number",
			"fieldname": "za_postal_service_number",
			"fieldtype": "Data",
			"insert_after": "za_care_of",
		},
		{
			"module": "SA Payroll",
			"label": "Address Line 3",
			"fieldname": "za_address_line_3",
			"fieldtype": "Data",
			"insert_after": "za_postal_service_number",
		},
		{
			"module": "SA Payroll",
			"label": "Address Line 4",
			"fieldname": "za_address_line_4",
			"fieldtype": "Data",
			"insert_after": "za_address_line_3",
		},
	],
}


def get_payroll_custom_fields() -> dict[str, list[dict]]:
	"""Return an isolated copy so callers cannot mutate the schema definition."""
	return deepcopy(PAYROLL_CUSTOM_FIELDS)


def apply_payroll_custom_fields() -> None:
	"""Synchronize app-owned payroll schema without changing document values."""
	create_custom_fields(get_payroll_custom_fields(), update=True)
