# Copyright (c) 2025, Cohenix and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from za_local_payroll.utils.lump_sum_tax_utils import calculate_severance_tax
from za_local_payroll.utils.tax_utils import calculate_south_african_tax, calculate_uif_contribution


class EmployeeFinalSettlement(Document):
	def validate(self):
		"""Validate final settlement"""
		self.calculate_settlement()

	def before_submit(self):
		"""Actions before submission"""
		if not self.total_gross:
			frappe.throw(_("Please calculate settlement before submitting"))
		self.validate_tax_directive()

	def on_submit(self):
		"""Actions on submission"""
		frappe.msgprint(
			_("Final Settlement submitted. Process the approved values through the standard payroll flow.")
		)

	def calculate_settlement(self):
		"""
		Calculate complete final settlement.

		Components:
		- Notice pay (if not worked)
		- Severance pay (if applicable)
		- Leave payout (untaken annual leave)
		- Pro-rata bonus (if applicable)

		Deductions:
		- PAYE (special lump sum rates)
		- UIF (if applicable)
		"""
		# Total gross components
		notice_pay = flt(self.notice_pay)
		severance = flt(self.severance_pay)
		leave = flt(self.leave_payout)
		bonus = flt(self.bonus_prorata)

		self.total_gross = notice_pay + severance + leave + bonus

		severance_tax = self.get_directive_tax_amount()
		if not severance_tax and severance > 0:
			severance_tax = calculate_severance_tax(
				severance,
				date_value=self.separation_date,
				previous_lump_sums=self.previous_lump_sum_benefits,
			)

		normal_taxable = notice_pay + leave + bonus
		normal_tax = self.calculate_normal_termination_tax(normal_taxable)

		self.paye = flt(severance_tax) + flt(normal_tax)

		# UIF applies to normal termination remuneration, not severance benefits.
		self.uif = (
			calculate_uif_contribution(normal_taxable, self.separation_date)[0] if normal_taxable > 0 else 0
		)

		# Net settlement
		self.net_settlement = self.total_gross - self.paye - self.uif

	def validate_tax_directive(self):
		if flt(self.severance_pay) <= 0:
			return
		if not self.tax_directive:
			frappe.throw(
				_(
					"A SARS tax directive is required before submitting a settlement with a severance benefit."
				),
				title=_("Tax Directive Required"),
			)
		directive = frappe.get_doc("Tax Directive", self.tax_directive)
		if directive.employee != self.employee:
			frappe.throw(_("Tax Directive must belong to employee {0}.").format(self.employee))
		if directive.docstatus != 1 or directive.status != "Active":
			frappe.throw(
				_("Tax Directive {0} must be submitted and Active.").format(directive.directive_number)
			)

	def get_directive_tax_amount(self):
		if not self.tax_directive:
			return 0
		directive = frappe.get_doc("Tax Directive", self.tax_directive)
		if directive.directive_type in {"Fixed Amount", "Severance / Lump Sum"}:
			return flt(directive.fixed_amount)
		return 0

	def calculate_normal_termination_tax(self, amount):
		if flt(amount) <= 0:
			return 0
		annual_base = self.get_employee_annual_base()
		company = frappe.db.get_value("Employee", self.employee, "company")
		tax_context = {"date_value": self.separation_date, "company": company}
		base_tax = calculate_south_african_tax(annual_base, **tax_context)
		total_tax = calculate_south_african_tax(annual_base + flt(amount), **tax_context)
		return flt(max(0, total_tax - base_tax), 2)

	def get_employee_annual_base(self):
		assignment = frappe.get_all(
			"Salary Structure Assignment",
			filters={"employee": self.employee, "docstatus": 1, "from_date": ["<=", self.separation_date]},
			fields=["base"],
			order_by="from_date desc",
			limit=1,
		)
		if not assignment:
			return 0
		return flt(assignment[0].base) * 12

	@frappe.whitelist(methods=["POST"])
	def generate_final_payslip(self):
		"""Prevent fabrication of a Salary Slip outside the supported HRMS payroll flow."""
		self.check_permission("write")
		frappe.throw(
			_(
				"Automatic final payslip creation from this settlement is not supported. "
				"Process notice pay, leave payout, severance, directive tax, and other final amounts "
				"through the normal Payroll Entry and Salary Slip workflow."
			),
			title=_("Use the Standard Payroll Flow"),
		)

	@frappe.whitelist(methods=["POST"])
	def create_final_irp5(self):
		"""
		Create final IRP5 certificate for terminated employee.

		Returns:
			str: Name of created IRP5 certificate
		"""
		self.check_permission("write")
		if self.docstatus != 1:
			frappe.throw(_("Settlement must be submitted first"))

		frappe.throw(
			_(
				"Automatic final IRP5 creation from settlement is not available yet. "
				"Generate the IRP5/IT3(a) certificate from the EMP501 process after the final payroll is posted."
			),
			title=_("Use EMP501 Certificate Flow"),
		)
