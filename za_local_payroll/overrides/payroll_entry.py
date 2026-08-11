"""
South African Payroll Entry Override

This module extends the standard HRMS Payroll Entry functionality to support
South African payroll requirements including frequency-based processing and
bank entry management.

Note: This module only works when HRMS is installed.
"""

import frappe
from erpnext.accounts.doctype.accounting_dimension.accounting_dimension import get_accounting_dimensions
from frappe import _
from frappe.utils import escape_html, flt, getdate

from za_local_payroll.utils.hrms import get_hrms_doctype_class, require_hrms

# Conditionally import HRMS classes
PayrollEntry = get_hrms_doctype_class("hrms.payroll.doctype.payroll_entry.payroll_entry", "PayrollEntry")

if PayrollEntry is None:
	# HRMS not available - create a dummy class to prevent import errors
	class PayrollEntry:
		pass


# Try to import get_employee_list
try:
	from hrms.payroll.doctype.payroll_entry.payroll_entry import get_employee_list
except ImportError:

	def get_employee_list(*args, **kwargs):
		require_hrms("Payroll Entry")
		return []


# Import ZA Local utilities
from za_local_core.localisation import is_south_african_company

from za_local_payroll.setup.preflight import validate_company_payroll_setup
from za_local_payroll.setup.statutory import validate_current_tax_configuration
from za_local_payroll.utils.payroll_utils import (
	get_current_block_period,
	get_employee_frequency_map,
	is_payroll_processed,
)

LOGGER = frappe.logger("za_local_payroll")


class ZAPayrollEntry(PayrollEntry):
	"""
	South African Payroll Entry implementation.

	Extends the standard Payroll Entry with:
	- Frequency-based payroll processing (Quarterly, Half-Yearly, Yearly)
	- Bank account validation for employees
	- Employee type validation
	"""

	@property
	def za_localisation_applies(self) -> bool:
		"""Whether South African statutory rules govern this run's company."""
		return is_south_african_company(self.get("company"))

	def validate(self):
		"""Run stock HRMS validation and mandatory SA employee checks on every save."""
		require_hrms("Payroll Entry")
		super().validate()
		if self.za_localisation_applies:
			self.validate_employee_requirements()

	def before_save(self):
		self.ensure_consistent_status()

	def before_cancel(self):
		active_batch = frappe.db.get_value(
			"Payroll Payment Batch",
			{"payroll_entry": self.name, "docstatus": ["<", 2]},
			"name",
		)
		if active_batch:
			frappe.throw(
				_("Cancel Payroll Payment Batch {0} before cancelling this Payroll Entry.").format(
					frappe.bold(active_batch)
				),
				title=_("Active Payroll Payment Batch"),
			)

	def on_submit(self):
		if hasattr(super(), "on_submit"):
			super().on_submit()
		self.db_set("status", "Submitted", update_modified=False)

	def on_cancel(self):
		if hasattr(super(), "on_cancel"):
			super().on_cancel()
		self._set_company_contribution_flags(0)
		self.db_set("status", "Cancelled", update_modified=False)

	def delete_linked_salary_slips(self):
		"""Remove dependent ETI evidence before HRMS deletes cancelled Salary Slips.

		HRMS deliberately deletes the Salary Slips when a Payroll Entry is cancelled.
		The app-owned ETI log is therefore a dependent calculation snapshot, not an
		independent statutory record that can outlive its source slip.
		"""
		salary_slip_names = [row.name for row in self.get_linked_salary_slips()]
		if salary_slip_names:
			log_names = frappe.get_all(
				"Employee ETI Log",
				filters={"against_salary_slip": ["in", salary_slip_names]},
				pluck="name",
			)
			for log_name in log_names:
				log = frappe.get_doc("Employee ETI Log", log_name)
				if log.docstatus == 1:
					log.cancel()
				frappe.delete_doc("Employee ETI Log", log_name, ignore_permissions=True)

		return super().delete_linked_salary_slips()

	def make_accrual_jv_entry(self, submitted_salary_slips):
		"""Post stock payroll accruals and the employer statutory contribution accrual."""
		super().make_accrual_jv_entry(submitted_salary_slips)
		if self.za_localisation_applies:
			self._ensure_company_contribution_entry()

	def ensure_consistent_status(self):
		if self.docstatus == 0 and self.get("status") == "Submitted":
			self.status = "Draft"
		elif self.docstatus == 1:
			self.status = "Submitted"
		elif self.docstatus == 2:
			self.status = "Cancelled"

	def validate_employee_requirements(self):
		"""
		Validate that all employees have required SA fields populated.

		Note: Bank account is only needed when creating bank entries (payments),
		not for creating salary slips. Employee type is always required.

		Employee metadata is fetched in one query so large payrolls do not cause
		two database round trips per employee during every save.
		"""
		employees = self.get("employees") or []
		if not employees:
			return

		employee_names = list(dict.fromkeys(row.employee for row in employees if row.employee))
		employee_details = {
			row.name: row
			for row in frappe.get_all(
				"Employee",
				filters={"name": ["in", employee_names]},
				fields=[
					"name",
					"employee_name",
					"za_employee_type",
					"za_payroll_payable_bank_account",
				],
			)
		}
		employees_without_employee_type = [
			row for row in employees if not employee_details.get(row.employee, {}).get("za_employee_type")
		]
		employees_without_bank_account = [
			row
			for row in employees
			if not employee_details.get(row.employee, {}).get("za_payroll_payable_bank_account")
		]

		if employees_without_employee_type:
			labels = []
			for row in employees_without_employee_type:
				detail = employee_details.get(row.employee) or {}
				employee_name = detail.get("employee_name") or row.get("employee_name") or ""
				labels.append(escape_html(f"{row.employee}: {employee_name}"))
			frappe.throw(
				_("Employee Type is required for the following employees:")
				+ "<br><ul><li>"
				+ "</li><li>".join(labels)
				+ "</li></ul>",
				title=_("Missing Required Field"),
			)

		if employees_without_bank_account:
			LOGGER.warning(
				"Payroll Entry %s has %s employee(s) without a payroll bank account: %s",
				self.name or "New Payroll Entry",
				len(employees_without_bank_account),
				", ".join(row.employee for row in employees_without_bank_account),
			)

	def validate_mandatory_fields(self):
		"""
		Validate that all mandatory fields are filled before creating salary slips.
		This prevents silent failures when the form is not properly saved.
		"""
		mandatory_fields = {
			"posting_date": _("Posting Date"),
			"company": _("Company"),
			"currency": _("Currency"),
			"exchange_rate": _("Exchange Rate"),
			"payroll_payable_account": _("Payroll Payable Account"),
			"payroll_frequency": _("Payroll Frequency"),
			"start_date": _("Start Date"),
			"end_date": _("End Date"),
			"cost_center": _("Cost Center"),
		}

		missing_fields = []
		for field, label in mandatory_fields.items():
			if not self.get(field):
				missing_fields.append(label)

		if missing_fields:
			error_msg = _("Mandatory fields required in Payroll Entry") + "<br><br><ul><li>"
			error_msg += "</li><li>".join(missing_fields)
			error_msg += "</li></ul>"
			frappe.throw(error_msg, title=_("Missing Fields"), exc=frappe.MandatoryError)

	@frappe.whitelist(methods=["POST"])
	def fill_employee_details(self):
		"""
		Fill employee details with frequency-based filtering.
		"""
		if not self.za_localisation_applies:
			return super().fill_employee_details()
		self.check_permission("write")
		filters = self.make_filters()
		employees = get_employee_list(filters=filters, as_dict=True, ignore_match_conditions=True)

		self.set("employees", [])

		if not employees:
			error_msg = _(
				"No employees found for the mentioned criteria:<br>Company: {0}<br>Currency: {1}"
			).format(
				frappe.bold(self.company),
				frappe.bold(self.currency),
			)
			if self.branch:
				error_msg += "<br>" + _("Branch: {0}").format(frappe.bold(self.branch))
			if self.department:
				error_msg += "<br>" + _("Department: {0}").format(frappe.bold(self.department))
			if self.designation:
				error_msg += "<br>" + _("Designation: {0}").format(frappe.bold(self.designation))
			if self.start_date:
				error_msg += "<br>" + _("Start date: {0}").format(frappe.bold(self.start_date))
			if self.end_date:
				error_msg += "<br>" + _("End date: {0}").format(frappe.bold(self.end_date))
			frappe.throw(error_msg, title=_("No employees found"))

		# Get frequency blocks and employee frequency mapping
		frequency = get_current_block_period(self)
		employee_frequency = get_employee_frequency_map()

		# Get payment timing setting
		pay_at = frappe.db.get_single_value("Employee Payroll Frequency", "pay_at")

		# Filter employees based on frequency
		for emp in employees:
			if emp.employee in employee_frequency:
				emp_freq = employee_frequency[emp.employee]

				frequency_period = frequency.get(emp_freq)
				if not frequency_period:
					frappe.throw(
						_("Could not resolve the {0} payroll period for employee {1}.").format(
							frappe.bold(emp_freq), frappe.bold(emp.employee)
						),
						title=_("Payroll Frequency Configuration Error"),
					)
				if pay_at == "Beginning of the period":
					if str(frequency_period.start_date) != str(self.start_date):
						continue
				elif pay_at == "End of the period":
					if str(frequency_period.end_date) != str(self.end_date):
						continue

			self.append("employees", emp)

		self.number_of_employees = len(self.employees)
		return self.get_employees_with_unmarked_attendance()

	@frappe.whitelist(methods=["POST"])
	def make_company_contribution_entry(self):
		"""
		Create a consolidated Journal Entry for Company Contributions (UIF ER, SDL, etc.).
		- Debits: Salary Component Account totals by component
		- Credit: Payroll Payable Account
		Also marks `Payroll Employee Detail.za_is_company_contribution_created` for all rows.
		"""
		self.check_permission("write")
		journal_entry = self._ensure_company_contribution_entry()
		if not journal_entry:
			frappe.msgprint(_("No company contributions were found on submitted Salary Slips."))
			return None
		frappe.msgprint(
			_("Company Contribution Journal Entry {0} is available.").format(frappe.bold(journal_entry)),
			indicator="green",
			alert=True,
		)
		return journal_entry

	def _ensure_company_contribution_entry(self):
		"""Create one submitted employer-contribution accrual for this Payroll Entry."""
		frappe.db.sql(
			"SELECT name FROM `tabPayroll Entry` WHERE name = %s FOR UPDATE",
			self.name,
		)

		JournalEntry = frappe.qb.DocType("Journal Entry")
		JournalEntryAccount = frappe.qb.DocType("Journal Entry Account")
		existing = (
			frappe.qb.from_(JournalEntry)
			.inner_join(JournalEntryAccount)
			.on(JournalEntry.name == JournalEntryAccount.parent)
			.select(JournalEntry.name)
			.where(
				(JournalEntry.docstatus < 2)
				& (JournalEntry.za_is_company_contribution == 1)
				& (JournalEntryAccount.reference_type == self.doctype)
				& (JournalEntryAccount.reference_name == self.name)
			)
			.limit(1)
		).run(pluck=True)
		if existing:
			self._set_company_contribution_flags(1)
			return existing[0]

		SalarySlip = frappe.qb.DocType("Salary Slip")
		Comp = frappe.qb.DocType("Company Contribution")

		slips = (
			frappe.qb.from_(SalarySlip)
			.select(SalarySlip.name)
			.where(
				(SalarySlip.docstatus == 1)
				& (SalarySlip.start_date >= self.start_date)
				& (SalarySlip.end_date <= self.end_date)
				& (SalarySlip.payroll_entry == self.name)
			)
		).run(pluck=True)

		if not slips:
			return None

		# Aggregate by component account
		totals_by_account = {}
		rows = (
			frappe.qb.from_(Comp)
			.select(Comp.parent, Comp.salary_component, Comp.amount)
			.where(
				(Comp.parent.isin(slips))
				& (Comp.parenttype == "Salary Slip")
				& (Comp.parentfield == "company_contribution")
			)
		).run(as_dict=True)

		component_names = sorted({row.salary_component for row in rows if row.salary_component})
		component_accounts = {
			row.parent: row.account
			for row in frappe.get_all(
				"Salary Component Account",
				filters={"parent": ["in", component_names], "company": self.company},
				fields=["parent", "account"],
			)
		}
		for r in rows:
			account = component_accounts.get(r.salary_component)
			if not account:
				frappe.throw(
					frappe._("Please set account in Salary Component {0}").format(
						frappe.get_desk_link("Salary Component", r.salary_component)
					)
				)
			totals_by_account[account] = totals_by_account.get(account, 0) + float(r.amount or 0)

		if not totals_by_account:
			return None

		# Build JE accounts
		precision = frappe.get_precision("Journal Entry Account", "debit_in_account_currency")
		accounts = []
		currencies = []
		company_currency = frappe.get_cached_value("Company", self.company, "default_currency")

		# Debits per component account
		for account, amount in totals_by_account.items():
			exchange_rate, amt = self.get_amount_and_exchange_rate_for_journal_entry(
				account, amount, company_currency, currencies
			)
			if amt:
				accounts.append(
					self.update_accounting_dimensions(
						{
							"account": account,
							"debit_in_account_currency": round(amt, precision),
							"exchange_rate": exchange_rate,
							"cost_center": self.cost_center,
						},
						get_accounting_dimensions() if hasattr(self, "get_accounting_dimensions") else [],
					)
				)

		# Single credit to payroll payable
		total_credit = sum(a["debit_in_account_currency"] for a in accounts)
		exchange_rate, amt = self.get_amount_and_exchange_rate_for_journal_entry(
			self.payroll_payable_account, total_credit, company_currency, currencies
		)
		accounts.append(
			self.update_accounting_dimensions(
				{
					"account": self.payroll_payable_account,
					"credit_in_account_currency": round(amt, precision),
					"exchange_rate": exchange_rate,
					"reference_type": self.doctype,
					"reference_name": self.name,
					"cost_center": self.cost_center,
				},
				get_accounting_dimensions() if hasattr(self, "get_accounting_dimensions") else [],
			)
		)

		# Create and submit JE
		je = self.make_journal_entry(
			accounts,
			currencies,
			payroll_payable_account=self.payroll_payable_account,
			voucher_type="Journal Entry",
			user_remark=_("Company Contribution for {0} to {1}").format(self.start_date, self.end_date),
			submit_journal_entry=True,
		)
		je.db_set(
			{"za_is_payroll_entry": 1, "za_is_company_contribution": 1},
			update_modified=False,
		)

		self._set_company_contribution_flags(1)
		return je.name

	def _set_company_contribution_flags(self, value):
		for employee in {row.employee for row in self.get("employees") or [] if row.employee}:
			frappe.db.set_value(
				"Payroll Employee Detail",
				{"parent": self.name, "employee": employee},
				"za_is_company_contribution_created",
				value,
			)

	@frappe.whitelist(methods=["POST"])
	def create_salary_slips(self):
		"""
		Create salary slips with frequency-based filtering.
		"""
		if not self.za_localisation_applies:
			return super().create_salary_slips()
		self.check_permission("write")
		validate_current_tax_configuration(self.company, self.end_date)
		validate_company_payroll_setup(self.company)

		# Validate mandatory fields before proceeding
		self.validate_mandatory_fields()

		# Ensure document is saved before creating salary slips
		# If document doesn't have a name, it hasn't been saved yet
		if not self.name:
			# Document hasn't been saved yet - save it first
			try:
				self.save()
			except Exception as e:
				# If save fails, show the error
				frappe.throw(
					_(
						"Cannot create salary slips. Please fix the errors and save the document first: {0}"
					).format(str(e)),
					title=_("Validation Error"),
				)

		employees = []

		frequency = get_current_block_period(self)
		employee_frequency = get_employee_frequency_map()

		for employee in self.employees:
			employee_frequency_name = employee_frequency.get(employee.employee)
			if employee_frequency_name:
				frequency_period = frequency.get(employee_frequency_name)
				if not frequency_period:
					frappe.throw(
						_("Could not resolve the {0} payroll period for employee {1}.").format(
							frappe.bold(employee_frequency_name),
							frappe.bold(employee.employee),
						),
						title=_("Payroll Frequency Configuration Error"),
					)
				if is_payroll_processed(employee.employee, frequency_period, self.company):
					continue
			employees.append(employee.employee)

		if employees:
			require_hrms("Payroll Entry - Create Salary Slips")
			try:
				from hrms.payroll.doctype.payroll_entry.payroll_entry import create_salary_slips_for_employees
			except ImportError:
				frappe.throw(_("HRMS is required to create salary slips. Please install HRMS app."))

			args = frappe._dict(
				{
					"salary_slip_based_on_timesheet": self.salary_slip_based_on_timesheet,
					"payroll_frequency": self.payroll_frequency,
					"start_date": self.start_date,
					"end_date": self.end_date,
					"company": self.company,
					"posting_date": self.posting_date,
					"deduct_tax_for_unsubmitted_tax_exemption_proof": self.deduct_tax_for_unsubmitted_tax_exemption_proof,
					"payroll_entry": self.name,
					"exchange_rate": self.exchange_rate,
					"currency": self.currency,
				}
			)

			try:
				if len(employees) > 30 or frappe.flags.enqueue_payroll_entry:
					# Enqueue for background processing
					frappe.enqueue(
						create_salary_slips_for_employees,
						timeout=600,
						employees=employees,
						args=args,
						publish_progress=True,
					)
					frappe.msgprint(
						_("Salary slip creation has been enqueued. It may take a few minutes to complete."),
						alert=True,
					)
				else:
					create_salary_slips_for_employees(employees, args, publish_progress=False)
					self.reload()

					created_for = set(
						frappe.get_all(
							"Salary Slip",
							filters={
								"payroll_entry": self.name,
								"employee": ["in", employees],
								"docstatus": ["<", 2],
							},
							pluck="employee",
						)
					)
					missing = sorted(set(employees) - created_for)
					if missing:
						detail = (self.error_message or "").strip()
						detail_message = _(" Payroll engine detail: {0}").format(detail) if detail else ""
						frappe.throw(
							_(
								"Salary Slips were not created for: {0}. Review the Payroll Entry Error Message and Error Log before continuing.{1}"
							).format(", ".join(missing), detail_message),
							title=_("Salary Slip Creation Incomplete"),
						)
					frappe.msgprint(_("Salary slips created successfully."), indicator="green", alert=True)

				return True
			except Exception as e:
				# Log the full error
				frappe.log_error(
					title=f"Payroll Entry salary slip creation failed: {self.name}",
					message=frappe.get_traceback(),
				)
				# Re-raise with a user-friendly message
				frappe.throw(
					_("Error creating salary slips: {0}. Please check the Error Log for details.").format(
						str(e)
					),
					title=_("Salary Slip Creation Failed"),
				)

		return False

	@frappe.whitelist(methods=["POST"])
	def make_payment_entry(self, selected_payment_account=None):
		"""Reject the retired direct-Journal-Entry payment path for South Africa.

		Companies outside South Africa keep the stock HRMS bank entry; the
		Payroll Payment Batch control exists for South African banking only.
		"""
		if not self.za_localisation_applies:
			return super().make_payment_entry(selected_payment_account)
		self.check_permission("write")
		frappe.throw(
			_(
				"Direct payroll bank Journal Entries are retired. Create and submit a Payroll "
				"Payment Batch, then generate its controlled private EFT file."
			),
			title=_("Use Payroll Payment Batch"),
		)


@frappe.whitelist(methods=["POST"])
def make_payment_entry_for_payroll(dt, dn, selected_payment_account=None):
	"""Compatibility endpoint that rejects the retired direct-Journal-Entry flow."""
	if dt != "Payroll Entry":
		frappe.throw(_("This action is only available for Payroll Entry."))
	if not frappe.db.exists(dt, dn):
		frappe.throw(_("{0} {1} does not exist").format(dt, dn))
	if not (frappe.has_permission(dt, "submit", dn) or frappe.has_permission(dt, "write", dn)):
		frappe.throw(
			_("You do not have permission to prepare payments for {0} {1}.").format(dt, dn),
			frappe.PermissionError,
			title=_("Permission Denied"),
		)
	frappe.throw(
		_(
			"Direct payroll bank Journal Entries are retired. Create and submit a Payroll "
			"Payment Batch, then generate its controlled private EFT file."
		),
		title=_("Use Payroll Payment Batch"),
	)


def get_payroll_entry_bank_entries(payroll_entry):
	"""Reject imports of the obsolete bank-entry grouping helper."""
	frappe.throw(
		_(
			"Direct payroll bank Journal Entries are retired. Use Payroll Payment Batch for "
			"validated employee routing, duplicate protection and EFT generation."
		),
		title=_("Use Payroll Payment Batch"),
	)
