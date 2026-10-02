# Copyright (c) 2025, Cohenix and contributors
# For license information, please see license.txt

import hashlib

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate, today

from za_local_payroll.utils.integrations.eft_file_generator import (
	build_payment_batch_snapshot,
	normalize_bank_format,
	validate_payment_batch_header,
)


class PayrollPaymentBatch(Document):
	def validate(self):
		self._set_company_from_payroll_entry()
		self._set_batch_key()
		self._validate_no_active_duplicate()
		self.bank_format = normalize_bank_format(self.bank_format)
		validate_payment_batch_header(self)

	def before_submit(self):
		snapshot = build_payment_batch_snapshot(self)
		self.total_employees = len(snapshot.recipients)
		self.total_amount = snapshot.total_amount
		self.eft_source_hash = snapshot.source_hash

	def _set_company_from_payroll_entry(self):
		if not self.payroll_entry:
			frappe.throw(_("Payroll Entry is required."))
		company = frappe.db.get_value("Payroll Entry", self.payroll_entry, "company")
		if not company:
			frappe.throw(_("Payroll Entry {0} does not exist.").format(frappe.bold(self.payroll_entry)))
		if self.company and self.company != company:
			frappe.throw(_("Company must match Payroll Entry company {0}.").format(frappe.bold(company)))
		self.company = company

	def _set_batch_key(self):
		if self.payroll_entry:
			self.batch_key = hashlib.sha256(self.payroll_entry.encode()).hexdigest()

	def before_cancel(self):
		if (
			self.settlement_journal_entry
			and frappe.db.get_value("Journal Entry", self.settlement_journal_entry, "docstatus") == 1
		):
			frappe.throw(
				_("Cancel settlement Journal Entry {0} before cancelling this batch.").format(
					frappe.bold(self.settlement_journal_entry)
				),
				title=_("Batch Already Settled"),
			)

	@frappe.whitelist(methods=["POST"])
	def record_bank_settlement(self, posting_date=None):
		"""Post the bank's payment of this batch once the bank confirms it.

		Debits Payroll Payable for each employee's net pay and credits the bank
		account's ledger, from the same snapshot the payment file was built from.
		A changed snapshot (slips or bank details edited after submission) is refused.
		"""
		self.check_permission("submit")
		if self.docstatus != 1:
			frappe.throw(_("Submit the Payroll Payment Batch before recording its settlement."))
		if (
			self.settlement_journal_entry
			and frappe.db.get_value("Journal Entry", self.settlement_journal_entry, "docstatus") == 1
		):
			return self.settlement_journal_entry
		snapshot = build_payment_batch_snapshot(self)
		if snapshot.source_hash != self.eft_source_hash:
			frappe.throw(
				_(
					"Salary Slips or bank details changed after this batch was submitted. Cancel and amend it."
				),
				title=_("Batch Snapshot Changed"),
			)
		posting_date = getdate(posting_date or self.payment_date or today())
		payroll_payable = frappe.db.get_value("Payroll Entry", self.payroll_entry, "payroll_payable_account")
		bank_ledger = frappe.db.get_value("Bank Account", self.bank_account, "account")
		if not payroll_payable or not bank_ledger:
			frappe.throw(
				_("The Payroll Entry's Payroll Payable Account and the Bank Account's ledger are required.")
			)
		accounts = [
			{
				"account": payroll_payable,
				"party_type": "Employee",
				"party": recipient.employee,
				"debit_in_account_currency": flt(
					frappe.db.get_value("Salary Slip", recipient.salary_slip, "net_pay"), 2
				),
				"reference_type": "Payroll Entry",
				"reference_name": self.payroll_entry,
			}
			for recipient in snapshot.recipients
		]
		accounts.append({"account": bank_ledger, "credit_in_account_currency": flt(self.total_amount, 2)})
		journal = frappe.get_doc(
			{
				"doctype": "Journal Entry",
				"voucher_type": "Bank Entry",
				"company": self.company,
				"posting_date": posting_date,
				"cheque_no": self.name,
				"cheque_date": posting_date,
				"user_remark": _("Net pay paid by the bank for {0} under {1}").format(
					self.payroll_entry, self.name
				),
				"accounts": accounts,
			}
		)
		journal.insert()
		journal.submit()
		self.db_set({"settlement_journal_entry": journal.name, "settled_on": posting_date})
		return journal.name

	def on_cancel(self):
		cancelled_key = hashlib.sha256(f"{self.batch_key}|cancelled|{self.name}".encode()).hexdigest()
		self.db_set("batch_key", cancelled_key, update_modified=False)

	def _validate_no_active_duplicate(self):
		duplicate = frappe.db.get_value(
			"Payroll Payment Batch",
			{
				"payroll_entry": self.payroll_entry,
				"docstatus": ["<", 2],
				"name": ["!=", self.name],
			},
			"name",
		)
		if duplicate:
			frappe.throw(
				_("Payroll Entry {0} is already covered by active Payroll Payment Batch {1}.").format(
					frappe.bold(self.payroll_entry), frappe.bold(duplicate)
				),
				title=_("Duplicate Payroll Payment Batch"),
			)
