"""
South African Salary Slip Override

This module extends the standard HRMS Salary Slip functionality to support
South African payroll requirements including PAYE, UIF, SDL, COIDA, and ETI.

Note: This module only works when HRMS is installed.
"""

from datetime import timedelta
from math import ceil

import frappe
from frappe import _
from frappe.utils import add_days, flt, getdate

from za_local_payroll.utils.hrms import get_hrms_doctype_class, require_hrms, safe_import_hrms

# Conditionally import HRMS classes
SalarySlip = get_hrms_doctype_class("hrms.payroll.doctype.salary_slip.salary_slip", "SalarySlip")

if SalarySlip is None:
	# HRMS not available - create a dummy class to prevent import errors
	class SalarySlip:
		pass


# Try to import other HRMS functions
(get_salary_component_data,) = safe_import_hrms(
	"hrms.payroll.doctype.salary_slip.salary_slip", "get_salary_component_data"
)

(get_period_factor,) = safe_import_hrms(
	"hrms.payroll.doctype.payroll_period.payroll_period", "get_period_factor"
)

if get_salary_component_data is None:

	def get_salary_component_data(*args, **kwargs):
		require_hrms("Salary Slip")
		return {}


if get_period_factor is None:

	def get_period_factor(*args, **kwargs):
		require_hrms("Salary Slip")
		return 1.0


# Import ZA Local utilities
from za_local_core.localisation import is_south_african_company

from za_local_payroll.setup.statutory import validate_current_tax_configuration
from za_local_payroll.utils.eti_utils import (
	calculate_eti_amount,
	cancel_eti_log,
	check_eti_eligibility,
	log_eti_calculation,
	submit_eti_log,
)
from za_local_payroll.utils.payroll_utils import (
	get_additional_salaries,
	get_current_block_period,
	get_employee_frequency_map,
	is_payroll_processed,
)
from za_local_payroll.utils.statutory_rates import (
	get_default_travel_paye_inclusion_percentage,
	get_retirement_annual_cap,
	get_retirement_deduction_percentage,
	get_sdl_rate,
)
from za_local_payroll.utils.tax_utils import (
	calculate_sdl_contribution,
	calculate_uif_contribution,
	get_medical_aid_credit,
	get_tax_rebate,
)

RETIREMENT_FUND_DEDUCTION_CODES = {"4001", "4003", "4006"}
# Employer retirement fund contributions: a fringe benefit of the employee that is also
# deemed paid by the employee and so counts toward the deduction cap (since 2016).
EMPLOYER_FUND_CONTRIBUTION_CODES = {"4472", "4473", "4475"}
UIF_CODES = {"4141"}
SDL_CODES = {"4142"}
PAYE_CODES = {"4102", "4115"}
# SARS employees' tax tables use whole pay periods per tax year; HRMS derives
# 52.14 weeks and 26.07 fortnights from the calendar.
SARS_PERIODS_PER_YEAR = {"Monthly": 12, "Fortnightly": 26, "Weekly": 52}
# Lump sums taxed by SARS directive, never through the annualised PAYE average.
LUMP_SUM_TREATMENTS = {"Severance Benefit"}


def sars_periods_per_year(salary_slip) -> int:
	"""Pay periods per tax year for the slip's frequency, as the SARS tables use them."""
	return SARS_PERIODS_PER_YEAR.get(getattr(salary_slip, "payroll_frequency", None) or "Monthly", 12)


class ZASalarySlip(SalarySlip):
	"""
	South African Salary Slip implementation.

	Extends the standard Salary Slip with:
	- SA tax calculations (PAYE with rebates and medical credits)
	- Employment Tax Incentive (ETI)
	- UIF, SDL, and COIDA contributions
	- Annual bonus handling
	- Company contributions
	"""

	def __init__(self, *args, **kwargs):
		"""Ensure HRMS is available before initialization"""
		if SalarySlip is None:
			require_hrms("Salary Slip")
		super().__init__(*args, **kwargs)

	@property
	def za_localisation_applies(self) -> bool:
		"""Whether South African statutory rules govern this slip's company."""
		return is_south_african_company(self.get("company"))

	def validate(self):
		"""
		Validate salary slip with SA-specific checks.
		"""
		require_hrms("Salary Slip")
		if not self.za_localisation_applies:
			return super().validate()
		if self.company and self.end_date:
			validate_current_tax_configuration(self.company, self.end_date)
		if self.is_new() and not flt(self.get("za_eti_hours")) and self.employee:
			self.za_eti_hours = flt(frappe.get_cached_value("Employee", self.employee, "za_hours_per_month"))
		super().validate()

		# Prevent duplicate salary slips for payroll frequency
		self.validate_payroll_frequency()

	def apply_sa_component_classification_defaults(self):
		"""Apply retirement and variable-pay classification once rows have been built."""
		for deduction in self.get("deductions") or []:
			if self.is_retirement_fund_component(deduction.salary_component):
				deduction.exempted_from_income_tax = 1

		for earning in self.get("earnings") or []:
			metadata = self.get_sa_component_metadata(earning.salary_component)
			if self.is_once_off_full_tax(metadata):
				earning.deduct_full_tax_on_selected_payroll_date = 1

	def is_once_off_full_tax(self, metadata):
		"""Whether a component's variable pay is taxed in full in the period it accrues.

		An annual payment is added to the annualised balance of remuneration and taxed
		in full when it accrues, rather than being spread across the year. The
		component declares this through za_variable_pay_treatment or by being
		classified as an Annual Payment.
		"""
		return (
			metadata.get("za_variable_pay_treatment") == "Once-Off Full Tax"
			or metadata.get("za_payroll_treatment") == "Annual Payment"
		)

	def add_tax_components(self):
		"""Classify populated deduction rows immediately before HRMS calculates PAYE."""
		if not self.za_localisation_applies:
			return super().add_tax_components()
		self.apply_sa_component_classification_defaults()
		return super().add_tax_components()

	def before_submit(self):
		"""
		Validate before submitting salary slip.
		"""
		# Note: Parent class (SalarySlip) doesn't have before_submit, so we don't call super()
		if not self.za_localisation_applies:
			return
		# Validate all components have accounts before allowing submission
		self.validate_component_accounts()

	def after_insert(self):
		"""Persist ETI audit evidence only after the Salary Slip link exists."""
		if not self.za_localisation_applies:
			return
		self._log_current_eti_calculation()

	def validate_payroll_frequency(self):
		"""
		Validate that salary slip doesn't duplicate an existing one for the frequency period.
		"""
		employee_frequency = get_employee_frequency_map().get(self.employee)
		if not employee_frequency:
			return

		frequency_period = get_current_block_period(self).get(employee_frequency)
		if not frequency_period:
			frappe.throw(
				_("Could not resolve the {0} payroll period for employee {1}.").format(
					frappe.bold(employee_frequency), frappe.bold(self.employee)
				),
				title=_("Payroll Frequency Configuration Error"),
			)

		if is_payroll_processed(self.employee, frequency_period, self.company):
			frappe.throw(_("Salary Slip already created for current {0}").format(employee_frequency))

	def validate_component_accounts(self):
		"""
		Ensure posting salary components have associated GL accounts.
		Required for accurate financial reporting.

		A component marked "do not include in accounts" writes no GL entry, so it
		needs no ledger. Demanding one blocks payroll over the shipped fringe
		benefits, which are all flagged that way, and invites a meaningless mapping.

		Collects all components missing accounts and provides links to configure them.
		"""
		components_missing_accounts = []

		for component_type in ["earnings", "deductions"]:
			for row in self.get(component_type):
				if frappe.db.get_value(
					"Salary Component", row.salary_component, "do_not_include_in_accounts"
				):
					continue
				if not frappe.db.exists(
					"Salary Component Account", {"parent": row.salary_component, "company": self.company}
				):
					components_missing_accounts.append(row.salary_component)

		if components_missing_accounts:
			# Remove duplicates while preserving order
			unique_components = []
			seen = set()
			for comp in components_missing_accounts:
				if comp not in seen:
					unique_components.append(comp)
					seen.add(comp)

			# Build error message with links to all components
			if len(unique_components) == 1:
				error_msg = _(
					"Salary Component <a href='/app/salary-component/{0}'>{0}</a> is missing an account configuration. "
					"Please set an account for this component in the Salary Component Account section for company {1}. "
					"Accounts are required for SA payroll compliance."
				).format(unique_components[0], self.company)
			else:
				component_links = ", ".join(
					[f"<a href='/app/salary-component/{comp}'>{comp}</a>" for comp in unique_components]
				)
				error_msg = _(
					"The following Salary Components are missing account configurations: {0}. "
					"Please set accounts for these components in their respective Salary Component Account sections for company {1}. "
					"All components must have associated accounts for SA payroll compliance."
				).format(component_links, self.company)

			frappe.throw(error_msg, title=_("Missing Salary Component Accounts"))

	def compute_taxable_earnings_for_year(self):
		"""
		Calculate annual taxable earnings including annual bonus.
		"""
		if not self.za_localisation_applies:
			return super().compute_taxable_earnings_for_year()
		super().compute_taxable_earnings_for_year()

		self.apply_sars_annual_equivalent()

		# Add annual bonus to taxable earnings
		self.annual_bonus = self.get_annual_bonus()
		self.total_taxable_earnings += self.annual_bonus

		self.apply_retirement_fund_deduction_cap()

		# Track taxable earnings without annual payments, which carry their own tax
		self.total_taxable_earnings_without_full_tax_addl_components = self.total_taxable_earnings - getattr(
			self, "za_annual_payments_to_date", 0
		)

	def get_total_sub_periods(self):
		"""Pay periods in the tax year, independent of when the employee joined."""
		if not self.payroll_period:
			return 0
		if self.payroll_frequency in SARS_PERIODS_PER_YEAR and self.payroll_period_is_full_tax_year():
			return SARS_PERIODS_PER_YEAR[self.payroll_frequency]
		return flt(
			get_period_factor(
				self.employee,
				self.start_date,
				self.end_date,
				self.payroll_frequency,
				self.payroll_period,
				joining_date=self.joining_date,
				relieving_date=self.relieving_date,
			)[0]
		)

	def payroll_period_is_full_tax_year(self) -> bool:
		start = getdate(self.payroll_period.start_date)
		end = getdate(self.payroll_period.end_date)
		return (
			start.month == 3
			and start.day == 1
			and end.month == 2
			and end == getdate(f"{start.year + 1}-03-01") - timedelta(days=1)
		)

	def get_periods_employed_to_date(self):
		"""Pay periods this employee has been paid in the tax year, including this one.

		Counted from the slips actually raised rather than from the calendar, so an
		employer that starts running payroll mid-year annualises on the periods it
		has paid instead of crediting the employee with months it never processed.
		"""
		if not self.payroll_period:
			return 1
		return (
			frappe.db.count(
				"Salary Slip",
				{
					"employee": self.employee,
					"company": self.company,
					"docstatus": 1,
					"start_date": [">=", self.payroll_period.start_date],
					"end_date": ["<", self.start_date],
				},
			)
			+ 1
		)

	def get_previous_annual_payment_earnings(self):
		"""Annual payments already taxed in earlier periods of this tax year."""
		if not self.payroll_period:
			return 0

		previous_slips = frappe.get_all(
			"Salary Slip",
			filters={
				"employee": self.employee,
				"company": self.company,
				"docstatus": 1,
				"start_date": [">=", self.payroll_period.start_date],
				"end_date": ["<", self.start_date],
			},
			pluck="name",
		)
		if not previous_slips:
			return 0

		total = 0
		for row in frappe.get_all(
			"Salary Detail",
			filters={"parent": ["in", previous_slips], "parentfield": "earnings"},
			fields=["salary_component", "amount", "is_tax_applicable"],
		):
			if not row.is_tax_applicable:
				continue
			if self.is_once_off_full_tax(self.get_sa_component_metadata(row.salary_component)):
				total += flt(row.amount)
		return total

	def apply_sars_annual_equivalent(self):
		"""Annualise the average of remuneration to date, not a forward projection.

		Paragraph 9(3) of the Fourth Schedule taxes the annual equivalent of the
		balance of remuneration, and the annual equivalent is the year-to-date
		balance divided by the periods worked and multiplied by the periods in the
		tax year. HRMS instead adds actual year-to-date earnings to a projection of
		the current period across the periods remaining, which overstates the
		equivalent whenever earnings are lumpy and then corrects it later.

		Annual payments are excluded from the average. They are not annualised: they
		are added to the annualised balance and taxed in full when they accrue.

		Two HRMS projections are removed before averaging: the future months of a
		recurring Additional Salary (the average already grosses up what was paid),
		and the non-PAYE portion of partially included earnings such as the 20% of a
		travel allowance, which is excluded where it was paid, to date.
		"""
		periods = self.get_total_sub_periods()
		elapsed = self.get_periods_employed_to_date()
		if periods <= 0 or elapsed <= 0:
			return

		annual_payments = flt(self.current_additional_earnings_with_full_tax) + flt(
			self.get_previous_annual_payment_earnings()
		)
		regular_exclusion, annual_exclusion = self.get_paye_exclusions_to_date()
		earnings_to_date = (
			flt(self.previous_taxable_earnings)
			+ flt(self.current_structured_taxable_earnings)
			+ flt(self.current_additional_earnings)
			- flt(self.get_future_recurring_projection())
			+ flt(self.other_incomes)
			+ flt(self.unclaimed_taxable_benefits)
			- flt(self.total_exemption_amount)
			- annual_payments
			- regular_exclusion
		)
		taxable_annual_payments = max(0, annual_payments - annual_exclusion)

		self.total_taxable_earnings = earnings_to_date / elapsed * periods + taxable_annual_payments
		self.za_annual_payments_to_date = taxable_annual_payments
		self.za_paye_inclusion_adjustment = flt(regular_exclusion / elapsed * periods + annual_exclusion, 2)

	def get_future_recurring_projection(self):
		"""Future months of recurring Additional Salary that HRMS adds to this period."""
		total = 0
		for row in self.get("earnings") or []:
			if (
				row.get("is_tax_applicable")
				and row.get("additional_amount")
				and row.get("is_recurring_additional_salary")
			):
				total += flt(
					self.get_future_recurring_additional_amount(row.additional_salary, row.additional_amount)
				)
		if getattr(self, "tax_slab", None) and self.tax_slab.get("allow_tax_exemption"):
			for row in self.get("deductions") or []:
				if (
					row.get("exempted_from_income_tax")
					and row.get("additional_amount")
					and row.get("is_recurring_additional_salary")
				):
					total -= flt(
						self.get_future_recurring_additional_amount(
							row.additional_salary, row.additional_amount
						)
					)
		return total

	def get_paye_exclusions_to_date(self):
		"""Non-PAYE portion of taxable earnings paid so far this tax year.

		Returns (regular, annual): the portion of averaged earnings and of annual
		payments that the component's PAYE inclusion percentage leaves out.
		"""
		rows = [
			(row.salary_component, flt(row.amount))
			for row in self.get("earnings") or []
			if row.get("is_tax_applicable") and flt(row.amount)
		]
		if self.payroll_period:
			previous_slips = frappe.get_all(
				"Salary Slip",
				filters={
					"employee": self.employee,
					"company": self.company,
					"docstatus": 1,
					"start_date": [">=", self.payroll_period.start_date],
					"end_date": ["<", self.start_date],
				},
				pluck="name",
			)
			if previous_slips:
				rows += [
					(row.salary_component, flt(row.amount))
					for row in frappe.get_all(
						"Salary Detail",
						filters={
							"parent": ["in", previous_slips],
							"parentfield": "earnings",
							"is_tax_applicable": 1,
						},
						fields=["salary_component", "amount"],
					)
				]
		regular = annual = 0.0
		for component, amount in rows:
			inclusion = self.get_component_paye_inclusion_percentage(component)
			if inclusion >= 100:
				continue
			excluded = amount * (100 - inclusion) / 100
			if self.is_once_off_full_tax(self.get_sa_component_metadata(component)):
				annual += excluded
			else:
				regular += excluded
		return flt(regular, 2), flt(annual, 2)

	def apply_retirement_fund_deduction_cap(self):
		"""Add back retirement fund contributions above the SARS deduction limit.

		HRMS reduces taxable earnings by deduction rows marked
		``exempted_from_income_tax``. The deduction is the lower of the contributions,
		27.5% of remuneration and the annual cap. Employer contributions count too: they
		are a fringe benefit of the employee (codes 3817/3825/3828) and deemed paid by
		the employee, so both the remuneration and the contributions include them. The
		benefit and its deemed deduction cancel out until the limit binds.
		"""
		if not getattr(self, "tax_slab", None) or not self.tax_slab.allow_tax_exemption:
			return

		employee_annual = self.get_annual_retirement_fund_contribution()
		employer_annual = self.get_annual_employer_fund_contribution()
		annual_contribution = employee_annual + employer_annual
		if annual_contribution <= 0:
			return

		remuneration = flt(self.total_taxable_earnings) + annual_contribution
		max_by_percentage = remuneration * get_retirement_deduction_percentage(self.end_date)
		allowed_deduction = min(
			annual_contribution, max_by_percentage, get_retirement_annual_cap(self.end_date)
		)
		disallowed_deduction = max(0, annual_contribution - allowed_deduction)
		self.za_retirement_allowed_ratio = allowed_deduction / annual_contribution

		if disallowed_deduction:
			self.total_taxable_earnings += disallowed_deduction
			self.za_retirement_fund_taxable_excess = disallowed_deduction

	def get_annual_employer_fund_contribution(self):
		"""Employer retirement fund contributions for the tax year, projected as the employee's are."""
		current = self.get_current_employer_fund_contribution()
		self.za_employer_fund_contribution = current
		previous = self.get_previous_employer_fund_contribution()
		if not current:
			return previous
		future_periods = max(ceil(flt(getattr(self, "remaining_sub_periods", 1))) - 1, 0)
		return previous + current + current * future_periods

	def get_current_employer_fund_contribution(self):
		"""This period's employer fund contributions, evaluated from the structure before the
		company contribution rows are built (they are built after PAYE)."""
		if not self.salary_structure:
			return 0
		structure = frappe.get_cached_doc("Salary Structure", self.salary_structure)
		rows = [
			row
			for row in structure.get("company_contribution") or []
			if self.get_required_sars_code(row.salary_component) in EMPLOYER_FUND_CONTRIBUTION_CODES
		]
		if not rows:
			return 0
		data = self.get_data_for_eval()
		data = data[0] if isinstance(data, tuple) else data
		return flt(sum(max(flt(self.eval_condition_and_formula(row, data)), 0) for row in rows), 2)

	def get_previous_employer_fund_contribution(self):
		if not self.payroll_period or not frappe.db.exists("DocType", "Company Contribution"):
			return 0
		previous_slips = frappe.get_all(
			"Salary Slip",
			filters={
				"employee": self.employee,
				"company": self.company,
				"docstatus": 1,
				"start_date": [">=", self.payroll_period.start_date],
				"end_date": ["<", self.start_date],
			},
			pluck="name",
		)
		if not previous_slips:
			return 0
		return flt(
			sum(
				flt(row.amount)
				for row in frappe.get_all(
					"Company Contribution",
					filters={"parent": ["in", previous_slips], "parenttype": "Salary Slip"},
					fields=["salary_component", "amount"],
				)
				if self.get_required_sars_code(row.salary_component) in EMPLOYER_FUND_CONTRIBUTION_CODES
			),
			2,
		)

	def get_current_retirement_fund_contribution(self):
		"""Total this period's retirement-fund deduction rows."""
		total = 0
		for deduction in self.get("deductions") or []:
			if not deduction.get("exempted_from_income_tax"):
				continue
			if self.is_retirement_fund_component(deduction.salary_component):
				total += flt(deduction.amount)
		return flt(total, 2)

	def get_annual_retirement_fund_contribution(self):
		"""Annualise retirement-fund deduction rows used before PAYE."""
		current_contribution = self.get_current_retirement_fund_contribution()

		if not current_contribution:
			return 0

		previous_contribution = self.get_previous_retirement_fund_contribution()
		future_periods = max(ceil(flt(getattr(self, "remaining_sub_periods", 1))) - 1, 0)
		return previous_contribution + current_contribution + (current_contribution * future_periods)

	def get_previous_retirement_fund_contribution(self):
		if not self.payroll_period:
			return 0

		previous_slips = frappe.get_all(
			"Salary Slip",
			filters={
				"employee": self.employee,
				"company": self.company,
				"docstatus": 1,
				"start_date": [">=", self.payroll_period.start_date],
				"end_date": ["<", self.start_date],
			},
			pluck="name",
		)
		if not previous_slips:
			return 0

		total = 0
		for row in frappe.get_all(
			"Salary Detail",
			filters={
				"parent": ["in", previous_slips],
				"parentfield": "deductions",
				"exempted_from_income_tax": 1,
			},
			fields=["salary_component", "amount"],
		):
			if self.is_retirement_fund_component(row.salary_component):
				total += flt(row.amount)

		return total

	def is_retirement_fund_component(self, salary_component):
		return self.get_required_sars_code(salary_component) in RETIREMENT_FUND_DEDUCTION_CODES

	def get_component_paye_inclusion_percentage(self, salary_component):
		metadata = self.get_sa_component_metadata(salary_component)
		treatment = metadata.get("za_payroll_treatment")
		value = metadata.get("za_paye_inclusion_percentage")
		if treatment in LUMP_SUM_TREATMENTS:
			# Taxed by SARS directive (code 4115), never in the annualised average.
			return 0
		if treatment and value is not None:
			return flt(value)
		if treatment == "Fixed Travel Allowance":
			return get_default_travel_paye_inclusion_percentage(self.end_date)
		if treatment in {"Reimbursive Travel", "Non-Taxable Reimbursement"}:
			return 0
		return 100

	def get_sa_component_metadata(self, salary_component):
		if not salary_component:
			return frappe._dict()

		fields = [
			"za_sars_payroll_code",
			"za_payroll_treatment",
			"za_paye_inclusion_percentage",
			"za_uif_applicable",
			"za_sdl_applicable",
			"za_coida_applicable",
			"za_is_reimbursement",
			"za_variable_pay_treatment",
			"za_exclude_from_irp5",
		]
		try:
			meta = frappe.get_meta("Salary Component")
			fields = [field for field in fields if meta.has_field(field)]
		except Exception:
			fields = ["za_sars_payroll_code"]

		if not fields:
			return frappe._dict()
		# Cached read: this metadata is fetched repeatedly per component within
		# the payroll loop, and Salary Component master data rarely changes.
		return (
			frappe.get_cached_value("Salary Component", salary_component, fields, as_dict=True)
			or frappe._dict()
		)

	def get_annual_bonus(self):
		"""
		Get annual bonus amount from Salary Structure Assignment.

		Returns:
		    float: Annual bonus amount
		"""
		annual_bonus = (
			frappe.db.get_value(
				"Salary Structure Assignment",
				{
					"employee": self.employee,
					"salary_structure": self.salary_structure,
					"docstatus": 1,
					"from_date": ("<=", self.end_date),
				},
				"za_annual_bonus",
				order_by="from_date desc",
			)
			or 0
		)

		if not annual_bonus:
			return 0

		# Check if bonus has already been paid
		bonus_component = frappe.get_all(
			"Salary Component", filters={"disabled": False, "za_is_annual_bonus": True}, pluck="name"
		)

		if not bonus_component:
			return annual_bonus

		is_bonus_paid = frappe.db.exists(
			"Additional Salary",
			{
				"docstatus": 1,
				"employee": self.employee,
				"salary_component": ["in", bonus_component],
				"company": self.company,
				"payroll_date": ["between", [self.payroll_period.start_date, self.end_date]],
			},
		)

		return 0 if is_bonus_paid else annual_bonus

	def calculate_variable_based_on_taxable_salary(self, tax_component):
		"""
		Validate prerequisites, then calculate tax using SA-specific logic with rebates/credits.

		Follows standard HRMS pattern: validates payroll_period, then calls calculate_variable_tax.
		"""
		if not self.za_localisation_applies:
			return super().calculate_variable_based_on_taxable_salary(tax_component)
		# Validate required attributes (standard HRMS validation)
		if not self.payroll_period:
			frappe.throw(
				_("Start and end dates are not in a valid Payroll Period; {0} cannot be calculated.").format(
					frappe.bold(tax_component)
				),
				title=_("Missing Payroll Period"),
			)

		# Call our overridden calculate_variable_tax (uses SA tax calculation)
		# This populates all the standard HRMS dictionary fields
		self.calculate_variable_tax(tax_component)

		# Apply SA-specific rebates and medical credits as an adjustment
		if tax_component in self._component_based_variable_tax:
			tax_rebates = self.get_tax_rebates()
			annual_tax_after_rebates = max(
				0,
				self._component_based_variable_tax[tax_component]["total_structured_tax_amount"]
				- tax_rebates,
			)
			# The medical scheme fees credit is a monthly credit for each month of
			# membership (section 6A). Credit only the months of membership up to this
			# period: annualising a part-year membership over the periods elapsed
			# over-credits the first month of membership and under-credits the rest.
			medical_credits_to_date = self.get_medical_aid_credits(up_to_date=self.end_date)
			medical_credits_before = self.get_medical_aid_credits(up_to_date=add_days(self.start_date, -1))
			# Persisted for certificate code 4116.
			self.za_medical_tax_credit = flt(medical_credits_to_date - medical_credits_before, 2)

			# The employee is liable for the share of the annual liability that the
			# periods worked so far represent, less what has already been deducted.
			# Deducting the shortfall over the periods remaining instead would
			# back-load the tax and misstate every EMP201 along the way.
			previous_total_paid_taxes = self._component_based_variable_tax[tax_component][
				"previous_total_paid_taxes"
			]
			total_sub_periods = self.get_total_sub_periods()
			elapsed = self.get_periods_employed_to_date()
			current_structured_tax_amount = 0
			if total_sub_periods > 0:
				# May be negative once an annual payment has been taxed in full: the
				# tax already deducted then runs ahead of the liability to date.
				liability_to_date = max(
					0, annual_tax_after_rebates * elapsed / total_sub_periods - medical_credits_to_date
				)
				current_structured_tax_amount = liability_to_date - previous_total_paid_taxes
			full_tax_amount = flt(
				self._component_based_variable_tax[tax_component].get("full_tax_on_additional_earnings")
			)
			current_tax_amount = max(0, current_structured_tax_amount + full_tax_amount)

			annual_tax_after_rebates = max(0, annual_tax_after_rebates - self.get_medical_aid_credits())
			self.total_structured_tax_amount = annual_tax_after_rebates
			self.current_structured_tax_amount = current_structured_tax_amount
			self.current_tax_amount = current_tax_amount
			self._component_based_variable_tax[tax_component].update(
				{
					"total_structured_tax_amount": annual_tax_after_rebates,
					"current_structured_tax_amount": current_structured_tax_amount,
					"current_tax_amount": current_tax_amount,
				}
			)
			self.apply_paye_directive(tax_component)

	def apply_paye_directive(self, tax_component):
		"""A fixed-percentage or fixed-amount directive replaces the tables' PAYE."""
		directive = self.get_active_tax_directive()
		if not directive or directive.directive_type not in {"Reduced Tax Rate", "Fixed Amount"}:
			return
		if directive.directive_type == "Fixed Amount":
			tax = flt(directive.fixed_amount, 2)
		else:
			tax = flt(self.get_period_remuneration() * flt(directive.tax_rate_override) / 100, 2)
		self.current_tax_amount = tax
		self.current_structured_tax_amount = tax
		self.za_tax_directive = directive.name
		self._component_based_variable_tax[tax_component].update(
			{
				"current_structured_tax_amount": tax,
				"current_tax_amount": tax,
				"full_tax_on_additional_earnings": 0,
			}
		)

	def get_period_remuneration(self):
		"""This period's remuneration for a directive rate: PAYE-included earnings less
		the allowable retirement deduction; lump sums carry their own directive."""
		earnings = sum(
			flt(row.amount) * self.get_component_paye_inclusion_percentage(row.salary_component) / 100
			for row in self.get("earnings") or []
			if row.get("is_tax_applicable") and flt(row.amount)
		)
		allowed_retirement = self.get_current_retirement_fund_contribution() * flt(
			getattr(self, "za_retirement_allowed_ratio", 1)
		)
		return max(0, flt(earnings - allowed_retirement, 2))

	def calculate_variable_tax(self, tax_component, has_additional_salary_tax_component=False):
		"""
		Override to use tax slab values (same as HRMS), but with SA-specific eval_locals handling.

		This uses the same tax slab calculation as standard HRMS, just avoids NoneType errors.
		"""
		if not self.za_localisation_applies:
			return super().calculate_variable_tax(tax_component, has_additional_salary_tax_component)
		# Get previous tax paid in period (standard HRMS logic)
		self.previous_total_paid_taxes = self.get_tax_paid_in_period(
			self.payroll_period.start_date, self.start_date, tax_component
		)

		# Calculate total structured tax amount using tax slab (same as HRMS)
		# Uses the same calculate_tax_by_tax_slab as standard HRMS, just ensures eval_locals is not None
		eval_locals, _default_data = self.get_data_for_eval()
		require_hrms("Salary Slip - Tax Calculation")
		try:
			from hrms.payroll.doctype.salary_slip.salary_slip import calculate_tax_by_tax_slab

			self.total_structured_tax_amount, __ = calculate_tax_by_tax_slab(
				self.total_taxable_earnings_without_full_tax_addl_components,
				self.tax_slab,
				self.whitelisted_globals,
				eval_locals if eval_locals is not None else {},  # Ensure not None
			)

			# Charge the share of the annual liability earned so far, net of tax paid
			total_sub_periods = self.get_total_sub_periods()
			elapsed = self.get_periods_employed_to_date()
			if has_additional_salary_tax_component:
				self.current_structured_tax_amount = self.additional_salary_amount
			elif total_sub_periods > 0:
				self.current_structured_tax_amount = (
					self.total_structured_tax_amount * elapsed / total_sub_periods
					- self.previous_total_paid_taxes
				)
			else:
				self.current_structured_tax_amount = 0.0

			# Tax on annual payments, carried for the rest of the year. The structured
			# liability is settled net of tax already deducted, so this has to be
			# restated in every later period, not only the one the payment fell in.
			self.full_tax_on_additional_earnings = 0.0
			if getattr(self, "za_annual_payments_to_date", 0):
				self.total_tax_amount, __ = calculate_tax_by_tax_slab(
					self.total_taxable_earnings,
					self.tax_slab,
					self.whitelisted_globals,
					eval_locals if eval_locals is not None else {},  # Ensure not None
				)
				self.full_tax_on_additional_earnings = (
					self.total_tax_amount - self.total_structured_tax_amount
				)
		except ImportError:
			frappe.throw(_("HRMS is required for tax calculations. Please install HRMS app."))

		# Calculate current tax amount (standard HRMS logic)
		self.current_tax_amount = max(
			0,
			flt(
				self.current_structured_tax_amount
				if has_additional_salary_tax_component
				else (self.current_structured_tax_amount + self.full_tax_on_additional_earnings)
			),
		)

		# Populate dictionary (standard HRMS pattern)
		self._component_based_variable_tax.setdefault(tax_component, {})
		self._component_based_variable_tax[tax_component].update(
			{
				"previous_total_paid_taxes": self.previous_total_paid_taxes,
				"total_structured_tax_amount": self.total_structured_tax_amount,
				"current_structured_tax_amount": self.current_structured_tax_amount,
				"full_tax_on_additional_earnings": self.full_tax_on_additional_earnings,
				"current_tax_amount": self.current_tax_amount,
			}
		)

	def get_tax_rebates(self):
		"""
		Calculate total tax rebates based on employee age.

		Returns:
		    float: Annual tax rebate amount
		"""
		dob = frappe.db.get_value("Employee", self.employee, "date_of_birth")
		if dob:
			return get_tax_rebate(self, dob)
		return 0

	def get_medical_aid_credits(self, up_to_date=None):
		"""
		Calculate medical aid tax credits.

		Args:
		    up_to_date: count only membership months up to this date (credit to date)

		Returns:
		    float: Medical aid credit for the tax year, or to date
		"""
		# Get active medical aid details from Employee Private Benefit. A main
		# member with zero dependants still qualifies for the main-member credit.
		benefits = frappe.get_all(
			"Employee Private Benefit",
			filters={
				"effective_from": ["<=", self.end_date],
				"disable": 0,
				"employee": self.employee,
			},
			fields=[
				"private_medical_aid",
				"medical_aid_dependant",
				"effective_from",
				"to",
			],
			order_by="effective_from desc",
		)

		employer_funded = self.has_employer_medical_aid_contribution()
		for benefit in benefits:
			if benefit.to and getdate(benefit.to) < getdate(self.start_date):
				continue
			# Membership, not who pays for it, is what the credit turns on. Section 6A
			# read with paragraph 12A of the Seventh Schedule treats an employer
			# contribution as a taxable benefit of the employee, so a wholly
			# employer-funded member is still entitled to the credit. Requiring a
			# private amount denied it to them.
			if flt(benefit.private_medical_aid) <= 0 and not employer_funded:
				continue
			kwargs = {"membership_start_date": benefit.effective_from, "membership_end_date": benefit.to}
			if up_to_date:
				kwargs["up_to_date"] = up_to_date
			return get_medical_aid_credit(self, benefit.medical_aid_dependant or 0, **kwargs)
		return 0

	def has_employer_medical_aid_contribution(self) -> bool:
		"""Whether this slip carries an employer contribution to a medical scheme."""
		for row in self.get("earnings") or []:
			if not flt(row.amount):
				continue
			metadata = self.get_sa_component_metadata(row.salary_component)
			if metadata.get("za_payroll_treatment") == "Medical Aid":
				return True
		return False

	def calculate_net_pay(self, skip_tax_breakup_computation: bool = False):
		"""
		Calculate net pay with ETI and company contributions.
		"""
		if not self.za_localisation_applies:
			return super().calculate_net_pay(skip_tax_breakup_computation)
		# Standard net pay calculation
		super().calculate_net_pay(skip_tax_breakup_computation)

		self.apply_statutory_deduction_amounts()
		self.apply_lump_sum_directive()

		# Calculate and apply ETI
		self.apply_eti()

		# Calculate company contributions
		self.calculate_company_contributions()

	def apply_eti(self):
		"""
		Calculate and apply Employment Tax Incentive.
		"""
		remuneration = self.get_statutory_earning_basis("za_uif_applicable")
		eligibility = check_eti_eligibility(self.employee, self, remuneration)

		if not eligibility["eligible"]:
			self.za_monthly_eti = 0
			if not self.is_new():
				log_eti_calculation(self.employee, self, 0, eligibility)
			return

		eti_amount = calculate_eti_amount(
			self.employee,
			self,
			remuneration,
			eligibility=eligibility,
		)

		if eti_amount <= 0:
			eligibility["eligible"] = False
			eligibility["reason"] = "No ETI is available at the employee's monthly remuneration"

		# Apply ETI to reduce PAYE
		self.za_monthly_eti = eti_amount

		if not self.is_new():
			log_eti_calculation(self.employee, self, eti_amount, eligibility)

	def _log_current_eti_calculation(self):
		remuneration = self.get_statutory_earning_basis("za_uif_applicable")
		eligibility = check_eti_eligibility(self.employee, self, remuneration)
		eti_amount = flt(self.za_monthly_eti)
		if eligibility["eligible"] and eti_amount <= 0:
			eligibility["eligible"] = False
			eligibility["reason"] = "No ETI is available at the employee's monthly remuneration"
		log_eti_calculation(self.employee, self, eti_amount, eligibility)

	def calculate_company_contributions(self):
		"""
		Calculate company contributions (UIF employer, SDL, COIDA).
		"""
		if not self.salary_structure:
			return

		salary_structure = frappe.get_doc("Salary Structure", self.salary_structure)

		# Clear existing company contributions
		self.company_contribution = []

		# Get additional company contributions
		additional_contributions = get_additional_salaries(
			self.employee, self.start_date, self.end_date, "company_contributions"
		)

		contribution_dict = {}
		data = self.get_data_for_eval()

		if isinstance(data, tuple):
			data = data[0]

		# Process salary structure company contributions
		for component in salary_structure.company_contribution:
			component.name = None
			component.amount = self.eval_condition_and_formula(component, data)

			if component.amount <= 0:
				continue

			self.append("company_contribution", component)
			contribution_dict[component.salary_component] = len(self.company_contribution) - 1

		# Add additional company contributions
		for contrib in additional_contributions:
			if contrib.component in contribution_dict:
				# Update existing
				idx = contribution_dict[contrib.component]
				self.company_contribution[idx].amount += flt(contrib.amount)
			else:
				# Add new
				self.append(
					"company_contribution",
					{"salary_component": contrib.component, "amount": flt(contrib.amount)},
				)
		# Rollup total
		self.apply_statutory_company_contribution_amounts()
		self.total_company_contribution = sum(flt(row.amount) for row in self.get("company_contribution", []))

	def apply_statutory_deduction_amounts(self):
		uif_basis = self.get_statutory_earning_basis("za_uif_applicable")
		employee_uif, _employer_uif = calculate_uif_contribution(
			uif_basis, self.end_date, sars_periods_per_year(self)
		)

		uif_rows = [
			row
			for row in self.get("deductions") or []
			if self.is_component_in_codes(row.salary_component, UIF_CODES)
		]
		if employee_uif and not uif_rows:
			component = self.get_configured_statutory_component(
				"za_uif_employee_salary_component",
				UIF_CODES,
				_("UIF Employee Contribution"),
			)
			component_data = get_salary_component_data(component)
			if not component_data:
				frappe.throw(
					_("Configured UIF employee Salary Component {0} does not exist.").format(
						frappe.bold(component)
					),
					title=_("Invalid UIF Configuration"),
				)
			self.update_component_row(
				component_data,
				flt(employee_uif, 2),
				"deductions",
				remove_if_zero_valued=False,
			)
			uif_rows = [
				row
				for row in self.get("deductions") or []
				if row.salary_component == component
				and self.is_component_in_codes(row.salary_component, UIF_CODES)
			]
			if not uif_rows:
				frappe.throw(
					_("UIF Employee Contribution could not be materialized on this Salary Slip."),
					title=_("UIF Materialization Failed"),
				)

		for row in uif_rows:
			row.amount = flt(employee_uif, 2)
			row.default_amount = row.amount
			row.depends_on_payment_days = 0

		if uif_rows:
			self.recalculate_totals_after_statutory_adjustment()

	def get_active_tax_directive(self):
		"""The submitted SARS directive covering this pay period, if any."""
		if not frappe.db.exists("DocType", "Tax Directive"):
			return None
		rows = frappe.get_all(
			"Tax Directive",
			filters={
				"employee": self.employee,
				"docstatus": 1,
				"status": ["!=", "Cancelled"],
				"effective_from": ["<=", self.end_date],
			},
			or_filters=[["effective_to", ">=", self.start_date], ["effective_to", "is", "not set"]],
			fields=["name", "directive_type", "directive_number", "fixed_amount", "tax_rate_override"],
			order_by="effective_from desc",
			limit=1,
		)
		return rows[0] if rows else None

	def get_lump_sum_earnings(self):
		return flt(
			sum(
				flt(row.amount)
				for row in self.get("earnings") or []
				if self.get_sa_component_metadata(row.salary_component).get("za_payroll_treatment")
				in LUMP_SUM_TREATMENTS
			),
			2,
		)

	def apply_lump_sum_directive(self):
		"""Deduct the directive tax on a lump sum (code 4115); refuse a lump sum without one.

		A severance benefit is taxed on the lump-sum table by SARS, which issues the
		tax as a directive. It never enters the annualised PAYE average (its PAYE
		inclusion is nil); the employer deducts exactly the directive amount.
		"""
		lump_sum = self.get_lump_sum_earnings()
		if not lump_sum:
			return
		directive = self.get_active_tax_directive()
		if not directive or directive.directive_type != "Severance / Lump Sum":
			frappe.throw(
				_(
					"Employee {0} receives a lump sum of {1} on this slip but has no submitted "
					"Severance / Lump Sum Tax Directive covering {2} to {3}. Apply to SARS for the "
					"directive and capture it before processing the lump sum."
				).format(frappe.bold(self.employee), lump_sum, self.start_date, self.end_date),
				title=_("Tax Directive Required"),
			)
		component = self.get_configured_statutory_component(
			"za_lump_sum_tax_salary_component", {"4115"}, _("Tax on Lump Sum")
		)
		amount = flt(directive.fixed_amount, 2)
		rows = [row for row in self.get("deductions") or [] if row.salary_component == component]
		if not rows and amount:
			component_data = get_salary_component_data(component)
			self.update_component_row(component_data, amount, "deductions", remove_if_zero_valued=False)
			rows = [row for row in self.get("deductions") or [] if row.salary_component == component]
		for row in rows:
			row.amount = amount
			row.default_amount = amount
			row.depends_on_payment_days = 0
		self.za_tax_directive = directive.name
		self.recalculate_totals_after_statutory_adjustment()

	def get_configured_statutory_component(self, settings_field, codes, label):
		component = frappe.db.get_single_value("Payroll Settings", settings_field)
		if component:
			metadata = self.get_sa_component_metadata(component)
			if self.get_required_sars_code(component, metadata) not in codes:
				frappe.throw(
					_("{0} is mapped to an incompatible SARS Payroll Code.").format(frappe.bold(component)),
					title=_("Invalid Statutory Component Configuration"),
				)
			return component

		matches = frappe.get_all(
			"Salary Component",
			filters={"disabled": 0, "za_sars_payroll_code": ["in", sorted(codes)]},
			pluck="name",
			limit=2,
		)
		if len(matches) == 1:
			return matches[0]

		frappe.throw(
			_("Configure exactly one {0} in Payroll Settings.").format(label),
			title=_("Missing Statutory Component Configuration"),
		)

	def apply_statutory_company_contribution_amounts(self):
		uif_basis = self.get_statutory_earning_basis("za_uif_applicable")
		sdl_basis = self.get_sdl_leviable_amount()
		_employee_uif, employer_uif = calculate_uif_contribution(
			uif_basis, self.end_date, sars_periods_per_year(self)
		)
		sdl = sdl_basis * get_sdl_rate(self.end_date)

		configured = (
			(
				employer_uif,
				"za_uif_employer_salary_component",
				UIF_CODES,
				_("UIF Employer Contribution"),
			),
			(sdl, "za_sdl_salary_component", SDL_CODES, _("SDL Contribution")),
		)
		for amount, settings_field, codes, label in configured:
			if not amount or any(
				self.is_component_in_codes(row.salary_component, codes)
				for row in self.get("company_contribution") or []
			):
				continue
			self.append(
				"company_contribution",
				{
					"salary_component": self.get_configured_statutory_component(settings_field, codes, label),
					"amount": flt(amount, 2),
					"default_amount": flt(amount, 2),
					"depends_on_payment_days": 0,
				},
			)

		for row in self.get("company_contribution") or []:
			if self.is_component_in_codes(row.salary_component, UIF_CODES):
				row.amount = flt(employer_uif, 2)
				row.default_amount = row.amount
				row.depends_on_payment_days = 0
			elif self.is_component_in_codes(row.salary_component, SDL_CODES):
				row.amount = flt(sdl, 2)
				row.default_amount = row.amount
				row.depends_on_payment_days = 0

	def get_sdl_leviable_amount(self):
		"""SDL leviable amount: the balance of remuneration for employees' tax.

		Section 3(4) of the Skills Development Levies Act sets the leviable amount by
		reference to the Fourth Schedule as applied in determining employees' tax.
		SARS's employer guide: "SDL is therefore determined on the balance of
		remuneration after the deduction of all allowable deductions". So earnings
		count at their PAYE inclusion (80% of a travel allowance or company car), and
		only the allowable retirement fund deduction (after the 27.5% / annual cap)
		reduces the levy. UIF is deliberately left on remuneration: the Unemployment
		Insurance Contributions Act defines its own base.
		"""
		leviable = self.get_statutory_earning_basis("za_sdl_applicable", apply_paye_inclusion=True)
		allowed_ratio = flt(getattr(self, "za_retirement_allowed_ratio", 1))
		employer_fund = flt(getattr(self, "za_employer_fund_contribution", 0))
		# The employer contribution is remuneration (a fringe benefit) and, being deemed
		# paid by the employee, part of the allowable deduction: net, only its
		# disallowed share is levied.
		allowed_retirement = (self.get_current_retirement_fund_contribution() + employer_fund) * allowed_ratio
		return flt(max(leviable + employer_fund - allowed_retirement, 0), 2)

	def get_statutory_earning_basis(self, applicability_field, apply_paye_inclusion=False):
		"""Total the earnings the given statutory levy applies to.

		``do_not_include_in_total`` is deliberately not a reason to skip a row. It
		keeps a component out of gross and net pay, which is right for a fringe
		benefit, but the SDL and UIF leviable amounts are remuneration under the
		Fourth Schedule, and paragraph 1 of that Schedule includes the cash
		equivalent of Seventh Schedule taxable benefits. Skipping those rows
		silently ignored ``za_sdl_applicable`` and under-declared the levy.

		The per-component flag is therefore the only thing that decides.
		"""
		total = 0
		for row in self.get("earnings") or []:
			if not flt(row.amount) or row.get("statistical_component"):
				continue
			metadata = self.get_sa_component_metadata(row.salary_component)
			self.get_required_sars_code(row.salary_component, metadata)
			if applicability_field not in metadata:
				frappe.throw(
					_("Salary Component {0} is missing the {1} classification field.").format(
						frappe.bold(row.salary_component), frappe.bold(applicability_field)
					),
					title=_("Incomplete SARS Payroll Classification"),
				)
			treatment = metadata.get("za_payroll_treatment")
			if treatment in {"Reimbursive Travel", "Non-Taxable Reimbursement", "Working Paper Only"}:
				continue
			if metadata.get("za_is_reimbursement"):
				continue
			if metadata.get(applicability_field) in (0, "0", False, None, ""):
				continue
			if apply_paye_inclusion:
				total += (
					flt(row.amount) * self.get_component_paye_inclusion_percentage(row.salary_component) / 100
				)
			else:
				total += flt(row.amount)
		return flt(total, 2)

	def is_component_in_codes(self, salary_component, codes):
		metadata = self.get_sa_component_metadata(salary_component)
		return self.get_required_sars_code(salary_component, metadata) in codes

	def get_required_sars_code(self, salary_component, metadata=None):
		metadata = metadata or self.get_sa_component_metadata(salary_component)
		code = metadata.get("za_sars_payroll_code")
		if code:
			return code
		# A component kept off the IRP5 (for example a union subscription the employer
		# only collects) has no SARS source code to carry.
		if (
			metadata.get("za_exclude_from_irp5")
			or metadata.get("za_payroll_treatment") == "Working Paper Only"
		):
			return ""

		frappe.throw(
			_("Salary Component {0} must have a SARS Payroll Code before payroll can be calculated.").format(
				frappe.bold(salary_component)
			),
			title=_("Missing SARS Payroll Classification"),
		)

	def recalculate_totals_after_statutory_adjustment(self):
		self.set_net_pay()

	def add_additional_salary_components(self, component_type):
		"""Add earning or deduction Additional Salaries to the slip.

		Company contributions are partitioned out upstream by
		payroll_utils.get_additional_salaries, which routes them to
		calculate_company_contributions instead.
		"""
		additional_salaries = get_additional_salaries(
			self.employee, self.start_date, self.end_date, component_type
		)

		for additional_salary in additional_salaries:
			component_data = get_salary_component_data(additional_salary.component)
			remove_if_zero_valued = frappe.get_cached_value(
				"Salary Component", additional_salary.component, "remove_if_zero_valued"
			)
			if flt(additional_salary.amount) == 0 and remove_if_zero_valued:
				continue
			self.update_component_row(
				component_data,
				additional_salary.amount,
				component_type,
				additional_salary,
				is_recurring=additional_salary.is_recurring,
			)

			if component_type == "earnings" and hasattr(self, "benefit_ledger_components"):
				if (
					additional_salary.ref_doctype == "Employee Benefit Claim"
					and component_data.is_flexible_benefit
				) or component_data.accrual_component:
					if additional_salary.ref_doctype == "Employee Benefit Claim":
						remarks = f"Payout against Employee Benefit Claim {additional_salary.ref_docname}"
						flexible_benefit = 1
					else:
						remarks = "Accrual Component payout via Additional Salary"
						flexible_benefit = 0

					self.benefit_ledger_components.append(
						{
							"salary_component": additional_salary.component,
							"amount": additional_salary.amount,
							"is_accrual": 0,
							"transaction_type": "Payout",
							"flexible_benefit": flexible_benefit,
							"remarks": remarks,
						}
					)

	def on_submit(self):
		"""
		Post-submission tasks.
		"""
		super().on_submit()
		if self.za_localisation_applies:
			submit_eti_log(self.employee, self)

	def on_cancel(self):
		"""
		Post-cancellation tasks.
		"""
		if self.za_localisation_applies:
			cancel_eti_log(self.employee, self)
		super().on_cancel()

	def on_trash(self):
		"""Take this slip's ETI evidence with it.

		The log links to the slip by name, and Frappe reissues the same slip name
		when one is re-created for the same employee and period. A log left behind
		would then belong to a slip it never described.
		"""
		if self.za_localisation_applies:
			for name in frappe.get_all(
				"Employee ETI Log", filters={"against_salary_slip": self.name}, pluck="name"
			):
				frappe.delete_doc("Employee ETI Log", name, force=True, ignore_permissions=True)
		super().on_trash()


def get_eti_deduction(salary_slip):
	"""
	Wrapper function to calculate ETI for a salary slip.

	Args:
	    salary_slip: Salary Slip document

	Returns:
	    float: ETI amount
	"""
	remuneration = (
		salary_slip.get_statutory_earning_basis("za_uif_applicable")
		if hasattr(salary_slip, "get_statutory_earning_basis")
		else salary_slip.gross_pay
	)
	eligibility = check_eti_eligibility(salary_slip.employee, salary_slip, remuneration)

	if not eligibility["eligible"]:
		return 0

	return calculate_eti_amount(
		salary_slip.employee,
		salary_slip,
		remuneration,
		eligibility=eligibility,
	)


def get_tax_rebate_value(salary_slip, date_of_birth):
	"""
	Wrapper function to get tax rebates.

	Args:
	    salary_slip: Salary Slip document
	    date_of_birth (date): Employee date of birth

	Returns:
	    float: Tax rebate amount
	"""
	return get_tax_rebate(salary_slip, date_of_birth)


def get_medical_aid_value(salary_slip, dependants):
	"""
	Wrapper function to get medical aid credits.

	Args:
	    salary_slip: Salary Slip document
	    dependants (int): Number of dependants

	Returns:
	    float: Medical aid credit amount
	"""
	return get_medical_aid_credit(salary_slip, dependants)
